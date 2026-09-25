"""Ticket lifecycle. Every mutation checks authorization, validates the
transition, records an audit event and commits; AI follow-ups run as jobs."""

from __future__ import annotations

import mimetypes
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.agents.schemas import TriageResult
from app.container import Container
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domain import policies
from app.domain.enums import (
    ESCALATION_REASON_LABELS,
    STATUS_LABELS,
    ActorType,
    AIStatus,
    CommentKind,
    CommentVisibility,
    Priority,
    StepSource,
    StepStatus,
    SupportLevel,
    TicketSource,
    TicketStatus,
    TicketType,
)
from app.domain.policies import Principal, TicketFacts
from app.domain.priority import determine_priority
from app.domain.state_machine import AUTO_START_FROM, DIRECTLY_SETTABLE, ensure_transition
from app.domain.taxonomy import normalize_category
from app.infrastructure.cache import key as cache_key
from app.infrastructure.telemetry import span
from app.models import Attachment, ResolutionStep, Ticket, TicketComment
from app.schemas.tickets import (
    ActivityItem,
    AttachmentView,
    CommentCreate,
    CommentView,
    EscalateRequest,
    ProgressView,
    ReassignRequest,
    RelatedArticle,
    RelatedIncident,
    RelatedView,
    ReopenRequest,
    ResolveRequest,
    StepCreate,
    StepReorder,
    StepUpdate,
    TicketListParams,
    TicketListResponse,
    TicketUpdate,
)
from app.services.assignment_service import AssignmentService
from app.services.audit_service import AuditService
from app.services.base import Repos, Service, utcnow
from app.services.presenters import TicketPresenter, facts, person_ref, progress_view
from app.services.sla_service import SlaService
from app.domain.sla import format_duration
from app.repositories.ticket_repository import TicketFilters

AI_LABEL = "Nexa Copilot"
SYSTEM_LABEL = "System"
ALLOWED_UPLOAD_TYPES = {
    "image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf", "text/plain",
    "text/csv", "application/json", "application/zip", "application/x-zip-compressed",
}


@dataclass
class NewTicket:
    description: str
    title: str | None = None
    ticket_type: TicketType = TicketType.INCIDENT
    priority: Priority | None = None
    service_id: uuid.UUID | None = None
    source: TicketSource = TicketSource.ASSISTANT
    conversation_id: uuid.UUID | None = None


def derive_title(description: str) -> str:
    first = re.split(r"(?<=[.!?])\s|\n", description.strip(), maxsplit=1)[0]
    first = first.strip().rstrip(".")
    return (first[:77] + "…") if len(first) > 80 else (first or "IT request")


