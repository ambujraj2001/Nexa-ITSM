from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, and_, case, exists, func, literal_column, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OPEN_STATUSES
from app.domain.policies import Principal
from app.models import (
    Attachment,
    ResolutionStep,
    Ticket,
    TicketAiAnalysis,
    TicketAssignment,
    TicketComment,
)

_OPEN = [s.value for s in OPEN_STATUSES]
# Generated tsvector column (not mapped on the ORM model).
_TICKET_TSV = literal_column("tickets.search_vector")
_PRIORITY_RANK = case(
    (Ticket.priority == "P1", 1), (Ticket.priority == "P2", 2), (Ticket.priority == "P3", 3), else_=4
)


@dataclass(frozen=True)
class TicketFilters:
    scope: str = "visible"  # visible | assigned | team | requested
    ticket_type: str | None = None
    statuses: tuple[str, ...] = ()
    priority: str | None = None
    open_only: bool = False
    query: str | None = None
    sort: str = "updated"  # updated | sla | priority | created
    limit: int = 50
    offset: int = 0


class TicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── tickets ──────────────────────────────────────────────────────────
    async def get(self, ticket_id: uuid.UUID, *, for_update: bool = False) -> Ticket | None:
        stmt = select(Ticket).where(Ticket.id == ticket_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_number(self, number: str) -> Ticket | None:
        stmt = select(Ticket).where(func.upper(Ticket.ticket_number) == number.strip().upper())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def resolve_ref(self, ref: str, *, for_update: bool = False) -> Ticket | None:
        try:
            return await self.get(uuid.UUID(ref), for_update=for_update)
        except ValueError:
            ticket = await self.get_by_number(ref)
            if ticket is not None and for_update:
                return await self.get(ticket.id, for_update=True)
            return ticket

    async def add(self, ticket: Ticket) -> Ticket:
        self.session.add(ticket)
        await self.session.flush()
        return ticket

    async def was_assigned(self, ticket_id: uuid.UUID, profile_id: uuid.UUID) -> bool:
        stmt = select(exists().where(TicketAssignment.ticket_id == ticket_id, TicketAssignment.assignee_id == profile_id))
        return bool((await self.session.execute(stmt)).scalar())

    def _visibility(self, p: Principal) -> object:
        if p.is_admin:
            return True
        requested = Ticket.requester_id == p.profile_id
        if not p.is_engineer:
            return requested
        history = exists().where(TicketAssignment.ticket_id == Ticket.id, TicketAssignment.assignee_id == p.profile_id)
        clauses = [requested, Ticket.assigned_to == p.profile_id, history]
        if p.team_id is not None:
            clauses.append(Ticket.assignment_team_id == p.team_id)
        return or_(*clauses)

    def _filtered(self, p: Principal, f: TicketFilters) -> Select[tuple[Ticket]]:
        stmt = select(Ticket)
        visibility = self._visibility(p)
        if visibility is not True:
            stmt = stmt.where(visibility)  # type: ignore[arg-type]
        if f.scope == "assigned":
            stmt = stmt.where(Ticket.assigned_to == p.profile_id)
        elif f.scope == "requested":
            stmt = stmt.where(Ticket.requester_id == p.profile_id)
        elif f.scope == "team":
            stmt = stmt.where(Ticket.assignment_team_id == p.team_id) if p.team_id else stmt.where(False)
        if f.ticket_type:
            stmt = stmt.where(Ticket.ticket_type == f.ticket_type)
        if f.statuses:
            stmt = stmt.where(Ticket.status.in_(f.statuses))
        elif f.open_only:
            stmt = stmt.where(Ticket.status.in_(_OPEN))
        if f.priority:
            stmt = stmt.where(Ticket.priority == f.priority)
        if f.query:
            q = f.query.strip()
            tsq = func.websearch_to_tsquery("english", q)
            stmt = stmt.where(or_(Ticket.ticket_number.ilike(f"%{q}%"), Ticket.title.ilike(f"%{q}%"), _TICKET_TSV.op("@@")(tsq)))
        return stmt

    async def list(self, p: Principal, f: TicketFilters) -> tuple[Sequence[Ticket], int]:
        base = self._filtered(p, f)
        total = int((await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0)
        if f.sort == "sla":
            order = [Ticket.sla_due_at.asc().nulls_last(), _PRIORITY_RANK]
        elif f.sort == "priority":
            order = [_PRIORITY_RANK, Ticket.sla_due_at.asc().nulls_last()]
        elif f.sort == "created":
            order = [Ticket.created_at.desc()]
        else:
            order = [Ticket.updated_at.desc()]
        rows = (await self.session.execute(base.order_by(*order, Ticket.id).limit(f.limit).offset(f.offset))).scalars().all()
        return rows, total

    async def open_assigned_to(self, profile_id: uuid.UUID, limit: int = 100) -> Sequence[Ticket]:
        stmt = (
            select(Ticket)
            .where(Ticket.assigned_to == profile_id, Ticket.status.in_(_OPEN))
            .order_by(_PRIORITY_RANK, Ticket.sla_due_at.asc().nulls_last())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def team_unassigned(self, team_id: uuid.UUID, limit: int = 20) -> Sequence[Ticket]:
        stmt = (
            select(Ticket)
            .where(Ticket.assignment_team_id == team_id, Ticket.assigned_to.is_(None), Ticket.status.in_(_OPEN))
            .order_by(_PRIORITY_RANK, Ticket.sla_due_at.asc().nulls_last())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def requested_by(self, profile_id: uuid.UUID, *, limit: int = 20, open_only: bool = False) -> Sequence[Ticket]:
        stmt = select(Ticket).where(Ticket.requester_id == profile_id)
        if open_only:
            stmt = stmt.where(Ticket.status.in_(_OPEN))
        stmt = stmt.order_by(Ticket.updated_at.desc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()

    async def stale_investigations(self, older_than: datetime) -> Sequence[Ticket]:
        stmt = select(Ticket).where(
            Ticket.ai_status.in_(["pending", "running"]),
            Ticket.status.in_(["new", "triaging"]),
            Ticket.updated_at < older_than,
        )
        return (await self.session.execute(stmt)).scalars().all()

    # ── analysis ─────────────────────────────────────────────────────────
    async def get_analysis(self, ticket_id: uuid.UUID) -> TicketAiAnalysis | None:
        stmt = select(TicketAiAnalysis).where(TicketAiAnalysis.ticket_id == ticket_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def analyses_for(self, ticket_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, TicketAiAnalysis]:
        if not ticket_ids:
            return {}
        stmt = select(TicketAiAnalysis).where(TicketAiAnalysis.ticket_id.in_(ticket_ids))
        return {a.ticket_id: a for a in (await self.session.execute(stmt)).scalars().all()}

    async def upsert_analysis(self, ticket_id: uuid.UUID, **fields: object) -> TicketAiAnalysis:
        analysis = await self.get_analysis(ticket_id)
        if analysis is None:
            analysis = TicketAiAnalysis(ticket_id=ticket_id)
            self.session.add(analysis)
        for key, value in fields.items():
            setattr(analysis, key, value)
        await self.session.flush()
        return analysis

    # ── steps ────────────────────────────────────────────────────────────
    async def list_steps(self, ticket_id: uuid.UUID, *, include_deleted: bool = False) -> Sequence[ResolutionStep]:
        stmt = select(ResolutionStep).where(ResolutionStep.ticket_id == ticket_id)
        if not include_deleted:
            stmt = stmt.where(ResolutionStep.deleted_at.is_(None))
        stmt = stmt.order_by(ResolutionStep.position, ResolutionStep.created_at)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_step(self, ticket_id: uuid.UUID, step_id: uuid.UUID) -> ResolutionStep | None:
        stmt = select(ResolutionStep).where(
            ResolutionStep.id == step_id, ResolutionStep.ticket_id == ticket_id, ResolutionStep.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def step_progress(self, ticket_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
        """(completed_or_skipped, total) per ticket."""
        if not ticket_ids:
            return {}
        done = func.count().filter(ResolutionStep.status.in_(["completed", "skipped"]))
        stmt = (
            select(ResolutionStep.ticket_id, done, func.count())
            .where(ResolutionStep.ticket_id.in_(ticket_ids), ResolutionStep.deleted_at.is_(None))
            .group_by(ResolutionStep.ticket_id)
        )
        return {tid: (int(d), int(t)) for tid, d, t in (await self.session.execute(stmt)).all()}

    async def add_step(self, step: ResolutionStep) -> ResolutionStep:
        self.session.add(step)
        await self.session.flush()
        return step

    async def renumber_steps(self, ticket_id: uuid.UUID, ordered_ids: Sequence[uuid.UUID]) -> None:
        for position, step_id in enumerate(ordered_ids):
            await self.session.execute(
                update(ResolutionStep)
                .where(ResolutionStep.id == step_id, ResolutionStep.ticket_id == ticket_id)
                .values(position=position)
            )

    # ── comments ─────────────────────────────────────────────────────────
    async def list_comments(self, ticket_id: uuid.UUID, *, include_internal: bool) -> Sequence[TicketComment]:
        stmt = select(TicketComment).where(TicketComment.ticket_id == ticket_id)
        if not include_internal:
            stmt = stmt.where(TicketComment.visibility == "requester")
        return (await self.session.execute(stmt.order_by(TicketComment.created_at))).scalars().all()

    async def add_comment(self, comment: TicketComment) -> TicketComment:
        self.session.add(comment)
        await self.session.flush()
        return comment

    async def latest_comments(self, ticket_ids: Sequence[uuid.UUID], *, author_ids: Sequence[uuid.UUID] | None = None) -> dict[uuid.UUID, TicketComment]:
        if not ticket_ids:
            return {}
        ranked = (
            select(TicketComment, func.row_number().over(partition_by=TicketComment.ticket_id, order_by=TicketComment.created_at.desc()).label("rn"))
            .where(TicketComment.ticket_id.in_(ticket_ids))
        )
        if author_ids is not None:
            ranked = ranked.where(TicketComment.author_id.in_(author_ids))
        sub = ranked.subquery()
        rows = (await self.session.execute(select(TicketComment).join(sub, sub.c.id == TicketComment.id).where(sub.c.rn == 1))).scalars().all()
        return {c.ticket_id: c for c in rows}

    # ── assignment history ───────────────────────────────────────────────
    async def add_assignment(self, assignment: TicketAssignment) -> TicketAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def list_assignments(self, ticket_id: uuid.UUID) -> Sequence[TicketAssignment]:
        stmt = select(TicketAssignment).where(TicketAssignment.ticket_id == ticket_id).order_by(TicketAssignment.created_at)
        return (await self.session.execute(stmt)).scalars().all()

    # ── attachments ──────────────────────────────────────────────────────
    async def add_attachment(self, attachment: Attachment) -> Attachment:
        self.session.add(attachment)
        await self.session.flush()
        return attachment

    async def list_attachments(self, ticket_id: uuid.UUID) -> Sequence[Attachment]:
        stmt = select(Attachment).where(Attachment.ticket_id == ticket_id).order_by(Attachment.created_at)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_attachment(self, attachment_id: uuid.UUID) -> Attachment | None:
        return await self.session.get(Attachment, attachment_id)

    async def link_conversation_attachments(self, conversation_id: uuid.UUID, ticket_id: uuid.UUID) -> int:
        result = await self.session.execute(
            update(Attachment)
            .where(and_(Attachment.conversation_id == conversation_id, Attachment.ticket_id.is_(None)))
            .values(ticket_id=ticket_id)
        )
        return int(result.rowcount or 0)
