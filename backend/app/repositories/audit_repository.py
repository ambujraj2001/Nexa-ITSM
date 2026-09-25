from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, AuditEvent, Ticket


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, event: AuditEvent) -> AuditEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def for_ticket(self, ticket_id: uuid.UUID, *, actions: Sequence[str] | None = None) -> Sequence[AuditEvent]:
        stmt = select(AuditEvent).where(AuditEvent.ticket_id == ticket_id)
        if actions:
            stmt = stmt.where(AuditEvent.action.in_(actions))
        return (await self.session.execute(stmt.order_by(AuditEvent.created_at, AuditEvent.id))).scalars().all()

    async def search(
        self,
        *,
        entity_type: str | None = None,
        actor_type: str | None = None,
        action_prefix: str | None = None,
        ticket_id: uuid.UUID | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> Sequence[AuditEvent]:
        stmt = select(AuditEvent)
        if entity_type:
            stmt = stmt.where(AuditEvent.entity_type == entity_type)
        if actor_type:
            stmt = stmt.where(AuditEvent.actor_type == actor_type)
        if action_prefix:
            stmt = stmt.where(AuditEvent.action.startswith(action_prefix))
        if ticket_id:
            stmt = stmt.where(AuditEvent.ticket_id == ticket_id)
        if before:
            stmt = stmt.where(AuditEvent.created_at < before)
        return (await self.session.execute(stmt.order_by(AuditEvent.created_at.desc()).limit(limit))).scalars().all()

    async def notifications_for(self, profile_id: uuid.UUID, *, since: datetime | None, limit: int = 30) -> Sequence[AuditEvent]:
        """Events on tickets the user requested or is assigned to, excluding their own actions."""
        involved = select(Ticket.id).where(or_(Ticket.requester_id == profile_id, Ticket.assigned_to == profile_id))
        stmt = (
            select(AuditEvent)
            .where(
                AuditEvent.ticket_id.in_(involved),
                or_(AuditEvent.actor_id.is_(None), AuditEvent.actor_id != profile_id),
                AuditEvent.action.in_(
                    [
                        "ticket.created",
                        "ticket.assigned",
                        "ticket.status_changed",
                        "ticket.escalated",
                        "ticket.resolved",
                        "ticket.reopened",
                        "ticket.closed",
                        "comment.added",
                        "ai.analysis_generated",
                    ]
                ),
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def unread_count(self, profile_id: uuid.UUID, since: datetime | None) -> int:
        involved = select(Ticket.id).where(or_(Ticket.requester_id == profile_id, Ticket.assigned_to == profile_id))
        stmt = select(func.count()).where(
            AuditEvent.ticket_id.in_(involved),
            or_(AuditEvent.actor_id.is_(None), AuditEvent.actor_id != profile_id),
            AuditEvent.action.in_(["ticket.assigned", "ticket.escalated", "ticket.resolved", "ticket.reopened", "comment.added", "ticket.status_changed"]),
        )
        if since:
            stmt = stmt.where(AuditEvent.created_at > since)
        return int((await self.session.execute(stmt)).scalar() or 0)

    # ── agent runs ───────────────────────────────────────────────────────
    async def add_run(self, run: AgentRun) -> AgentRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def runs_for_ticket(self, ticket_id: uuid.UUID) -> Sequence[AgentRun]:
        stmt = select(AgentRun).where(AgentRun.ticket_id == ticket_id).order_by(AgentRun.started_at)
        return (await self.session.execute(stmt)).scalars().all()
