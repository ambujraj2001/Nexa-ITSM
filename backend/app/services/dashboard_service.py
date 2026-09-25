"""Operations Dispatch (engineer) and employee dashboards — all live queries."""

from __future__ import annotations

from app.container import Container
from app.domain.enums import DONE_STATUSES, AIStatus, TicketStatus
from app.domain.policies import Principal
from app.domain.sla import SlaState
from app.infrastructure.cache import key as cache_key
from app.models import Ticket
from app.schemas.misc import AiLine, AttentionItem, AttentionReason, DashboardMetrics, EmployeeDashboard, EngineerDashboard
from app.schemas.tickets import TicketSummary
from app.services.base import Repos, Service, utcnow
from app.services.presenters import TicketPresenter
from app.services.sla_service import SlaService
from app.utils.text import truncate

_CACHE_TTL = 15
_ATTENTION_LIMIT = 6


class DashboardService(Service):
    def __init__(self, repos: Repos, container: Container, principal: Principal) -> None:
        super().__init__(repos, container)
        self.principal = principal
        self.sla = SlaService(repos.settings, due_soon_minutes=container.settings.due_soon_minutes)

    async def _presenter(self) -> tuple[TicketPresenter, float]:
        config = await self.repos.settings.ai_configuration()
        threshold = float(config.confidence_threshold)
        return TicketPresenter(self.repos, self.sla, self.principal, ai_threshold=threshold, ai_available=self.container.ai_available), threshold

    async def engineer(self) -> EngineerDashboard:
        cache_id = cache_key("dashboard", "engineer", self.principal.profile_id)
        cached = await self.container.cache.get(cache_id)
        if cached:
            try:
                return EngineerDashboard.model_validate(cached)
            except ValueError:
                pass

        presenter, threshold = await self._presenter()
        mine = list(await self.repos.tickets.open_assigned_to(self.principal.profile_id))
        summaries = await presenter.summaries(mine)
        by_id = {s.id: s for s in summaries}
        analyses = await self.repos.tickets.analyses_for([t.id for t in mine])

        team_rows = list(await self.repos.tickets.team_unassigned(self.principal.team_id)) if self.principal.team_id else []
        team_queue = await presenter.summaries(team_rows)

        states = {t.id: self.sla.snapshot(t) for t in mine}
        urgent_ids = {t.id for t in mine if t.priority in ("P1", "P2") or states[t.id].state == SlaState.BREACHED}
        at_risk = {t.id for t in mine if states[t.id].state in (SlaState.BREACHED, SlaState.AT_RISK, SlaState.DUE_SOON)}

        attention: list[tuple[tuple, AttentionItem]] = []
        for ticket in mine:
            summary = by_id[ticket.id]
            reasons = self._reasons(ticket, summary, analyses.get(ticket.id), threshold)
            if not reasons:
                continue
            state = states[ticket.id]
            sort_key = (
                0 if state.state == SlaState.BREACHED else 1,
                int(ticket.priority[1]),
                state.remaining_seconds if state.remaining_seconds is not None else 10**9,
            )
            attention.append(
                (
                    sort_key,
                    AttentionItem(
                        ticket=summary,
                        reasons=reasons,
                        ai=self._ai_line(ticket, analyses.get(ticket.id), threshold),
                        action_label="Review" if ticket.status == TicketStatus.PENDING_ENGINEER.value else ("Resume" if ticket.status == TicketStatus.IN_PROGRESS.value else "Open Workspace"),
                    ),
                )
            )
        attention.sort(key=lambda pair: pair[0])

        me = await self.repos.users.get(self.principal.profile_id)
        team = await self.repos.users.get_team(self.principal.team_id) if self.principal.team_id else None
        shift = " · ".join(filter(None, [team.name if team else None, f"{me.engineer_level} Engineer" if me and me.engineer_level else None])) or "IT Operations"

        dashboard = EngineerDashboard(
            metrics=DashboardMetrics(
                assigned_to_me=len(mine),
                urgent=len(urgent_ids),
                urgent_at_risk=len(urgent_ids & at_risk),
                due_soon=sum(1 for s in states.values() if s.state == SlaState.DUE_SOON),
                team_queue=len(team_rows),
            ),
            needs_attention=[item for _, item in attention[:_ATTENTION_LIMIT]],
            my_tickets=sorted(summaries, key=lambda s: (int(s.priority[1]), s.sla.remaining_seconds if s.sla.remaining_seconds is not None else 10**9)),
            team_queue=team_queue,
            shift_label=shift,
            generated_at=utcnow(),
        )
        await self.container.cache.set(cache_id, dashboard.model_dump(mode="json"), ttl_seconds=_CACHE_TTL)
        return dashboard

    @staticmethod
    def _reasons(ticket: Ticket, summary: TicketSummary, analysis, threshold: float) -> list[AttentionReason]:  # type: ignore[no-untyped-def]
        status = TicketStatus(ticket.status)
        sla = summary.sla.state
        reasons: list[AttentionReason] = []
        if sla == "breached":
            reasons.append(AttentionReason(code="sla_breached", label="SLA breached"))
        elif sla == "due_soon":
            reasons.append(AttentionReason(code="sla_due_soon", label=f"SLA: {summary.sla.label}"))
        elif sla == "at_risk":
            reasons.append(AttentionReason(code="sla_at_risk", label="SLA at risk"))
        if status == TicketStatus.PENDING_USER and sla != "breached":
            return []  # the ball is with the requester
        if status == TicketStatus.ESCALATED:
            reasons.append(AttentionReason(code="escalated", label="Escalated to you"))
        elif status == TicketStatus.PENDING_ENGINEER:
            reasons.append(AttentionReason(code="requester_replied", label="Requester replied"))
        elif status == TicketStatus.REOPENED:
            reasons.append(AttentionReason(code="reopened", label="Reopened"))
        elif status in (TicketStatus.ASSIGNED, TicketStatus.NEW, TicketStatus.TRIAGING) and ticket.first_response_at is None:
            reasons.append(AttentionReason(code="new_assignment", label="New assignment"))
        if ticket.ai_status == AIStatus.FAILED.value:
            reasons.append(AttentionReason(code="ai_failed", label="AI investigation failed"))
        elif analysis is not None and analysis.confidence is not None and float(analysis.confidence) < threshold and ticket.ai_status == AIStatus.COMPLETED.value:
            reasons.append(AttentionReason(code="ai_uncertain", label="AI unsure"))
        if ticket.priority == "P1" and not any(r.code.startswith("sla") for r in reasons):
            reasons.append(AttentionReason(code="p1", label="P1 urgent"))
        return reasons

    @staticmethod
    def _ai_line(ticket: Ticket, analysis, threshold: float) -> AiLine:  # type: ignore[no-untyped-def]
        if ticket.ai_status == AIStatus.FAILED.value:
            return AiLine(kind="failed", label="AI investigation failed.", text="Continue manually.")
        if ticket.ai_status in (AIStatus.PENDING.value, AIStatus.RUNNING.value):
            return AiLine(kind="running", label="AI investigation in progress…")
        if ticket.ai_status == AIStatus.SKIPPED.value and not (analysis and analysis.diagnosis):
            return AiLine(kind="disabled", label="No AI investigation for this ticket.")
        if analysis is None or not analysis.diagnosis:
            return AiLine(kind="none", label="No diagnosis yet.")
        confidence = float(analysis.confidence) if analysis.confidence is not None else None
        if confidence is not None and confidence < threshold and analysis.missing_information:
            return AiLine(kind="needs_info", label="AI needs more information:", text=truncate(str(analysis.missing_information[0]), 140))
        if ticket.status == TicketStatus.PENDING_ENGINEER.value:
            return AiLine(kind="plan_ready", label="Resolution plan ready:", text=truncate(analysis.diagnosis, 140))
        return AiLine(kind="diagnosis", label="AI Diagnosis available:", text=truncate(analysis.diagnosis, 140))

    async def employee(self) -> EmployeeDashboard:
        presenter, _ = await self._presenter()
        active_rows = list(await self.repos.tickets.requested_by(self.principal.profile_id, limit=10, open_only=True))
        recent_rows = [t for t in await self.repos.tickets.requested_by(self.principal.profile_id, limit=12) if TicketStatus(t.status) in DONE_STATUSES][:6]
        return EmployeeDashboard(
            active=await presenter.summaries(active_rows),
            recent=await presenter.summaries(recent_rows),
            waiting_on_you=sum(1 for t in active_rows if t.status == TicketStatus.PENDING_USER.value),
            open_count=len(active_rows),
        )
