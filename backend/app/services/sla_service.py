from __future__ import annotations

from datetime import datetime

from app.domain.enums import DONE_STATUSES, TicketStatus
from app.domain.sla import SlaSnapshot, compute_targets, snapshot
from app.models import SlaPolicy, Ticket
from app.repositories.settings_repository import SettingsRepository
from app.services.base import utcnow


class SlaService:
    def __init__(self, repo: SettingsRepository, *, due_soon_minutes: int = 60) -> None:
        self.repo = repo
        self.due_soon_minutes = due_soon_minutes
        self._policies: dict[str, SlaPolicy | None] = {}

    async def policy_for(self, priority: str) -> SlaPolicy | None:
        if priority not in self._policies:
            self._policies[priority] = await self.repo.active_sla_policy(priority)
        return self._policies[priority]

    async def apply(self, ticket: Ticket, *, start: datetime | None = None) -> None:
        """(Re)compute due dates from `start` (defaults to ticket creation)."""
        policy = await self.policy_for(ticket.priority)
        if policy is None:
            ticket.sla_policy_id = None
            ticket.sla_response_due_at = None
            ticket.sla_due_at = None
            return
        begin = start or ticket.created_at or utcnow()
        targets = compute_targets(
            begin, response_minutes=policy.response_time_minutes, resolution_minutes=policy.resolution_time_minutes
        )
        ticket.sla_policy_id = policy.id
        ticket.sla_response_due_at = targets.response_due_at
        ticket.sla_due_at = targets.resolution_due_at

    def snapshot(self, ticket: Ticket, *, now: datetime | None = None) -> SlaSnapshot:
        resolved_at = ticket.resolved_at if TicketStatus(ticket.status) in DONE_STATUSES else None
        return snapshot(
            due_at=ticket.sla_due_at,
            window_start=ticket.created_at,
            now=now or utcnow(),
            resolved_at=resolved_at,
            due_soon_minutes=self.due_soon_minutes,
        )