class TicketService(Service):
    def __init__(self, repos: Repos, container: Container, principal: Principal) -> None:
        super().__init__(repos, container)
        self.principal = principal
        self.audit = AuditService(repos.audit)
        self.sla = SlaService(repos.settings, due_soon_minutes=container.settings.due_soon_minutes)
        self.assignment = AssignmentService(repos, self.audit)

    # ── access helpers ───────────────────────────────────────────────────
    async def load(self, ref: str | uuid.UUID, *, for_update: bool = False) -> Ticket:
        ticket = await self.repos.tickets.resolve_ref(str(ref), for_update=for_update)
        if ticket is None:
            raise NotFound("Ticket not found.")
        policies.ensure_can_view(self.principal, await self.facts(ticket))
        return ticket

    async def facts(self, ticket: Ticket) -> TicketFacts:
        previously = False
        if self.principal.is_engineer and ticket.assigned_to != self.principal.profile_id:
            previously = await self.repos.tickets.was_assigned(ticket.id, self.principal.profile_id)
        return facts(ticket, previously_assigned=previously)

    async def _ensure_work(self, ticket: Ticket) -> None:
        f = await self.facts(ticket)
        if TicketStatus(ticket.status) in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            raise Conflict("This ticket is resolved. Reopen it to make changes.", code="ticket_closed")
        policies.ensure(policies.can_work_ticket(self.principal, f), "Only the assigned engineer can work this ticket. Assign it to yourself first.")

    async def presenter(self) -> TicketPresenter:
        config = await self.repos.settings.ai_configuration()
        return TicketPresenter(
            self.repos, self.sla, self.principal, ai_threshold=float(config.confidence_threshold), ai_available=self.container.ai_available
        )

    async def _invalidate(self, *profile_ids: uuid.UUID | None) -> None:
        keys = [cache_key("dashboard", "engineer", pid) for pid in {p for p in profile_ids if p}]
        if keys:
            await self.container.cache.invalidate(*keys)

    async def _commit(self, ticket: Ticket, *extra: uuid.UUID | None) -> None:
        await self.commit()
        await self._invalidate(ticket.assigned_to, ticket.requester_id, self.principal.profile_id, *extra)

    # ── queries ──────────────────────────────────────────────────────────
    async def list(self, params: TicketListParams) -> TicketListResponse:
        filters = TicketFilters(
            scope=params.scope,
            ticket_type=params.ticket_type.value if params.ticket_type else None,
            statuses=tuple(s.value for s in params.status),
            priority=params.priority.value if params.priority else None,
            open_only=params.open_only,
            query=params.q,
            sort=params.sort,
            limit=params.limit,
            offset=params.offset,
        )
        tickets, total = await self.repos.tickets.list(self.principal, filters)
        items = await (await self.presenter()).summaries(tickets)
        return TicketListResponse(items=items, total=total, limit=params.limit, offset=params.offset)

    async def view(self, ref: str) -> Any:
        ticket = await self.load(ref)
        presenter = await self.presenter()
        f = await self.facts(ticket)
        if policies.can_view_internal(self.principal, f):
            return await presenter.detail(ticket)
        return await presenter.employee_detail(ticket)

    async def progress(self, ref: str) -> ProgressView:
        ticket = await self.load(ref)
        team = await self.repos.users.get_team(ticket.assignment_team_id) if ticket.assignment_team_id else None
        assignee = await self.repos.users.get(ticket.assigned_to) if ticket.assigned_to else None
        return progress_view(ticket, team=team, assignee=assignee)

    # ── creation ─────────────────────────────────────────────────────────
    async def create(self, data: NewTicket, *, triage: TriageResult | None = None, triage_model: str | None = None) -> Ticket:
        with span("ticket.create", **{"nexa.source": data.source.value, "nexa.ticket_type": data.ticket_type.value}) as current:
            config = await self.repos.settings.ai_configuration()
            service = await self.repos.settings.get_service(data.service_id) if data.service_id else None
            if service is None and triage and triage.service_hint:
                service = await self.repos.settings.get_service_by_name(triage.service_hint)

            category, subcategory = (None, None)
            priority_reason = "default"
            priority = data.priority
            impact = urgency = None
            if triage is not None:
                category, subcategory = normalize_category(triage.category, triage.subcategory)
                impact, urgency = triage.impact, triage.urgency
                decision = determine_priority(
                    impact=impact,
                    urgency=urgency,
                    ai_suggestion=triage.suggested_priority,
                    ticket_type=data.ticket_type,
                    category=category,
                    service_criticality=service.criticality if service else None,
                )
                if priority is None or not self.principal.is_staff:
                    priority, priority_reason = decision.priority, decision.reason
            if priority is None:
                priority = Priority.P3

            ai_enabled = self.container.ai_available and (config.ai_diagnosis_enabled or config.resolution_plans_enabled)
            ticket = Ticket(
                title=(data.title or (triage.title if triage else None) or derive_title(data.description))[:200],
                description=data.description,
                ticket_type=data.ticket_type.value,
                priority=Priority(priority).value,
                status=TicketStatus.NEW.value,
                category=category,
                subcategory=subcategory,
                impact=impact,
                urgency=urgency,
                requester_id=self.principal.profile_id,
                service_id=service.id if service else None,
                source=data.source.value,
                conversation_id=data.conversation_id,
                ai_status=AIStatus.PENDING.value if ai_enabled else AIStatus.SKIPPED.value,
            )
            await self.repos.tickets.add(ticket)
            await self.sla.apply(ticket)
            current.set_attribute("nexa.ticket_id", str(ticket.id))

            await self.audit.record(
                "ticket.created",
                actor=self.principal,
                ticket_id=ticket.id,
                new_value={"ticket_number": ticket.ticket_number, "title": ticket.title, "priority": ticket.priority, "type": ticket.ticket_type},
                metadata={"source": data.source.value, "priority_reason": priority_reason},
            )
            if triage is not None:
                await self.repos.tickets.upsert_analysis(
                    ticket.id,
                    category=category,
                    subcategory=subcategory,
                    priority=ticket.priority,
                    summary=triage.summary,
                    diagnosis=triage.likely_cause,
                    confidence=triage.confidence if triage.likely_cause else None,
                    signals=[s.model_dump() for s in triage.signals],
                    triage_model=triage_model,
                )
                await self.audit.record(
                    "ai.triage_completed",
                    actor_type=ActorType.AI,
                    ticket_id=ticket.id,
                    new_value={"category": category, "subcategory": subcategory, "priority": ticket.priority, "impact": impact, "urgency": urgency},
                    metadata={"model": triage_model, "priority_reason": priority_reason},
                )

            if data.conversation_id:
                await self.repos.tickets.link_conversation_attachments(data.conversation_id, ticket.id)

            if ai_enabled:
                ensure_transition(ticket.status, TicketStatus.TRIAGING)
                ticket.status = TicketStatus.TRIAGING.value
            else:
                # No AI investigation: route deterministically right away.
                decision = await self.assignment.route(
                    category=ticket.category, subcategory=ticket.subcategory, priority=ticket.priority,
                    ticket_type=ticket.ticket_type, service_id=ticket.service_id,
                )
                await self.assignment.assign(ticket, team_id=decision.team_id, support_level=decision.support_level, reason=decision.reason)
                ticket.status = TicketStatus.ASSIGNED.value
            await self._commit(ticket)

        if ai_enabled:
            from app.services.investigation_service import schedule_investigation

            await schedule_investigation(self.container, ticket.id)
        return ticket

    # ── updates ──────────────────────────────────────────────────────────
    async def _mark_engineer_activity(self, ticket: Ticket, *, requester_visible: bool = False) -> None:
        if not self.principal.is_staff or ticket.requester_id == self.principal.profile_id:
            return
        now = utcnow()
        if ticket.first_response_at is None:
            ticket.first_response_at = now
        if TicketStatus(ticket.status) in AUTO_START_FROM and ticket.assigned_to == self.principal.profile_id:
            await self._set_status(ticket, TicketStatus.IN_PROGRESS, reason="engineer_activity")

    async def _set_status(self, ticket: Ticket, target: TicketStatus, *, reason: str | None = None, actor_type: ActorType = ActorType.USER) -> None:
        if TicketStatus(ticket.status) == target:
            return
        ensure_transition(ticket.status, target)
        old = ticket.status
        ticket.status = target.value
        await self.audit.record(
            "ticket.status_changed",
            actor=self.principal if actor_type == ActorType.USER else None,
            actor_type=actor_type,
            ticket_id=ticket.id,
            old_value=old,
            new_value=target.value,
            metadata={"reason": reason} if reason else None,
        )

    async def update(self, ref: str, patch: TicketUpdate) -> Ticket:
        ticket = await self.load(ref, for_update=True)
        await self._ensure_work(ticket)
        changes = patch.model_dump(exclude_unset=True)
        with span("ticket.update", **{"nexa.ticket_id": str(ticket.id), "nexa.fields": ",".join(sorted(changes))}):
            if "priority" in changes and patch.priority and patch.priority.value != ticket.priority:
                old = ticket.priority
                ticket.priority = patch.priority.value
                await self.sla.apply(ticket)
                await self.audit.record("ticket.priority_changed", actor=self.principal, ticket_id=ticket.id, old_value=old, new_value=ticket.priority)
            if "title" in changes and patch.title and patch.title != ticket.title:
                old = ticket.title
                ticket.title = patch.title
                await self.audit.record("ticket.title_changed", actor=self.principal, ticket_id=ticket.id, old_value=old, new_value=ticket.title)
            if "ticket_type" in changes and patch.ticket_type and patch.ticket_type.value != ticket.ticket_type:
                old = ticket.ticket_type
                ticket.ticket_type = patch.ticket_type.value
                await self.audit.record("ticket.type_changed", actor=self.principal, ticket_id=ticket.id, old_value=old, new_value=ticket.ticket_type)
            if "service_id" in changes and patch.service_id != ticket.service_id:
                if patch.service_id and await self.repos.settings.get_service(patch.service_id) is None:
                    raise ValidationFailed("Unknown service.")
                old = str(ticket.service_id) if ticket.service_id else None
                ticket.service_id = patch.service_id
                await self.audit.record("ticket.service_changed", actor=self.principal, ticket_id=ticket.id, old_value=old, new_value=str(patch.service_id) if patch.service_id else None)
            if "category" in changes or "subcategory" in changes:
                cat, sub = normalize_category(changes.get("category", ticket.category), changes.get("subcategory", ticket.subcategory))
                if (cat, sub) != (ticket.category, ticket.subcategory):
                    old = {"category": ticket.category, "subcategory": ticket.subcategory}
                    ticket.category, ticket.subcategory = cat, sub
                    await self.audit.record("ticket.category_changed", actor=self.principal, ticket_id=ticket.id, old_value=old, new_value={"category": cat, "subcategory": sub})
            if "status" in changes and patch.status:
                if patch.status not in DIRECTLY_SETTABLE:
                    raise ValidationFailed(
                        "Use the dedicated action to escalate, resolve, reopen or close a ticket.", code="use_dedicated_action"
                    )
                await self._set_status(ticket, patch.status)
            await self._mark_engineer_activity(ticket)
            await self._commit(ticket)
        return ticket

    async def assign_to_me(self, ref: str) -> Ticket:
        ticket = await self.load(ref, for_update=True)
        f = await self.facts(ticket)
        policies.ensure(policies.can_self_assign(self.principal, f), "You can only pick up unassigned tickets from your team's queue.")
        me = await self.repos.users.get(self.principal.profile_id)
        previous = ticket.assigned_to
        await self.assignment.assign(
            ticket,
            team_id=ticket.assignment_team_id or (me.team_id if me else None),
            support_level=ticket.support_level,
            reason="self_assign",
            engineer=me,
            actor=self.principal,
            actor_type=ActorType.USER,
        )
        if TicketStatus(ticket.status) in (TicketStatus.NEW, TicketStatus.TRIAGING):
            # Investigation still running — the engineer takes it as-is.
            pass
        await self._commit(ticket, previous)
        return ticket

    async def reassign(self, ref: str, request: ReassignRequest) -> Ticket:
        ticket = await self.load(ref, for_update=True)
        f = await self.facts(ticket)
        policies.ensure(policies.can_reassign(self.principal, f), "Only the assigned engineer or an admin can reassign this ticket.")
        if request.assignee_id is None and request.team_id is None:
            raise ValidationFailed("Choose an engineer or a team.")
        engineer = None
        team_id = request.team_id or ticket.assignment_team_id
        if request.assignee_id:
            engineer = await self.repos.users.get(request.assignee_id)
            if engineer is None or not engineer.is_active or engineer.engineer_level is None:
                raise ValidationFailed("That person can't be assigned tickets.")
            team_id = request.team_id or engineer.team_id
        if team_id and await self.repos.users.get_team(team_id) is None:
            raise ValidationFailed("Unknown team.")
        previous = ticket.assigned_to
        await self.assignment.assign(
            ticket,
            team_id=team_id,
            support_level=engineer.engineer_level if engineer else ticket.support_level,
            reason="manual",
            engineer=engineer,
            pick_engineer=engineer is None,
            actor=self.principal,
            actor_type=ActorType.USER,
            exclude_engineer=previous,
            metadata={"note": request.note} if request.note else None,
        )
        if request.note:
            await self.repos.tickets.add_comment(
                TicketComment(ticket_id=ticket.id, author_id=self.principal.profile_id, content=request.note, visibility=CommentVisibility.INTERNAL.value, kind=CommentKind.COMMENT.value)
            )
        if TicketStatus(ticket.status) not in (TicketStatus.NEW, TicketStatus.TRIAGING, TicketStatus.ASSIGNED):
            await self._set_status(ticket, TicketStatus.ASSIGNED, reason="reassigned")
        await self._commit(ticket, previous)
        return ticket

    async def escalate(self, ref: str, request: EscalateRequest) -> Ticket:
        ticket = await self.load(ref, for_update=True)
        await self._ensure_work(ticket)
        target_team_id = request.target_team_id or ticket.assignment_team_id
        if target_team_id is None:
            desk = await self.repos.users.service_desk()
            target_team_id = desk.id if desk else None
        target_team = await self.repos.users.get_team(target_team_id) if target_team_id else None
        if target_team is None:
            raise ValidationFailed("Choose the team to escalate to.")
        if ticket.support_level == SupportLevel.L2.value and target_team.id == ticket.assignment_team_id:
            raise Conflict("This ticket is already with L2 in that team. Choose a different team or reassign.", code="already_l2")

        with span("ticket.escalate", **{"nexa.ticket_id": str(ticket.id), "nexa.reason": request.reason.value}):
            from_engineer = ticket.assigned_to
            engineer = await self.assignment.assign(
                ticket,
                team_id=target_team.id,
                support_level=SupportLevel.L2.value,
                reason="escalation",
                actor=self.principal,
                actor_type=ActorType.USER,
                exclude_engineer=from_engineer,
                metadata={"escalation_reason": request.reason.value},
            )
            ensure_transition(ticket.status, TicketStatus.ESCALATED)
            old_status = ticket.status
            ticket.status = TicketStatus.ESCALATED.value
            ticket.escalation_count += 1
            if request.note:
                await self.repos.tickets.add_comment(
                    TicketComment(
                        ticket_id=ticket.id, author_id=self.principal.profile_id, content=request.note,
                        visibility=CommentVisibility.INTERNAL.value, kind=CommentKind.ESCALATION_NOTE.value,
                    )
                )
            await self.audit.record(
                "ticket.escalated",
                actor=self.principal,
                ticket_id=ticket.id,
                old_value={"status": old_status, "support_level": "L1" if ticket.escalation_count == 1 else ticket.support_level, "assigned_to": str(from_engineer) if from_engineer else None},
                new_value={"status": ticket.status, "support_level": "L2", "assigned_to": str(engineer.id) if engineer else None, "assignee_name": engineer.name if engineer else None},
                metadata={
                    "reason": request.reason.value,
                    "reason_label": ESCALATION_REASON_LABELS[request.reason],
                    "note": request.note,
                    "to_team_id": str(target_team.id),
                    "to_team_name": target_team.name,
                },
            )
            await self._commit(ticket, from_engineer)

        config = await self.repos.settings.ai_configuration()
        if self.container.ai_available and config.ai_diagnosis_enabled:
            from app.services.resolution_service import schedule_handoff_brief

            await schedule_handoff_brief(self.container, ticket.id)
        return ticket

    async def resolve(self, ref: str, request: ResolveRequest) -> Ticket:
        ticket = await self.load(ref, for_update=True)
        await self._ensure_work(ticket)
        with span("ticket.resolve", **{"nexa.ticket_id": str(ticket.id), "nexa.resolution_code": request.resolution_code.value}):
            ensure_transition(ticket.status, TicketStatus.RESOLVED)
            old_status = ticket.status
            now = utcnow()
            ticket.status = TicketStatus.RESOLVED.value
            ticket.resolution_summary = request.resolution_summary.strip()
            ticket.resolution_code = request.resolution_code.value
            ticket.resolved_at = now
            ticket.resolved_by = self.principal.profile_id
            ticket.resolution_ai_summary = None
            if ticket.first_response_at is None:
                ticket.first_response_at = now
            await self.repos.tickets.add_comment(
                TicketComment(
                    ticket_id=ticket.id, author_id=self.principal.profile_id, content=ticket.resolution_summary,
                    visibility=CommentVisibility.REQUESTER.value, kind=CommentKind.RESOLUTION.value,
                )
            )
            steps = await self.repos.tickets.list_steps(ticket.id)
            await self.audit.record(
                "ticket.resolved",
                actor=self.principal,
                ticket_id=ticket.id,
                old_value={"status": old_status},
                new_value={"status": ticket.status, "resolution_code": ticket.resolution_code, "summary": ticket.resolution_summary},
                metadata={
                    "completed_steps": sum(1 for s in steps if s.status == StepStatus.COMPLETED.value),
                    "pending_steps": sum(1 for s in steps if s.status in (StepStatus.PENDING.value, StepStatus.IN_PROGRESS.value)),
                    "resolution_minutes": int((now - ticket.created_at).total_seconds() // 60),
                },
            )
            await self._commit(ticket)

        from app.services.resolution_service import schedule_post_resolution

        await schedule_post_resolution(self.container, ticket.id)
        return ticket

    async def reopen(self, ref: str, request: ReopenRequest) -> Ticket:
        ticket = await self.load(ref, for_update=True)
        policies.ensure(policies.can_reopen(self.principal, await self.facts(ticket)), "You can't reopen this ticket.")
        ensure_transition(ticket.status, TicketStatus.REOPENED)
        old = {"status": ticket.status, "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None}
        now = utcnow()
        ticket.status = TicketStatus.REOPENED.value
        ticket.reopen_count += 1
        ticket.resolved_at = None
        ticket.closed_at = None
        await self.sla.apply(ticket, start=now)
        await self.repos.tickets.add_comment(
            TicketComment(
                ticket_id=ticket.id, author_id=self.principal.profile_id, content=request.reason.strip(),
                visibility=CommentVisibility.REQUESTER.value, kind=CommentKind.COMMENT.value,
            )
        )
        if ticket.assigned_to is None and ticket.assignment_team_id:
            await self.assignment.assign(ticket, team_id=ticket.assignment_team_id, support_level=ticket.support_level, reason="reopened")
        await self.audit.record("ticket.reopened", actor=self.principal, ticket_id=ticket.id, old_value=old, new_value={"status": ticket.status}, metadata={"reason": request.reason})
        await self.repos.knowledge.remove_incident(ticket.id)
        await self._commit(ticket)
        return ticket

    async def close(self, ref: str) -> Ticket:
        ticket = await self.load(ref, for_update=True)
        policies.ensure(policies.can_close(self.principal, await self.facts(ticket)), "You can't close this ticket.")
        ensure_transition(ticket.status, TicketStatus.CLOSED)
        ticket.status = TicketStatus.CLOSED.value
        ticket.closed_at = utcnow()
        confirmed_by_requester = ticket.requester_id == self.principal.profile_id
        await self.audit.record(
            "ticket.closed", actor=self.principal, ticket_id=ticket.id, old_value="resolved", new_value="closed",
            metadata={"confirmed_by_requester": confirmed_by_requester},
        )
        await self._commit(ticket)
        return ticket

    # ── resolution steps ─────────────────────────────────────────────────
    async def add_step(self, ref: str, data: StepCreate) -> ResolutionStep:
        ticket = await self.load(ref, for_update=True)
        await self._ensure_work(ticket)
        steps = list(await self.repos.tickets.list_steps(ticket.id))
        position = len(steps) if data.position is None else min(data.position, len(steps))
        step = ResolutionStep(
            ticket_id=ticket.id,
            position=position,
            description=data.description.strip(),
            details=(data.details or "").strip() or None,
            technical_details=(data.technical_details or "").strip() or None,
            status=StepStatus.PENDING.value,
            source=StepSource.ENGINEER.value,
            created_by=self.principal.profile_id,
            updated_by=self.principal.profile_id,
        )
        steps.insert(position, step)
        await self.repos.tickets.add_step(step)
        await self.repos.tickets.renumber_steps(ticket.id, [s.id for s in steps])
        await self.audit.record("step.added", actor=self.principal, ticket_id=ticket.id, entity_type="step", entity_id=step.id, new_value={"description": step.description, "position": position})
        await self._mark_engineer_activity(ticket)
        await self._commit(ticket)
        await self.session.refresh(step)
        return step

    async def update_step(self, ref: str, step_id: uuid.UUID, patch: StepUpdate) -> ResolutionStep:
        ticket = await self.load(ref, for_update=True)
        await self._ensure_work(ticket)
        step = await self.repos.tickets.get_step(ticket.id, step_id)
        if step is None:
            raise NotFound("Step not found.")
        changes = patch.model_dump(exclude_unset=True)
        text_fields: dict[str, str | None] = {}
        for field_name in ("description", "details", "technical_details"):
            if field_name not in changes:
                continue
            value = (changes[field_name] or "").strip() or None
            if field_name == "description" and value is None:
                raise ValidationFailed("A step needs a description.")
            text_fields[field_name] = value
        text_changed = {k: v for k, v in text_fields.items() if v != getattr(step, k)}
        if text_changed:
            if step.source == StepSource.AI.value and step.ai_original is None:
                step.ai_original = {"description": step.description, "details": step.details, "technical_details": step.technical_details}
            old = {k: getattr(step, k) for k in text_changed}
            for k, v in text_changed.items():
                setattr(step, k, v)
            step.edited = True
            await self.audit.record("step.edited", actor=self.principal, ticket_id=ticket.id, entity_type="step", entity_id=step.id, old_value=old, new_value=text_changed)
        if "notes" in changes and (patch.notes or None) != step.notes:
            step.notes = (patch.notes or "").strip() or None
            await self.audit.record("step.note_added", actor=self.principal, ticket_id=ticket.id, entity_type="step", entity_id=step.id, new_value={"description": step.description, "note": step.notes})
        if patch.status and patch.status.value != step.status:
            old_status = step.status
            step.status = patch.status.value
            if patch.status == StepStatus.COMPLETED:
                step.completed_at = utcnow()
                step.completed_by = self.principal.profile_id
                action = "step.completed"
            else:
                step.completed_at = None
                step.completed_by = None
                action = "step.status_changed"
            await self.audit.record(
                action, actor=self.principal, ticket_id=ticket.id, entity_type="step", entity_id=step.id,
                old_value=old_status, new_value=step.status, metadata={"description": step.description, "note": step.notes},
            )
        step.updated_by = self.principal.profile_id
        await self._mark_engineer_activity(ticket)
        await self._commit(ticket)
        await self.session.refresh(step)
        return step

    async def delete_step(self, ref: str, step_id: uuid.UUID) -> None:
        ticket = await self.load(ref, for_update=True)
        await self._ensure_work(ticket)
        step = await self.repos.tickets.get_step(ticket.id, step_id)
        if step is None:
            raise NotFound("Step not found.")
        step.deleted_at = utcnow()
        step.deleted_by = self.principal.profile_id
        remaining = [s.id for s in await self.repos.tickets.list_steps(ticket.id) if s.id != step.id]
        await self.repos.tickets.renumber_steps(ticket.id, remaining)
        await self.audit.record(
            "step.deleted", actor=self.principal, ticket_id=ticket.id, entity_type="step", entity_id=step.id,
            old_value={"description": step.description, "status": step.status, "source": step.source},
        )
        await self._mark_engineer_activity(ticket)
        await self._commit(ticket)

    async def reorder_steps(self, ref: str, request: StepReorder) -> Sequence[ResolutionStep]:
        ticket = await self.load(ref, for_update=True)
        await self._ensure_work(ticket)
        steps = await self.repos.tickets.list_steps(ticket.id)
        current_ids = [s.id for s in steps]
        if sorted(map(str, request.step_ids)) != sorted(map(str, current_ids)) or len(set(request.step_ids)) != len(request.step_ids):
            raise ValidationFailed("Reorder must include every current step exactly once.")
        if request.step_ids != current_ids:
            await self.repos.tickets.renumber_steps(ticket.id, request.step_ids)
            await self.audit.record(
                "step.reordered", actor=self.principal, ticket_id=ticket.id, entity_type="step",
                old_value=[str(i) for i in current_ids], new_value=[str(i) for i in request.step_ids],
            )
            await self._mark_engineer_activity(ticket)
            await self._commit(ticket)
        for step in steps:
            await self.session.refresh(step)
        return await self.repos.tickets.list_steps(ticket.id)

    async def restore_ai_steps(self, ref: str) -> Sequence[ResolutionStep]:
        """Undo engineer edits/deletions of AI-suggested steps (engineer steps are kept)."""
        ticket = await self.load(ref, for_update=True)
        await self._ensure_work(ticket)
        restored = reverted = 0
        all_steps = await self.repos.tickets.list_steps(ticket.id, include_deleted=True)
        for step in all_steps:
            if step.source != StepSource.AI.value:
                continue
            if step.deleted_at is not None:
                step.deleted_at, step.deleted_by = None, None
                restored += 1
            if step.ai_original:
                step.description = step.ai_original.get("description") or step.description
                step.details = step.ai_original.get("details")
                step.technical_details = step.ai_original.get("technical_details")
                step.ai_original, step.edited = None, False
                reverted += 1
        if restored or reverted:
            live = [s for s in all_steps if s.deleted_at is None]
            ai_first = sorted(live, key=lambda s: (s.source != StepSource.AI.value, s.position))
            await self.repos.tickets.renumber_steps(ticket.id, [s.id for s in ai_first])
            await self.audit.record("step.restored", actor=self.principal, ticket_id=ticket.id, entity_type="step", metadata={"restored": restored, "reverted": reverted})
            await self._commit(ticket)
        return await self.repos.tickets.list_steps(ticket.id)

    # ── comments ─────────────────────────────────────────────────────────
    async def comments(self, ref: str) -> list[CommentView]:
        ticket = await self.load(ref)
        internal = policies.can_view_internal(self.principal, await self.facts(ticket))
        rows = await self.repos.tickets.list_comments(ticket.id, include_internal=internal)
        people = await self.repos.users.get_many([c.author_id for c in rows])
        teams = await self.repos.users.teams_by_ids([p.team_id for p in people.values()])
        out = []
        for c in rows:
            author = people.get(c.author_id) if c.author_id else None
            label = author.name if author else (AI_LABEL if c.author_type == "ai" else SYSTEM_LABEL)
            out.append(
                CommentView(
                    id=c.id, author=person_ref(author, teams, include_email=False), author_type=c.author_type, author_label=label,
                    content=c.content, visibility=c.visibility, kind=c.kind, created_at=c.created_at,
                )
            )
        return out

    async def add_comment(self, ref: str, data: CommentCreate) -> TicketComment:
        ticket = await self.load(ref, for_update=True)
        f = await self.facts(ticket)
        visibility = data.visibility if self.principal.is_staff else CommentVisibility.REQUESTER
        policies.ensure(policies.can_comment(self.principal, f, visibility), "You can't comment on this ticket.")
        if TicketStatus(ticket.status) == TicketStatus.CLOSED:
            raise Conflict("This ticket is closed. Reopen it to continue the conversation.", code="ticket_closed")
        is_requester = ticket.requester_id == self.principal.profile_id
        kind = CommentKind.QUESTION if (data.request_info and self.principal.is_staff and not is_requester) else CommentKind.COMMENT
        if kind == CommentKind.QUESTION:
            visibility = CommentVisibility.REQUESTER
        comment = await self.repos.tickets.add_comment(
            TicketComment(ticket_id=ticket.id, author_id=self.principal.profile_id, content=data.content.strip(), visibility=visibility.value, kind=kind.value)
        )
        await self.audit.record(
            "comment.added", actor=self.principal, ticket_id=ticket.id, entity_type="comment", entity_id=comment.id,
            new_value={"visibility": visibility.value, "kind": kind.value},
        )
        status = TicketStatus(ticket.status)
        if kind == CommentKind.QUESTION and policies.can_work_ticket(self.principal, f):
            await self._set_status(ticket, TicketStatus.PENDING_USER, reason="asked_requester")
            if ticket.first_response_at is None:
                ticket.first_response_at = utcnow()
        elif is_requester and status == TicketStatus.PENDING_USER:
            await self._set_status(ticket, TicketStatus.PENDING_ENGINEER, reason="requester_replied")
        elif self.principal.is_staff and not is_requester and ticket.assigned_to == self.principal.profile_id and status not in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
            await self._mark_engineer_activity(ticket, requester_visible=visibility == CommentVisibility.REQUESTER)
        await self._commit(ticket)
        return comment

    # ── activity timeline ────────────────────────────────────────────────
    async def activity(self, ref: str) -> list[ActivityItem]:
        ticket = await self.load(ref)
        internal = policies.can_view_internal(self.principal, await self.facts(ticket))
        events = await self.repos.audit.for_ticket(ticket.id)
        people = await self.repos.users.get_many([e.actor_id for e in events])
        items: list[ActivityItem] = []
        for event in events:
            rendered = _describe(event.action, event.old_value, event.new_value, event.metadata_ or {}, internal=internal, source=ticket.source)
            if rendered is None:
                continue
            summary, detail = rendered
            actor = people.get(event.actor_id) if event.actor_id else None
            label = actor.name if actor else (AI_LABEL if event.actor_type == ActorType.AI.value else SYSTEM_LABEL)
            items.append(ActivityItem(id=event.id, at=event.created_at, actor_type=event.actor_type, actor_label=label, action=event.action, summary=summary, detail=detail))
        return items

    # ── related knowledge & incidents ────────────────────────────────────
    async def related(self, ref: str) -> RelatedView:
        ticket = await self.load(ref)
        policies.ensure(policies.can_view_internal(self.principal, await self.facts(ticket)), "Related incidents are available to IT staff.")
        from app.services.knowledge_service import KnowledgeService

        knowledge = KnowledgeService(self.repos, self.container)
        analysis = await self.repos.tickets.get_analysis(ticket.id)
        query = " ".join(filter(None, [ticket.title, ticket.description, analysis.diagnosis if analysis else None]))
        incidents = await knowledge.search_incidents(query, exclude_ticket_id=ticket.id, limit=5)
        articles = await knowledge.search_articles(query, limit=5)
        return RelatedView(
            similar_incidents=[
                RelatedIncident(
                    ticket_id=h.ticket_id, ticket_number=h.ticket_number, title=h.title, resolution_summary=h.resolution_summary,
                    resolved_in=format_duration((h.resolved_at - h.created_at).total_seconds()) if h.resolved_at else None,
                    similarity=h.similarity,
                )
                for h in incidents
            ],
            knowledge=[
                RelatedArticle(article_id=h.article_id, article_number=h.article_number, title=h.title, excerpt=h.excerpt[:280], updated_at=h.updated_at, similarity=h.similarity)
                for h in articles
            ],
        )

    # ── attachments ──────────────────────────────────────────────────────
    async def upload_attachment(self, ref: str, *, file_name: str, content: bytes, content_type: str | None) -> AttachmentView:
        ticket = await self.load(ref, for_update=True)
        f = await self.facts(ticket)
        policies.ensure(policies.can_comment(self.principal, f, CommentVisibility.REQUESTER), "You can't add files to this ticket.")
        attachment = await store_attachment(
            self.container, self.repos, ticket_id=ticket.id, conversation_id=None, uploaded_by=self.principal.profile_id,
            file_name=file_name, content=content, content_type=content_type,
        )
        await self.audit.record("attachment.added", actor=self.principal, ticket_id=ticket.id, entity_type="attachment", entity_id=attachment.id, new_value={"file_name": attachment.file_name})
        await self._commit(ticket)
        return AttachmentView(id=attachment.id, file_name=attachment.file_name, content_type=attachment.content_type, size_bytes=attachment.size_bytes, created_at=attachment.created_at)

    async def attachments(self, ref: str) -> list[AttachmentView]:
        ticket = await self.load(ref)
        rows = await self.repos.tickets.list_attachments(ticket.id)
        people = await self.repos.users.get_many([a.uploaded_by for a in rows])
        out = []
        for a in rows:
            url = None
            if self.container.settings.supabase_admin_configured:
                try:
                    url = await self.container.supabase.signed_url(a.bucket, a.storage_path, expires_in=300)
                except Exception:  # noqa: BLE001 — listing still works without a link
                    url = None
            out.append(AttachmentView(id=a.id, file_name=a.file_name, content_type=a.content_type, size_bytes=a.size_bytes, uploaded_by=person_ref(people.get(a.uploaded_by), include_email=False), created_at=a.created_at, url=url))
        return out


async def store_attachment(
    container: Container,
    repos: Repos,
    *,
    ticket_id: uuid.UUID | None,
    conversation_id: uuid.UUID | None,
    uploaded_by: uuid.UUID,
    file_name: str,
    content: bytes,
    content_type: str | None,
) -> Attachment:
    if len(content) == 0:
        raise ValidationFailed("The file is empty.")
    if len(content) > container.settings.max_upload_bytes:
        raise ValidationFailed(f"Files must be under {container.settings.max_upload_bytes // (1024 * 1024)} MB.")
    safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", file_name).strip()[:120] or "attachment"
    guessed = content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    if guessed not in ALLOWED_UPLOAD_TYPES:
        raise ValidationFailed("That file type isn't supported. Use an image, PDF, text, CSV, JSON or ZIP file.")
    scope = f"tickets/{ticket_id}" if ticket_id else f"conversations/{conversation_id}"
    path = f"{scope}/{uuid.uuid4().hex}-{safe_name}"
    await container.supabase.upload("ticket-attachments", path, content, guessed)
    return await repos.tickets.add_attachment(
        Attachment(bucket="ticket-attachments", storage_path=path, file_name=safe_name, content_type=guessed, size_bytes=len(content), ticket_id=ticket_id, conversation_id=conversation_id, uploaded_by=uploaded_by)
    )


def _describe(action: str, old: Any, new: Any, meta: dict[str, Any], *, internal: bool, source: str) -> tuple[str, str | None] | None:
    """Human summary for an audit event; None hides it from this viewer."""
    new = new if isinstance(new, dict) else ({"value": new} if new is not None else {})
    old = old if isinstance(old, dict) else ({"value": old} if old is not None else {})
    status_label = lambda v: STATUS_LABELS.get(TicketStatus(v), v) if v in {s.value for s in TicketStatus} else str(v)  # noqa: E731
    match action:
        case "ticket.created":
            origin = {"assistant": "from the AI assistant", "portal": "from the portal", "email": "from email", "api": "via the API"}.get(source, "")
            return f"Ticket created {origin}".strip(), None
        case "ai.triage_completed":
            if not internal:
                return None
            cat = " / ".join(filter(None, [new.get("category"), new.get("subcategory")]))
            return f"Classified as {cat or 'uncategorised'} · {new.get('priority')}", meta.get("priority_reason")
        case "ai.analysis_generated":
            return ("Prepared diagnosis and evidence", new.get("diagnosis")) if internal else None
        case "ai.plan_generated":
            return (f"Generated {new.get('steps', 'a')}-step resolution plan", None) if internal else ("Prepared a resolution plan for the engineer", None)
        case "ai.investigation_failed":
            return ("AI investigation failed — continue manually", meta.get("stage")) if internal else None
        case "ai.handoff_generated":
            return ("Prepared the L2 handoff brief", None) if internal else None
        case "ai.resolution_summary_generated":
            return ("Summarised the resolution for the requester", None) if internal else None
        case "ticket.assigned":
            who, team = new.get("assignee_name"), new.get("team_name")
            if who:
                return f"Assigned to {who}" + (f" ({team})" if team else ""), meta.get("reason") if internal else None
            return (f"Routed to the {team} queue" if team else "Unassigned"), meta.get("reason") if internal else None
        case "ticket.status_changed":
            return f"Status changed to {status_label(new.get('value'))}", None
        case "ticket.priority_changed":
            return f"Priority changed from {old.get('value')} to {new.get('value')}", None
        case "ticket.title_changed" | "ticket.type_changed" | "ticket.service_changed" | "ticket.category_changed":
            return ("Updated ticket details", None) if internal else None
        case "step.added":
            return (f"Added step: {new.get('description')}", None) if internal else None
        case "step.completed":
            return f"Completed: {meta.get('description')}", (meta.get("note") if internal else None)
        case "step.status_changed":
            return (f"Marked “{meta.get('description')}” as {str(new.get('value')).replace('_', ' ')}", None) if internal else None
        case "step.edited":
            return (f"Edited step: {new.get('description') or old.get('description') or ''}".strip(), None) if internal else None
        case "step.note_added":
            return (f"Added a note on “{new.get('description')}”", new.get("note")) if internal else None
        case "step.deleted":
            return (f"Removed step: {old.get('description')}", None) if internal else None
        case "step.reordered":
            return ("Reordered the resolution plan", None) if internal else None
        case "step.restored":
            return ("Restored AI-suggested steps", None) if internal else None
        case "comment.added":
            if new.get("visibility") == "internal":
                return ("Added an internal note", None) if internal else None
            if new.get("kind") == "question":
                return "Asked the requester for more information", None
            return "Posted a message", None
        case "attachment.added":
            return f"Attached {new.get('file_name')}", None
        case "ticket.escalated":
            team = meta.get("to_team_name")
            if internal:
                return f"Escalated to {team} (L2) · {meta.get('reason_label', '')}".strip(" ·"), meta.get("note")
            return "Escalated to a specialist team", None
        case "ticket.resolved":
            return "Resolved", (new.get("summary") if internal else None)
        case "ticket.reopened":
            return "Reopened", meta.get("reason")
        case "ticket.closed":
            return ("Closed — confirmed fixed by requester" if meta.get("confirmed_by_requester") else "Closed"), None
    return None
