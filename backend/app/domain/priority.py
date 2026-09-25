"""Deterministic priority.

The AI estimates impact and urgency from the employee's words; this ITIL-style
matrix turns them into a priority, then a few hard rules adjust for service
criticality and security. The AI's own suggestion is recorded but never the
final word, so priority stays explainable and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import Impact, Priority, TicketType, Urgency

_MATRIX: dict[Impact, dict[Urgency, Priority]] = {
    Impact.ORGANIZATION: {Urgency.CRITICAL: Priority.P1, Urgency.HIGH: Priority.P1, Urgency.MEDIUM: Priority.P2, Urgency.LOW: Priority.P3},
    Impact.DEPARTMENT: {Urgency.CRITICAL: Priority.P1, Urgency.HIGH: Priority.P2, Urgency.MEDIUM: Priority.P2, Urgency.LOW: Priority.P3},
    Impact.TEAM: {Urgency.CRITICAL: Priority.P2, Urgency.HIGH: Priority.P2, Urgency.MEDIUM: Priority.P3, Urgency.LOW: Priority.P4},
    Impact.INDIVIDUAL: {Urgency.CRITICAL: Priority.P2, Urgency.HIGH: Priority.P3, Urgency.MEDIUM: Priority.P3, Urgency.LOW: Priority.P4},
}

SECURITY_CATEGORIES = frozenset({"security"})


@dataclass(frozen=True)
class PriorityDecision:
    priority: Priority
    reason: str


def _higher(a: Priority, b: Priority) -> Priority:
    return a if a.rank <= b.rank else b


def determine_priority(
    *,
    impact: Impact | str | None,
    urgency: Urgency | str | None,
    ai_suggestion: Priority | str | None = None,
    ticket_type: TicketType | str = TicketType.INCIDENT,
    category: str | None = None,
    service_criticality: str | None = None,
) -> PriorityDecision:
    if impact and urgency:
        base = _MATRIX[Impact(impact)][Urgency(urgency)]
        reason = f"{Impact(impact).value} impact × {Urgency(urgency).value} urgency"
    elif ai_suggestion:
        base = Priority(ai_suggestion)
        reason = "AI suggestion (impact/urgency not determined)"
    else:
        base = Priority.P3
        reason = "default"

    priority = base
    if (category or "").strip().lower() in SECURITY_CATEGORIES and TicketType(ticket_type) == TicketType.INCIDENT:
        raised = _higher(priority, Priority.P2)
        if raised != priority:
            priority, reason = raised, reason + "; raised for security incident"

    if service_criticality == "critical" and TicketType(ticket_type) == TicketType.INCIDENT:
        wide = impact and Impact(impact) in {Impact.DEPARTMENT, Impact.ORGANIZATION}
        floor = Priority.P1 if wide else Priority.P2
        raised = _higher(priority, floor)
        if raised != priority:
            priority, reason = raised, reason + "; raised for critical service"

    # Requests rarely warrant P1/P2 unless genuinely urgent.
    if TicketType(ticket_type) == TicketType.SERVICE_REQUEST:
        cap = Priority.P2 if urgency and Urgency(urgency) == Urgency.CRITICAL else Priority.P3
        if priority.rank < cap.rank:
            priority, reason = cap, reason + "; capped for service request"

    return PriorityDecision(priority=priority, reason=reason)
