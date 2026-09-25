"""Authorization rules (the backend's single source of truth for access)."""

from __future__ import annotations

import uuid

import pytest

from app.core.errors import NotFound
from app.domain import policies
from app.domain.enums import CommentVisibility, Role, SupportLevel, TicketStatus
from app.domain.policies import Principal, TicketFacts

TEAM, OTHER_TEAM = uuid.uuid4(), uuid.uuid4()


def person(role: Role, team: uuid.UUID | None = None, level: SupportLevel | None = None) -> Principal:
    return Principal(profile_id=uuid.uuid4(), auth_user_id=uuid.uuid4(), role=role, name="x", email="x@example.com", engineer_level=level, team_id=team)


employee = person(Role.EMPLOYEE)
other_employee = person(Role.EMPLOYEE)
engineer = person(Role.ENGINEER, TEAM, SupportLevel.L1)
teammate = person(Role.ENGINEER, TEAM, SupportLevel.L1)
outsider = person(Role.ENGINEER, OTHER_TEAM, SupportLevel.L2)
admin = person(Role.ADMIN)


def ticket(status: TicketStatus = TicketStatus.IN_PROGRESS, assigned: Principal | None = engineer, previously: bool = False) -> TicketFacts:
    return TicketFacts(
        id=uuid.uuid4(), requester_id=employee.profile_id, assigned_to=assigned.profile_id if assigned else None,
        assignment_team_id=TEAM, status=status, previously_assigned=previously,
    )


def test_employees_see_only_their_own_tickets() -> None:
    assert policies.can_view_ticket(employee, ticket())
    assert not policies.can_view_ticket(other_employee, ticket())
    with pytest.raises(NotFound):  # 404, not 403: existence isn't disclosed
        policies.ensure_can_view(other_employee, ticket())


def test_engineers_see_assigned_team_and_previously_handled_tickets() -> None:
    assert policies.can_view_ticket(engineer, ticket())
    assert policies.can_view_ticket(teammate, ticket())
    assert not policies.can_view_ticket(outsider, ticket())
    assert policies.can_view_ticket(outsider, ticket(previously=True))
    assert policies.can_view_ticket(admin, ticket())


def test_only_the_assignee_or_admin_works_a_ticket() -> None:
    assert policies.can_work_ticket(engineer, ticket())
    assert not policies.can_work_ticket(teammate, ticket())
    assert not policies.can_work_ticket(employee, ticket())
    assert policies.can_work_ticket(admin, ticket())
    assert not policies.can_work_ticket(engineer, ticket(TicketStatus.RESOLVED))


def test_self_assign_only_unassigned_team_work() -> None:
    assert policies.can_self_assign(teammate, ticket(assigned=None))
    assert not policies.can_self_assign(teammate, ticket())
    assert not policies.can_self_assign(outsider, ticket(assigned=None))
    assert not policies.can_self_assign(employee, ticket(assigned=None))


def test_internal_notes_are_staff_only() -> None:
    t = ticket()
    assert policies.can_comment(employee, t, CommentVisibility.REQUESTER)
    assert not policies.can_comment(employee, t, CommentVisibility.INTERNAL)
    assert policies.can_comment(engineer, t, CommentVisibility.INTERNAL)
    assert not policies.can_view_internal(employee, t)


def test_reopen_and_close() -> None:
    resolved = ticket(TicketStatus.RESOLVED)
    assert policies.can_reopen(employee, resolved) and policies.can_close(employee, resolved)
    assert not policies.can_reopen(other_employee, resolved)
    assert not policies.can_reopen(employee, ticket())


def test_settings_are_admin_only() -> None:
    assert policies.can_manage_settings(admin)
    assert not policies.can_manage_settings(engineer)
    assert not policies.can_manage_settings(employee)
