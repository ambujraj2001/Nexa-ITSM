"""Resolution planning, resolution drafts, employee summaries and L2 handoff briefs."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.agents import prompts
from app.agents.guardrails import clean_list, contains_execution_claim, neutralise_execution_claims, strip_reasoning
from app.agents.runner import build_agent, run_agent
from app.agents.schemas import DiagnosisReport, EmployeeResolutionSummary, HandoffBrief, PlanStep, ResolutionDraft, ResolutionPlan
from app.agents.tools import ToolContext, resolution_tools
from app.container import Container
from app.core.logging import get_logger
from app.domain.enums import ActorType, CommentKind, CommentVisibility, StepStatus
from app.models import Ticket, TicketComment
from app.repositories.knowledge_repository import IncidentHit, KnowledgeHit
from app.schemas.tickets import ResolutionDraftView
from app.services.audit_service import AuditService
from app.services.base import Repos, Service, utcnow
from app.utils.text import truncate

log = get_logger(__name__)
MAX_PLAN_STEPS = 8


def sanitize_plan(steps: Sequence[PlanStep]) -> list[PlanStep]:
    """Engineer-facing, deduplicated steps; no step may claim work was done."""
    seen: set[str] = set()
    out: list[PlanStep] = []
    for step in steps:
        if contains_execution_claim(step.description):
            continue  # a step reporting work as done isn't a step an engineer can take
        description = (strip_reasoning(step.description) or "").strip().rstrip(".")
        if not description:
            continue
        key_text = description.lower()
        if key_text in seen:
            continue
        seen.add(key_text)
        out.append(
            PlanStep(
                description=description[:120],
                details=neutralise_execution_claims(step.details),
                technical_details=strip_reasoning(step.technical_details),
            )
        )
        if len(out) >= MAX_PLAN_STEPS:
            break
    return out


async def _ticket_context(repos: Repos, ticket: Ticket, *, include_notes: bool = True) -> str:
    analysis = await repos.tickets.get_analysis(ticket.id)
    steps = await repos.tickets.list_steps(ticket.id)
    lines = [
        f"Ticket {ticket.ticket_number}: {ticket.title} ({ticket.priority}, {ticket.category or 'uncategorised'}"
        + (f" / {ticket.subcategory}" if ticket.subcategory else "") + ")",
        f'Requester\'s words: """{truncate(ticket.description, 2000)}"""',
    ]
    if analysis and analysis.diagnosis:
        lines.append(f"AI diagnosis (unconfirmed): {analysis.diagnosis}")
    if steps:
        lines.append("Resolution steps:")
        for s in steps:
            marker = {"completed": "✓", "skipped": "–", "in_progress": "…"}.get(s.status, "○")
            lines.append(f"  {marker} {s.description} [{s.status}]" + (f" — note: {truncate(s.notes, 300)}" if s.notes else ""))
    if include_notes:
        comments = await repos.tickets.list_comments(ticket.id, include_internal=True)
        if comments:
            lines.append("Notes and messages:")
            lines += [f"  - ({c.visibility}) {truncate(c.content, 400)}" for c in comments[-10:]]
    return "\n".join(lines)


class ResolutionService(Service):
    def __init__(self, repos: Repos, container: Container) -> None:
        super().__init__(repos, container)
        self.audit = AuditService(repos.audit)

    async def plan(self, ticket: Ticket, *, report: DiagnosisReport | None, knowledge: Sequence[KnowledgeHit], incidents: Sequence[IncidentHit]) -> tuple[list[PlanStep], str | None]:
        ctx = ToolContext(repos=self.repos, container=self.container, ticket_id=ticket.id, requester_id=ticket.requester_id)
        model_alias = self.settings.model_for_task("resolution_plan") or None
        articles = []
        for hit in knowledge[:2]:
            article = await self.repos.knowledge.get(hit.article_id)
            if article:
                articles.append(f"{article.article_number} “{article.title}”:\n{truncate(article.content, 2500)}")
        brief = [
            f"Ticket {ticket.ticket_number}: {ticket.title}",
            f'Requester\'s words: """{truncate(ticket.description, 2000)}"""',
        ]
        if report:
            brief.append(f"Diagnosis (unconfirmed, confidence {report.confidence:.2f}): {report.diagnosis}")
            if report.hypotheses:
                brief.append("Alternatives: " + "; ".join(f"{h.cause} (verify: {h.how_to_verify})" for h in report.hypotheses))
        if articles:
            brief.append("Relevant procedures:\n" + "\n\n".join(articles))
        if incidents:
            brief.append("How similar incidents were resolved:\n" + "\n".join(f"- {h.ticket_number}: {truncate(h.resolution_summary, 300)}" for h in incidents[:3]))
        agent = build_agent(
            model=self.container.chat_model("resolution_plan", ticket_id=str(ticket.id)),
            tools=resolution_tools(ctx),
            system_prompt=prompts.RESOLUTION_PLAN,
            response_format=ResolutionPlan,
            name="nexa-resolution-planner",
        )
        result = await run_agent(
            agent,
            messages=[{"role": "user", "content": "\n\n".join(brief) + "\n\nReturn the ResolutionPlan."}],
            schema=ResolutionPlan,
            audit=self.repos.audit,
            agent_name="nexa-resolution-planner",
            operation="resolution_plan",
            model_label=model_alias,
            ticket_id=ticket.id,
            tool_calls_counter=ctx,
            timeout_seconds=min(270.0, float(self.settings.investigation_timeout_seconds)),
        )
        return sanitize_plan(result.output.steps), model_alias

    async def draft_resolution(self, ticket: Ticket) -> ResolutionDraftView:
        """AI-drafted resolution record the engineer edits before resolving."""
        context = await _ticket_context(self.repos, ticket)
        try:
            draft, _ = await self.container.llm.structured(
                "summary",
                [{"role": "system", "content": prompts.RESOLUTION_DRAFT}, {"role": "user", "content": context}],
                ResolutionDraft,
                temperature=0.2,
                max_tokens=700,
                metadata={"ticket_id": str(ticket.id)},
            )
        except Exception as exc:  # noqa: BLE001 — fall back to a factual template
            log.warning("ai.resolution_draft_failed", error=type(exc).__name__)
            steps = await self.repos.tickets.list_steps(ticket.id)
            done = [s.description for s in steps if s.status == StepStatus.COMPLETED.value]
            summary = "Completed: " + "; ".join(done) + "." if done else ""
            return ResolutionDraftView(resolution_summary=summary, employee_summary="", generated=False)
        return ResolutionDraftView(
            resolution_summary=neutralise_execution_claims(draft.resolution_summary) or "",
            employee_summary=neutralise_execution_claims(draft.employee_summary) or "",
        )

    async def summarize_for_employee(self, ticket: Ticket) -> None:
        if not ticket.resolution_summary or ticket.resolution_ai_summary:
            return
        steps = await self.repos.tickets.list_steps(ticket.id)
        done = [s.description for s in steps if s.status == StepStatus.COMPLETED.value]
        content = f"Problem: {truncate(ticket.description, 800)}\nEngineer's resolution note: {ticket.resolution_summary}\nCompleted steps: {'; '.join(done) or 'none recorded'}"
        summary, info = await self.container.llm.structured(
            "summary",
            [{"role": "system", "content": prompts.EMPLOYEE_SUMMARY}, {"role": "user", "content": content}],
            EmployeeResolutionSummary,
            temperature=0.2,
            max_tokens=300,
            metadata={"ticket_id": str(ticket.id)},
        )
        ticket.resolution_ai_summary = neutralise_execution_claims(summary.employee_summary)
        await self.audit.record("ai.resolution_summary_generated", actor_type=ActorType.AI, ticket_id=ticket.id, metadata={"model": info.model})
        await self.commit()

    async def handoff_brief(self, ticket: Ticket) -> None:
        context = await _ticket_context(self.repos, ticket)
        brief, info = await self.container.llm.structured(
            "escalation_analysis",
            [{"role": "system", "content": prompts.HANDOFF}, {"role": "user", "content": context}],
            HandoffBrief,
            temperature=0.1,
            max_tokens=900,
            metadata={"ticket_id": str(ticket.id)},
        )
        payload = {
            "summary": neutralise_execution_claims(brief.summary),
            "completed_checks": clean_list(brief.completed_checks, limit=8),
            "ruled_out": clean_list(brief.ruled_out, limit=6),
            "open_questions": clean_list(brief.open_questions, limit=6),
            "suggested_next": clean_list(brief.suggested_next, limit=6),
            "generated_at": utcnow().isoformat(),
        }
        await self.repos.tickets.upsert_analysis(ticket.id, handoff_summary=payload)
        await self.repos.tickets.add_comment(
            TicketComment(
                ticket_id=ticket.id, author_id=None, author_type=ActorType.AI.value, content=payload["summary"] or "Handoff brief prepared.",
                visibility=CommentVisibility.INTERNAL.value, kind=CommentKind.HANDOFF_SUMMARY.value,
            )
        )
        await self.audit.record("ai.handoff_generated", actor_type=ActorType.AI, ticket_id=ticket.id, metadata={"model": info.model})
        await self.commit()


async def schedule_post_resolution(container: Container, ticket_id: uuid.UUID) -> None:
    async def job() -> None:
        from app.services.knowledge_service import KnowledgeService

        async with container.db.session() as session:
            repos = Repos.for_session(session)
            ticket = await repos.tickets.get(ticket_id)
            if ticket is None:
                return
            if container.ai_available:
                try:
                    await ResolutionService(repos, container).summarize_for_employee(ticket)
                except Exception as exc:  # noqa: BLE001 — employee still sees the engineer's note
                    await session.rollback()
                    log.warning("ai.employee_summary_failed", error=type(exc).__name__)
            await KnowledgeService(repos, container).index_resolved_ticket(ticket_id)

    await container.jobs.spawn(f"post-resolution-{ticket_id}", job)


async def schedule_handoff_brief(container: Container, ticket_id: uuid.UUID) -> None:
    async def job() -> None:
        async with container.db.session() as session:
            repos = Repos.for_session(session)
            ticket = await repos.tickets.get(ticket_id)
            if ticket is None:
                return
            try:
                await ResolutionService(repos, container).handoff_brief(ticket)
            except Exception as exc:  # noqa: BLE001 — L2 still has the full ticket history
                await session.rollback()
                log.warning("ai.handoff_failed", error=type(exc).__name__)

    await container.jobs.spawn(f"handoff-{ticket_id}", job)

