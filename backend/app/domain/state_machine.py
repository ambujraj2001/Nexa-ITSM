"""Ticket lifecycle. Every status change in the system goes through `ensure_transition`."""

from __future__ import annotations

from app.core.errors import Conflict
from app.domain.enums import TicketStatus as S

ALLOWED_TRANSITIONS: dict[S, frozenset[S]] = {
    S.NEW: frozenset({S.TRIAGING, S.ASSIGNED, S.IN_PROGRESS}),
    S.TRIAGING: frozenset({S.ASSIGNED, S.IN_PROGRESS, S.NEW}),
    S.ASSIGNED: frozenset({S.ASSIGNED, S.IN_PROGRESS, S.PENDING_USER, S.ESCALATED, S.RESOLVED}),
    S.IN_PROGRESS: frozenset({S.ASSIGNED, S.PENDING_USER, S.ESCALATED, S.RESOLVED}),
    S.PENDING_USER: frozenset({S.PENDING_ENGINEER, S.IN_PROGRESS, S.ESCALATED, S.RESOLVED, S.ASSIGNED}),
    S.PENDING_ENGINEER: frozenset({S.IN_PROGRESS, S.PENDING_USER, S.ESCALATED, S.RESOLVED, S.ASSIGNED}),
    S.ESCALATED: frozenset({S.ESCALATED, S.IN_PROGRESS, S.PENDING_USER, S.RESOLVED, S.ASSIGNED}),
    S.RESOLVED: frozenset({S.CLOSED, S.REOPENED}),
    S.CLOSED: frozenset({S.REOPENED}),
    S.REOPENED: frozenset({S.ASSIGNED, S.IN_PROGRESS, S.PENDING_USER, S.ESCALATED, S.RESOLVED}),
}

# Statuses an engineer may set directly via PATCH. Everything else has a
# dedicated flow that captures the required context (escalate, resolve, reopen…).
DIRECTLY_SETTABLE: frozenset[S] = frozenset({S.IN_PROGRESS, S.PENDING_USER})

# When an engineer starts acting on a ticket in one of these states, it moves to in_progress.
AUTO_START_FROM: frozenset[S] = frozenset({S.NEW, S.TRIAGING, S.ASSIGNED, S.ESCALATED, S.REOPENED, S.PENDING_ENGINEER})


def can_transition(current: S | str, target: S | str) -> bool:
    return S(target) in ALLOWED_TRANSITIONS.get(S(current), frozenset())


def ensure_transition(current: S | str, target: S | str) -> None:
    if not can_transition(current, target):
        raise Conflict(
            f"A ticket that is {S(current).value.replace('_', ' ')} can't move to {S(target).value.replace('_', ' ')}.",
            code="invalid_transition",
            details={"from": S(current).value, "to": S(target).value},
        )
