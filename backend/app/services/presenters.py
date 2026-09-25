"""Turn ORM rows into role-appropriate API views.

Engineers get the full investigation context; employees get status, people,
progress and resolution — never evidence (which can reference other people's
incidents), technical commands or internal notes.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from app.domain import policies
from app.domain.enums import (
    AI_STAGE_LABELS,
    AI_STAGE_ORDER,
    ESCALATION_REASON_LABELS,
    STATUS_LABELS,
    TICKET_TYPE_LABELS,
    AIStage,
    AIStatus,
    EscalationReason,
    StepStatus,
    TicketStatus,
    TicketType,
    WAITING_ON_ENGINEER,
)
from app.domain.policies import Principal, TicketFacts
from app.models import Profile, ResolutionStep, Service, Team, Ticket, TicketAiAnalysis
from app.schemas.common import PersonRef, ServiceRef, SlaInfo, TeamRef
from app.schemas.tickets import (
    AnalysisView,
    EmployeeStepView,
    EmployeeTicketDetail,
    EscalationInfo,
    EvidenceView,
    HandoffView,
    HypothesisView,
    ProgressStage,
    ProgressView,
    ResolutionView,
    SignalView,
    StepView,
    TicketDetail,
    TicketPermissions,
    TicketSummary,
)
from app.services.base import Repos
from app.services.sla_service import SlaService


def confidence_label(confidence: float | Decimal | None) -> str | None:
    if confidence is None:
        return None
    value = float(confidence)
    if value >= 0.75:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


def person_ref(profile: Profile | None, teams: dict[uuid.UUID, Team] | None = None, *, include_email: bool = True) -> PersonRef | None:
    if profile is None:
        return None
    team = (teams or {}).get(profile.team_id) if profile.team_id else None
    return PersonRef(
        id=profile.id,
        name=profile.name,
        email=profile.email if include_email else None,
        avatar_url=profile.avatar_url,
        job_title=profile.job_title,
        department=profile.department,
        location=profile.location,
        role=profile.role,
        engineer_level=profile.engineer_level,
        team_name=team.name if team else None,
    )


def team_ref(team: Team | None) -> TeamRef | None:
    return TeamRef(id=team.id, name=team.name) if team else None


def service_ref(service: Service | None) -> ServiceRef | None:
    return ServiceRef(id=service.id, name=service.name, criticality=service.criticality) if service else None


def facts(ticket: Ticket, *, previously_assigned: bool = False) -> TicketFacts:
    return TicketFacts(
        id=ticket.id,
        requester_id=ticket.requester_id,
        assigned_to=ticket.assigned_to,
        assignment_team_id=ticket.assignment_team_id,
        status=TicketStatus(ticket.status),
        previously_assigned=previously_assigned,
    )


def permissions_for(p: Principal, ticket: Ticket, *, previously_assigned: bool, ai_available: bool) -> TicketPermissions:
    f = facts(ticket, previously_assigned=previously_assigned)
    can_work = policies.can_work_ticket(p, f)
    return TicketPermissions(
        can_work=can_work,
        can_self_assign=policies.can_self_assign(p, f),
        can_reassign=policies.can_reassign(p, f),
        can_escalate=can_work,
        can_resolve=can_work,
        can_reopen=policies.can_reopen(p, f),
        can_close=policies.can_close(p, f),
        can_comment_internal=policies.can_view_internal(p, f),
        can_reply=policies.can_view_ticket(p, f) and TicketStatus(ticket.status) != TicketStatus.CLOSED,
        can_retry_ai=can_work and ai_available and ticket.ai_status in (AIStatus.FAILED.value, AIStatus.SKIPPED.value),
    )


def progress_view(ticket: Ticket, *, team: Team | None = None, assignee: Profile | None = None) -> ProgressView:
    status = AIStatus(ticket.ai_status)
    current = AIStage(ticket.ai_stage) if ticket.ai_stage else None
    stages: list[ProgressStage] = []
    current_index = AI_STAGE_ORDER.index(current) if current else -1
    for index, stage in enumerate(AI_STAGE_ORDER[:-1]):
        if status == AIStatus.COMPLETED:
            state = "done"
        elif status == AIStatus.SKIPPED:
            state = "skipped"
        elif status == AIStatus.FAILED:
            state = "done" if index < current_index else ("failed" if index == current_index else "pending")
        elif status == AIStatus.RUNNING:
            state = "done" if index < current_index else ("active" if index == current_index else "pending")
        else:
            state = "pending"
        stages.append(ProgressStage(key=stage.value, label=AI_STAGE_LABELS[stage], state=state))  # type: ignore[arg-type]
    return ProgressView(
        ticket_id=ticket.id,
        ticket_number=ticket.ticket_number,
        status=ticket.status,
        ai_status=ticket.ai_status,
        ai_stage=ticket.ai_stage,
        stages=stages,
        error=ticket.ai_error,
        team=team_ref(team),
        assignee=person_ref(assignee, include_email=False),
    )


def analysis_view(analysis: TicketAiAnalysis | None, *, threshold: float, teams: dict[uuid.UUID, Team]) -> AnalysisView | None:
    if analysis is None:
        return None
    confidence = float(analysis.confidence) if analysis.confidence is not None else None
    handoff = None
    if analysis.handoff_summary:
        try:
            handoff = HandoffView.model_validate(analysis.handoff_summary)
        except ValueError:
            handoff = None
    return AnalysisView(
        category=analysis.category,
        subcategory=analysis.subcategory,
        priority=analysis.priority,
        summary=analysis.summary,
        diagnosis=analysis.diagnosis,
        confidence=confidence,
        confidence_label=confidence_label(confidence),  # type: ignore[arg-type]
        below_threshold=confidence is not None and confidence < threshold,
        rationale=analysis.rationale,
        evidence=[EvidenceView.model_validate(e) for e in analysis.evidence or [] if isinstance(e, dict) and e.get("summary")],
        hypotheses=[HypothesisView.model_validate(h) for h in analysis.hypotheses or [] if isinstance(h, dict) and h.get("cause")],
        signals=[SignalView.model_validate(s) for s in analysis.signals or [] if isinstance(s, dict) and s.get("value")],
        missing_information=[str(m) for m in analysis.missing_information or []],
        recommended_team=team_ref(teams.get(analysis.recommended_team_id)) if analysis.recommended_team_id else None,
        handoff=handoff,
        updated_at=analysis.updated_at,
    )


def current_step_id(steps: Sequence[ResolutionStep]) -> uuid.UUID | None:
    for step in steps:
        if step.status in (StepStatus.IN_PROGRESS.value,):
            return step.id
    for step in steps:
        if step.status == StepStatus.PENDING.value:
            return step.id
    return None


class TicketPresenter:
    def __init__(self, repos: Repos, sla: SlaService, principal: Principal, *, ai_threshold: float = 0.8, ai_available: bool = True) -> None:
        self.repos = repos
        self.sla = sla
        self.principal = principal
        self.ai_threshold = ai_threshold
        self.ai_available = ai_available

    def _sla(self, ticket: Ticket, policy_names: dict[uuid.UUID, str] | None = None) -> SlaInfo:
        snap = self.sla.snapshot(ticket)
        return SlaInfo(
            state=snap.state.value,  # type: ignore[arg-type]
            label=snap.label,
            due_at=snap.due_at,
            response_due_at=ticket.sla_response_due_at,
            remaining_seconds=snap.remaining_seconds,
            policy_name=(policy_names or {}).get(ticket.sla_policy_id) if ticket.sla_policy_id else None,
        )

    async def summaries(self, tickets: Sequence[Ticket]) -> list[TicketSummary]:
        if not tickets:
            return []
        people = await self.repos.users.get_many([t.requester_id for t in tickets] + [t.assigned_to for t in tickets])
        teams = await self.repos.users.teams_by_ids([t.assignment_team_id for t in tickets] + [p.team_id for p in people.values()])
        analyses = await self.repos.tickets.analyses_for([t.id for t in tickets])
        progress = await self.repos.tickets.step_progress([t.id for t in tickets])
        staff = self.principal.is_staff
        out: list[TicketSummary] = []
        for t in tickets:
            analysis = analyses.get(t.id)
            done, total = progress.get(t.id, (0, 0))
            out.append(
                TicketSummary(
                    id=t.id,
                    ticket_number=t.ticket_number,
                    title=t.title,
                    ticket_type=t.ticket_type,
                    type_label=TICKET_TYPE_LABELS[TicketType(t.ticket_type)],
                    priority=t.priority,
                    status=t.status,
                    status_label=STATUS_LABELS[TicketStatus(t.status)],
                    category=t.category,
                    subcategory=t.subcategory,
                    requester=person_ref(people.get(t.requester_id), teams, include_email=staff)
                    or PersonRef(id=t.requester_id, name="Unknown requester"),
                    assignee=person_ref(people.get(t.assigned_to), teams, include_email=staff) if t.assigned_to else None,
                    team=team_ref(teams.get(t.assignment_team_id)) if t.assignment_team_id else None,
                    support_level=t.support_level,
                    sla=self._sla(t),
                    ai_status=t.ai_status,
                    ai_headline=(analysis.diagnosis or analysis.summary) if analysis else None,
                    summary=analysis.summary if analysis else None,
                    steps_done=done,
                    steps_total=total,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                    resolved_at=t.resolved_at,
                )
            )
        return out

    async def _escalation(self, ticket: Ticket, people: dict[uuid.UUID, Profile], teams: dict[uuid.UUID, Team]) -> EscalationInfo | None:
        if ticket.escalation_count == 0:
            return None
        events = await self.repos.audit.for_ticket(ticket.id, actions=["ticket.escalated"])
        if not events:
            return None
        last = events[-1]
        meta = last.metadata_ or {}
        from_id = last.actor_id
        extra_people = await self.repos.users.get_many([from_id])
        to_team_id = meta.get("to_team_id")
        to_team = teams.get(uuid.UUID(to_team_id)) if to_team_id else None
        if to_team is None and to_team_id:
            to_team = await self.repos.users.get_team(uuid.UUID(to_team_id))
        reason = meta.get("reason", EscalationReason.OTHER.value)
        try:
            reason_label = ESCALATION_REASON_LABELS[EscalationReason(reason)]
        except ValueError:
            reason_label = str(reason)
        return EscalationInfo(
            escalated_at=last.created_at,
            from_person=person_ref(extra_people.get(from_id) or people.get(from_id), teams, include_email=False),
            to_team=team_ref(to_team),
            reason=reason,
            reason_label=reason_label,
            note=meta.get("note"),
        )

    async def detail(self, ticket: Ticket) -> TicketDetail:
        [summary] = await self.summaries([ticket])
        analysis = await self.repos.tickets.get_analysis(ticket.id)
        steps = await self.repos.tickets.list_steps(ticket.id)
        people = await self.repos.users.get_many(
            [ticket.requester_id, ticket.assigned_to, ticket.resolved_by]
            + [s.created_by for s in steps]
            + [s.completed_by for s in steps]
        )
        teams = await self.repos.users.teams_by_ids(
            [ticket.assignment_team_id, ticket.ai_recommended_team_id, analysis.recommended_team_id if analysis else None]
            + [p.team_id for p in people.values()]
        )
        service = await self.repos.settings.get_service(ticket.service_id) if ticket.service_id else None
        previously = await self.repos.tickets.was_assigned(ticket.id, self.principal.profile_id)
        current = current_step_id(steps)
        resolution = None
        if ticket.resolved_at or ticket.resolution_summary:
            resolution = ResolutionView(
                summary=ticket.resolution_summary,
                employee_summary=ticket.resolution_ai_summary,
                code=ticket.resolution_code,
                resolved_by=person_ref(people.get(ticket.resolved_by), teams, include_email=False),
                resolved_at=ticket.resolved_at,
                completed_steps=[s.description for s in steps if s.status == StepStatus.COMPLETED.value],
            )
        return TicketDetail(
            **summary.model_dump(),
            description=ticket.description,
            impact=ticket.impact,
            urgency=ticket.urgency,
            source=ticket.source,
            service=service_ref(service),
            sla_response_due_at=ticket.sla_response_due_at,
            first_response_at=ticket.first_response_at,
            ai_error=ticket.ai_error,
            ai_stage=ticket.ai_stage,
            ai_recommended_team=team_ref(teams.get(ticket.ai_recommended_team_id)) if ticket.ai_recommended_team_id else None,
            assignment_reason=ticket.assignment_reason,
            analysis=analysis_view(analysis, threshold=self.ai_threshold, teams=teams),
            steps=[
                StepView(
                    id=s.id,
                    position=s.position,
                    description=s.description,
                    details=s.details,
                    technical_details=s.technical_details,
                    status=s.status,
                    source=s.source,
                    edited=s.edited,
                    notes=s.notes,
                    created_by=person_ref(people.get(s.created_by), teams, include_email=False) if s.created_by else None,
                    completed_by=person_ref(people.get(s.completed_by), teams, include_email=False) if s.completed_by else None,
                    completed_at=s.completed_at,
                    updated_at=s.updated_at,
                    is_current=s.id == current,
                )
                for s in steps
            ],
            escalation=await self._escalation(ticket, people, teams),
            resolution=resolution,
            permissions=permissions_for(self.principal, ticket, previously_assigned=previously, ai_available=self.ai_available),
            escalation_count=ticket.escalation_count,
            reopen_count=ticket.reopen_count,
        )

    async def employee_detail(self, ticket: Ticket) -> EmployeeTicketDetail:
        analysis = await self.repos.tickets.get_analysis(ticket.id)
        steps = await self.repos.tickets.list_steps(ticket.id)
        people = await self.repos.users.get_many([ticket.assigned_to, ticket.resolved_by])
        teams = await self.repos.users.teams_by_ids([ticket.assignment_team_id] + [p.team_id for p in people.values()])
        status = TicketStatus(ticket.status)
        waiting_on = "you" if status == TicketStatus.PENDING_USER else ("it_team" if status in WAITING_ON_ENGINEER else None)
        visible_steps = [s for s in steps if s.status != StepStatus.SKIPPED.value]
        resolution = None
        if ticket.resolved_at:
            resolution = ResolutionView(
                summary=ticket.resolution_ai_summary or ticket.resolution_summary,
                employee_summary=ticket.resolution_ai_summary,
                code=ticket.resolution_code,
                resolved_by=person_ref(people.get(ticket.resolved_by), teams, include_email=False),
                resolved_at=ticket.resolved_at,
                completed_steps=[s.description for s in steps if s.status == StepStatus.COMPLETED.value],
            )
        return EmployeeTicketDetail(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            title=ticket.title,
            description=ticket.description,
            ticket_type=ticket.ticket_type,
            type_label=TICKET_TYPE_LABELS[TicketType(ticket.ticket_type)],
            priority=ticket.priority,
            status=ticket.status,
            status_label=STATUS_LABELS[status],
            category=ticket.category,
            subcategory=ticket.subcategory,
            likely_cause=analysis.diagnosis if analysis else None,
            summary=analysis.summary if analysis else None,
            assignee=person_ref(people.get(ticket.assigned_to), teams, include_email=False) if ticket.assigned_to else None,
            team=team_ref(teams.get(ticket.assignment_team_id)) if ticket.assignment_team_id else None,
            ai_status=ticket.ai_status,
            waiting_on=waiting_on,  # type: ignore[arg-type]
            steps=[EmployeeStepView(id=s.id, position=s.position, description=s.description, status=s.status, completed_at=s.completed_at) for s in visible_steps],
            steps_done=sum(1 for s in visible_steps if s.status == StepStatus.COMPLETED.value),
            steps_total=len(visible_steps),
            resolution=resolution,
            permissions=permissions_for(self.principal, ticket, previously_assigned=False, ai_available=False),
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            resolved_at=ticket.resolved_at,
        )

    def progress(self, ticket: Ticket, *, team: Team | None, assignee: Profile | None) -> ProgressView:
        return progress_view(ticket, team=team, assignee=assignee)


def stage_label(stage: AIStage) -> str:
    return AI_STAGE_LABELS[stage]
