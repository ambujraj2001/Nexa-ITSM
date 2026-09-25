"""Authorization rules — the single place that decides who may do what.

Pure functions over the authenticated principal (loaded server-side from the
verified JWT, never from client input) and ticket facts. The Postgres RLS
policies in `supabase/migrations/*_rls.sql` mirror `can_view_ticket` as a second
line of defence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.errors import NotFound, PermissionDenied
from app.domain.enums import DONE_STATUSES, CommentVisibility, Role, SupportLevel, TicketStatus


@dataclass(frozen=True)
class Principal:
    profile_id: uuid.UUID
    auth_user_id: uuid.UUID | None
    role: Role
    name: str
    email: str
    engineer_level: SupportLevel | None = None
    team_id: uuid.UUID | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_engineer(self) -> bool:
        return self.role == Role.ENGINEER

    @property
    def is_staff(self) -> bool:
        return self.role in (Role.ENGINEER, Role.ADMIN)


@dataclass(frozen=True)
class TicketFacts:
    id: uuid.UUID
    requester_id: uuid.UUID
    assigned_to: uuid.UUID | None
    assignment_team_id: uuid.UUID | None
    status: TicketStatus
    # True when the principal appears in the ticket's assignment history.
    previously_assigned: bool = False


def can_view_ticket(p: Principal, t: TicketFacts) -> bool:
    if t.requester_id == p.profile_id or p.is_admin:
        return True
    if p.is_engineer:
        return (
            t.assigned_to == p.profile_id
            or (p.team_id is not None and t.assignment_team_id == p.team_id)
            or t.previously_assigned
        )
    return False


def can_view_internal(p: Principal, t: TicketFacts) -> bool:
    """Internal notes, evidence, technical details, full history."""
    return p.is_staff and can_view_ticket(p, t)


def can_work_ticket(p: Principal, t: TicketFacts) -> bool:
    """Execute steps, change status/priority, escalate, resolve."""
    if TicketStatus(t.status) in DONE_STATUSES:
        return False
    return p.is_admin or (p.is_engineer and t.assigned_to == p.profile_id)


def can_self_assign(p: Principal, t: TicketFacts) -> bool:
    if TicketStatus(t.status) in DONE_STATUSES or not p.is_staff or t.assigned_to == p.profile_id:
        return False
    if p.is_admin:
        return True
    # Engineers may pick up unassigned work from their own team's queue.
    return t.assigned_to is None and p.team_id is not None and t.assignment_team_id == p.team_id


def can_reassign(p: Principal, t: TicketFacts) -> bool:
    return TicketStatus(t.status) not in DONE_STATUSES and (p.is_admin or (p.is_engineer and t.assigned_to == p.profile_id))


def can_comment(p: Principal, t: TicketFacts, visibility: CommentVisibility) -> bool:
    if not can_view_ticket(p, t):
        return False
    if visibility == CommentVisibility.INTERNAL:
        return p.is_staff
    return True


def can_reopen(p: Principal, t: TicketFacts) -> bool:
    if TicketStatus(t.status) not in DONE_STATUSES:
        return False
    return t.requester_id == p.profile_id or (p.is_staff and can_view_ticket(p, t))


def can_close(p: Principal, t: TicketFacts) -> bool:
    if TicketStatus(t.status) != TicketStatus.RESOLVED:
        return False
    return t.requester_id == p.profile_id or p.is_admin or (p.is_engineer and t.assigned_to == p.profile_id)


def can_manage_settings(p: Principal) -> bool:
    return p.is_admin


def can_manage_knowledge(p: Principal) -> bool:
    return p.is_staff


def ensure_can_view(p: Principal, t: TicketFacts) -> None:
    # 404 rather than 403, so ticket existence isn't disclosed.
    if not can_view_ticket(p, t):
        raise NotFound("Ticket not found.")


def ensure(allowed: bool, message: str = "You don't have permission to do that.") -> None:
    if not allowed:
        raise PermissionDenied(message)


def ensure_staff(p: Principal) -> None:
    ensure(p.is_staff, "This area is available to IT staff only.")


def ensure_admin(p: Principal) -> None:
    ensure(p.is_admin, "Only workspace admins can do that.")
