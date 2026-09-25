"""Deterministic routing: rules → service owner → AI recommendation → service desk.

AI can *recommend* a team; hard routing requirements live in assignment rules,
which always win. Both the AI-recommended team and the actual team are stored
on the ticket so routing quality can be audited and improved.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.enums import ActorType, SupportLevel
from app.domain.policies import Principal
from app.models import AssignmentRule, Profile, Ticket, TicketAssignment
from app.services.audit_service import AuditService
from app.services.base import Repos


@dataclass(frozen=True)
class RoutingDecision:
    team_id: uuid.UUID | None
    team_name: str | None
    support_level: str
    reason: str
    rule_id: uuid.UUID | None = None
    rule_name: str | None = None


def _eq(a: str | None, b: str | None) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def match_rule(
    rules: Sequence[AssignmentRule],
    *,
    category: str | None,
    subcategory: str | None,
    priority: str | None,
    ticket_type: str | None,
    service_id: uuid.UUID | None,
) -> AssignmentRule | None:
    """Most specific enabled rule wins; ties go to the lowest sort_order."""
    best: tuple[int, int, str] | None = None
    winner: AssignmentRule | None = None
    for rule in rules:
        if not rule.enabled:
            continue
        conditions = [
            (rule.category, lambda v: _eq(v, category)),
            (rule.subcategory, lambda v: _eq(v, subcategory)),
            (rule.priority, lambda v: v == priority),
            (rule.ticket_type, lambda v: v == ticket_type),
            (rule.service_id, lambda v: v == service_id),
        ]
        if not all(value is None or check(value) for value, check in conditions):
            continue
        specificity = sum(1 for value, _ in conditions if value is not None)
        if specificity == 0:
            continue  # a rule with no conditions would swallow everything
        key = (-specificity, rule.sort_order, rule.name)
        if best is None or key < best:
            best, winner = key, rule
    return winner


class AssignmentService:
    def __init__(self, repos: Repos, audit: AuditService) -> None:
        self.repos = repos
        self.audit = audit

    async def route(
        self,
        *,
        category: str | None,
        subcategory: str | None,
        priority: str | None,
        ticket_type: str | None,
        service_id: uuid.UUID | None,
        ai_team_id: uuid.UUID | None = None,
    ) -> RoutingDecision:
        rules = await self.repos.settings.assignment_rules(enabled_only=True)
        rule = match_rule(
            rules, category=category, subcategory=subcategory, priority=priority, ticket_type=ticket_type, service_id=service_id
        )
        if rule is not None:
            team = await self.repos.users.get_team(rule.team_id)
            return RoutingDecision(rule.team_id, team.name if team else None, rule.support_level, f"rule:{rule.name}", rule.id, rule.name)

        if service_id is not None:
            service = await self.repos.settings.get_service(service_id)
            if service and service.owner_team_id:
                team = await self.repos.users.get_team(service.owner_team_id)
                if team:
                    return RoutingDecision(team.id, team.name, SupportLevel.L1.value, "service_owner")

        if ai_team_id is not None:
            team = await self.repos.users.get_team(ai_team_id)
            if team:
                return RoutingDecision(team.id, team.name, SupportLevel.L1.value, "ai_recommendation")

        desk = await self.repos.users.service_desk()
        if desk:
            return RoutingDecision(desk.id, desk.name, SupportLevel.L1.value, "service_desk_default")
        return RoutingDecision(None, None, SupportLevel.L1.value, "no_team_configured")

    async def pick_engineer(self, team_id: uuid.UUID, level: str, *, exclude: uuid.UUID | None = None) -> Profile | None:
        """Least-loaded active engineer at the level, falling back to any level in the team."""
        for wanted in (level, None):
            candidates = [p for p, _ in await self.repos.users.assignable_engineers(team_id, wanted) if p.id != exclude]
            if candidates:
                return candidates[0]
        return None

    async def assign(
        self,
        ticket: Ticket,
        *,
        team_id: uuid.UUID | None,
        support_level: str,
        reason: str,
        engineer: Profile | None = None,
        pick_engineer: bool = True,
        actor: Principal | None = None,
        actor_type: ActorType = ActorType.SYSTEM,
        exclude_engineer: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> Profile | None:
        if engineer is None and pick_engineer and team_id is not None:
            engineer = await self.pick_engineer(team_id, support_level, exclude=exclude_engineer)
        old = {
            "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
            "team_id": str(ticket.assignment_team_id) if ticket.assignment_team_id else None,
            "support_level": ticket.support_level,
        }
        ticket.assignment_team_id = team_id
        ticket.assigned_to = engineer.id if engineer else None
        ticket.support_level = support_level
        ticket.assignment_reason = reason
        await self.repos.tickets.add_assignment(
            TicketAssignment(
                ticket_id=ticket.id,
                team_id=team_id,
                assignee_id=engineer.id if engineer else None,
                support_level=support_level,
                reason=reason,
                assigned_by=actor.profile_id if actor else None,
            )
        )
        team = await self.repos.users.get_team(team_id) if team_id else None
        await self.audit.record(
            "ticket.assigned",
            actor=actor,
            actor_type=actor_type,
            ticket_id=ticket.id,
            old_value=old,
            new_value={
                "assigned_to": str(engineer.id) if engineer else None,
                "assignee_name": engineer.name if engineer else None,
                "team_id": str(team_id) if team_id else None,
                "team_name": team.name if team else None,
                "support_level": support_level,
            },
            metadata={"reason": reason, **(metadata or {})},
        )
        return engineer
