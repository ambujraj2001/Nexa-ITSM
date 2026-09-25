"""The AI investigation pipeline for a new ticket.

    understanding → knowledge → similar incidents → diagnosis → planning → assignment

Runs as a background job so ticket creation returns immediately; each stage
commits `ai_stage` so the UI can show progress (stages, never reasoning).
AI stages are optional (per AI settings) and failure-tolerant: if any AI stage
fails, the ticket is still routed by deterministic rules and marked
"AI investigation failed — continue manually". A ticket is never left stuck.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

from app.agents.schemas import TriageResult
from app.container import Container
from app.core.logging import get_logger
from app.domain.enums import AIStage, AIStatus, ActorType, StepSource, StepStatus, TicketStatus
from app.domain.priority import determine_priority
from app.domain.state_machine import can_transition
from app.domain.taxonomy import normalize_category
from app.infrastructure.telemetry import span
from app.models import ResolutionStep, Ticket
from app.services.assignment_service import AssignmentService
from app.services.audit_service import AuditService
from app.services.base import Repos, Service, utcnow
from app.services.diagnosis_service import DiagnosisService
from app.services.knowledge_service import KnowledgeService
from app.services.resolution_service import ResolutionService
from app.services.sla_service import SlaService
from app.services.triage_service import TriageService

log = get_logger(__name__)

FAILURE_MESSAGE = "AI investigation failed. You can continue manually."


async def schedule_investigation(container: Container, ticket_id: uuid.UUID) -> None:
    timeout = container.settings.investigation_timeout_seconds

    async def job() -> None:
        async with container.locks.hold(f"investigation:{ticket_id}", ttl_seconds=timeout + 120) as acquired:
            if not acquired:
                log.info("investigation.already_running", ticket_id=str(ticket_id))
                return
            async with container.db.session() as session:
                await InvestigationService(Repos.for_session(session), container).run(ticket_id)

    await container.jobs.spawn(f"investigation-{ticket_id}", job)


class InvestigationService(Service):
    def __init__(self, repos: Repos, container: Container) -> None:
        super().__init__(repos, container)
        self.audit = AuditService(repos.audit)
        self.assignment = AssignmentService(repos, self.audit)
        self.sla = SlaService(repos.settings, due_soon_minutes=container.settings.due_soon_minutes)

    async def _stage(self, ticket: Ticket, stage: AIStage) -> None:
        ticket.ai_stage = stage.value
        await self.commit()

    async def run(self, ticket_id: uuid.UUID) -> None:
        ticket = await self.repos.tickets.get(ticket_id)
        if ticket is None or ticket.ai_status not in (AIStatus.PENDING.value, AIStatus.RUNNING.value, AIStatus.FAILED.value):
            return
        with span("investigation.run", **{"nexa.ticket_id": str(ticket.id), "nexa.ticket_number": ticket.ticket_number}) as current:
            ticket.ai_status = AIStatus.RUNNING.value
            ticket.ai_error = None
            await self._stage(ticket, AIStage.UNDERSTANDING)
            try:
                await asyncio.wait_for(self._pipeline(ticket), timeout=self.settings.investigation_timeout_seconds)
                current.set_attribute("nexa.investigation.status", "completed")
            except Exception as exc:  # noqa: BLE001 — any AI failure degrades to manual work
                current.set_attribute("nexa.investigation.status", "failed")
                current.set_attribute("nexa.investigation.error", type(exc).__name__)
                log.warning("investigation.failed", ticket_id=str(ticket_id), stage=ticket.ai_stage, error=type(exc).__name__)
                await self._fail(ticket_id, type(exc).__name__)

    async def _pipeline(self, ticket: Ticket) -> None:
        config = await self.repos.settings.ai_configuration()
        analysis = await self.repos.tickets.get_analysis(ticket.id)

        # 1. Understanding (triage if the ticket didn't come through the assistant)
        if (analysis is None or analysis.triage_model is None) and config.ai_triage_enabled and self.container.ai_available:
            await self._triage(ticket)
            analysis = await self.repos.tickets.get_analysis(ticket.id)

        query = " ".join(filter(None, [ticket.title, ticket.description, analysis.summary if analysis else None]))
        knowledge_service = KnowledgeService(self.repos, self.container)

        # 2–3. Retrieval
        await self._stage(ticket, AIStage.KNOWLEDGE)
        knowledge = await knowledge_service.search_articles(query, limit=5)
        await self._stage(ticket, AIStage.SIMILAR_INCIDENTS)
        incidents = await knowledge_service.search_incidents(query, exclude_ticket_id=ticket.id, limit=5)

        # 4. Diagnosis
        report = None
        ai_team_id = None
        if config.ai_diagnosis_enabled:
            await self._stage(ticket, AIStage.DIAGNOSIS)
            outcome = await DiagnosisService(self.repos, self.container).diagnose(ticket, analysis=analysis, knowledge=knowledge, incidents=incidents)
            report = outcome.report
            ai_team_id = outcome.recommended_team_id
            await self.repos.tickets.upsert_analysis(
                ticket.id,
                summary=report.summary,
                diagnosis=report.diagnosis,
                confidence=report.confidence,
                rationale=report.rationale,
                evidence=outcome.evidence,
                hypotheses=[h.model_dump() for h in report.hypotheses],
                missing_information=report.missing_information,
                recommended_team_id=ai_team_id,
                diagnosis_model=outcome.model,
            )
            ticket.ai_recommended_team_id = ai_team_id
            await self.audit.record(
                "ai.analysis_generated",
                actor_type=ActorType.AI,
                ticket_id=ticket.id,
                new_value={"diagnosis": report.diagnosis, "confidence": report.confidence},
                metadata={"model": outcome.model, "evidence": len(outcome.evidence), "unverified_references_dropped": outcome.dropped_references},
            )
            await self.commit()

        # 5. Resolution plan
        if config.resolution_plans_enabled:
            await self._stage(ticket, AIStage.PLANNING)
            existing = await self.repos.tickets.list_steps(ticket.id)
            if not existing:
                steps, model = await ResolutionService(self.repos, self.container).plan(ticket, report=report, knowledge=knowledge, incidents=incidents)
                for position, step in enumerate(steps):
                    await self.repos.tickets.add_step(
                        ResolutionStep(
                            ticket_id=ticket.id, position=position, description=step.description, details=step.details,
                            technical_details=step.technical_details, status=StepStatus.PENDING.value, source=StepSource.AI.value,
                        )
                    )
                await self.repos.tickets.upsert_analysis(ticket.id, plan_model=model)
                await self.audit.record("ai.plan_generated", actor_type=ActorType.AI, ticket_id=ticket.id, new_value={"steps": len(steps)}, metadata={"model": model})
                await self.commit()

        # 6. Assignment
        await self._stage(ticket, AIStage.ASSIGNMENT)
        await self._ensure_assigned(ticket, ai_team_id=ai_team_id)
        ticket.ai_status = AIStatus.COMPLETED.value
        ticket.ai_stage = AIStage.DONE.value
        await self.commit()

    async def _triage(self, ticket: Ticket) -> None:
        requester = await self.repos.users.get(ticket.requester_id)
        if requester is None:
            return
        result, model = await TriageService(self.repos, self.container).triage(
            [{"role": "user", "content": ticket.description}], requester=requester, open_tickets=[], metadata={"ticket_id": str(ticket.id)}
        )
        await self.apply_triage(ticket, result, model)

    async def apply_triage(self, ticket: Ticket, result: TriageResult, model: str | None) -> None:
        category, subcategory = normalize_category(result.category, result.subcategory)
        service = await self.repos.settings.get_service_by_name(result.service_hint) if result.service_hint else None
        decision = determine_priority(
            impact=result.impact, urgency=result.urgency, ai_suggestion=result.suggested_priority, ticket_type=ticket.ticket_type,
            category=category, service_criticality=service.criticality if service else None,
        )
        old_priority = ticket.priority
        ticket.category, ticket.subcategory = category, subcategory
        ticket.impact, ticket.urgency = result.impact, result.urgency
        if service and ticket.service_id is None:
            ticket.service_id = service.id
        if decision.priority.value != ticket.priority:
            ticket.priority = decision.priority.value
            await self.sla.apply(ticket)
        await self.repos.tickets.upsert_analysis(
            ticket.id, category=category, subcategory=subcategory, priority=ticket.priority, summary=result.summary,
            diagnosis=result.likely_cause, confidence=result.confidence if result.likely_cause else None,
            signals=[s.model_dump() for s in result.signals], triage_model=model,
        )
        await self.audit.record(
            "ai.triage_completed", actor_type=ActorType.AI, ticket_id=ticket.id,
            old_value={"priority": old_priority},
            new_value={"category": category, "subcategory": subcategory, "priority": ticket.priority, "impact": result.impact, "urgency": result.urgency},
            metadata={"model": model, "priority_reason": decision.reason},
        )
        await self.commit()

    async def _ensure_assigned(self, ticket: Ticket, *, ai_team_id: uuid.UUID | None) -> None:
        if ticket.assignment_team_id is None:
            decision = await self.assignment.route(
                category=ticket.category, subcategory=ticket.subcategory, priority=ticket.priority,
                ticket_type=ticket.ticket_type, service_id=ticket.service_id, ai_team_id=ai_team_id,
            )
            await self.assignment.assign(ticket, team_id=decision.team_id, support_level=decision.support_level, reason=decision.reason)
        if TicketStatus(ticket.status) in (TicketStatus.NEW, TicketStatus.TRIAGING) and can_transition(ticket.status, TicketStatus.ASSIGNED):
            old = ticket.status
            ticket.status = TicketStatus.ASSIGNED.value
            await self.audit.record("ticket.status_changed", actor_type=ActorType.SYSTEM, ticket_id=ticket.id, old_value=old, new_value=ticket.status, metadata={"reason": "investigation_complete"})

    async def _fail(self, ticket_id: uuid.UUID, error: str) -> None:
        await self.session.rollback()
        ticket = await self.repos.tickets.get(ticket_id)
        if ticket is None:
            return
        stage = ticket.ai_stage
        ticket.ai_status = AIStatus.FAILED.value
        ticket.ai_error = FAILURE_MESSAGE
        await self.audit.record("ai.investigation_failed", actor_type=ActorType.SYSTEM, ticket_id=ticket.id, metadata={"stage": stage, "error": error})
        await self._ensure_assigned(ticket, ai_team_id=ticket.ai_recommended_team_id)
        await self.commit()

    async def recover_stale(self) -> int:
        """Re-queue investigations orphaned by a crashed/restarted worker."""
        cutoff = utcnow() - timedelta(minutes=self.settings.stale_investigation_minutes)
        stale = await self.repos.tickets.stale_investigations(cutoff)
        for ticket in stale:
            if self.container.ai_available:
                ticket.ai_status = AIStatus.PENDING.value
                await self.commit()
                await schedule_investigation(self.container, ticket.id)
            else:
                await self._fail(ticket.id, "ai_unavailable")
        return len(stale)

