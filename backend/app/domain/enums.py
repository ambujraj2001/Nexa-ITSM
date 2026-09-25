"""Controlled vocabularies. Values match the CHECK constraints in the migrations."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    EMPLOYEE = "employee"
    ENGINEER = "engineer"
    ADMIN = "admin"


class SupportLevel(StrEnum):
    L1 = "L1"
    L2 = "L2"


class TicketType(StrEnum):
    INCIDENT = "incident"
    SERVICE_REQUEST = "service_request"
    PROBLEM = "problem"
    CHANGE = "change"


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

    @property
    def rank(self) -> int:
        return int(self.value[1])


class TicketStatus(StrEnum):
    NEW = "new"
    TRIAGING = "triaging"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING_USER = "pending_user"
    PENDING_ENGINEER = "pending_engineer"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


OPEN_STATUSES: frozenset[TicketStatus] = frozenset(
    s for s in TicketStatus if s not in {TicketStatus.RESOLVED, TicketStatus.CLOSED}
)
DONE_STATUSES: frozenset[TicketStatus] = frozenset({TicketStatus.RESOLVED, TicketStatus.CLOSED})
# Statuses where the next move is the engineer's.
WAITING_ON_ENGINEER: frozenset[TicketStatus] = frozenset(
    {
        TicketStatus.NEW,
        TicketStatus.TRIAGING,
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.PENDING_ENGINEER,
        TicketStatus.ESCALATED,
        TicketStatus.REOPENED,
    }
)


class StepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class StepSource(StrEnum):
    AI = "ai"
    ENGINEER = "engineer"


class CommentVisibility(StrEnum):
    INTERNAL = "internal"
    REQUESTER = "requester"


class CommentKind(StrEnum):
    COMMENT = "comment"
    QUESTION = "question"
    ESCALATION_NOTE = "escalation_note"
    HANDOFF_SUMMARY = "handoff_summary"
    RESOLUTION = "resolution"
    SYSTEM = "system"


class ActorType(StrEnum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class AIStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AIStage(StrEnum):
    UNDERSTANDING = "understanding"
    KNOWLEDGE = "knowledge"
    SIMILAR_INCIDENTS = "similar_incidents"
    DIAGNOSIS = "diagnosis"
    PLANNING = "planning"
    ASSIGNMENT = "assignment"
    DONE = "done"


AI_STAGE_ORDER: tuple[AIStage, ...] = (
    AIStage.UNDERSTANDING,
    AIStage.KNOWLEDGE,
    AIStage.SIMILAR_INCIDENTS,
    AIStage.DIAGNOSIS,
    AIStage.PLANNING,
    AIStage.ASSIGNMENT,
    AIStage.DONE,
)

AI_STAGE_LABELS: dict[AIStage, str] = {
    AIStage.UNDERSTANDING: "Understanding request",
    AIStage.KNOWLEDGE: "Finding relevant knowledge",
    AIStage.SIMILAR_INCIDENTS: "Reviewing similar incidents",
    AIStage.DIAGNOSIS: "Preparing diagnosis",
    AIStage.PLANNING: "Building resolution plan",
    AIStage.ASSIGNMENT: "Routing to the right team",
    AIStage.DONE: "Investigation complete",
}


class Impact(StrEnum):
    INDIVIDUAL = "individual"
    TEAM = "team"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"


class Urgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketSource(StrEnum):
    ASSISTANT = "assistant"
    PORTAL = "portal"
    EMAIL = "email"
    API = "api"
    MANUAL = "manual"


class ResolutionCode(StrEnum):
    FIXED = "fixed"
    WORKAROUND = "workaround"
    NO_FAULT_FOUND = "no_fault_found"
    USER_GUIDANCE = "user_guidance"
    DUPLICATE = "duplicate"
    OTHER = "other"


class EscalationReason(StrEnum):
    ELEVATED_ACCESS = "requires_elevated_access"
    SPECIALIST_EXPERTISE = "requires_specialist_expertise"
    OUTSIDE_RUNBOOK = "outside_l1_runbook"
    SLA_RISK = "sla_risk"
    VENDOR = "vendor_involvement"
    OTHER = "other"


ESCALATION_REASON_LABELS: dict[EscalationReason, str] = {
    EscalationReason.ELEVATED_ACCESS: "Requires elevated access",
    EscalationReason.SPECIALIST_EXPERTISE: "Requires specialist expertise",
    EscalationReason.OUTSIDE_RUNBOOK: "Outside the L1 runbook",
    EscalationReason.SLA_RISK: "SLA at risk",
    EscalationReason.VENDOR: "Needs vendor involvement",
    EscalationReason.OTHER: "Other",
}

STATUS_LABELS: dict[TicketStatus, str] = {
    TicketStatus.NEW: "New",
    TicketStatus.TRIAGING: "Investigating",
    TicketStatus.ASSIGNED: "Assigned",
    TicketStatus.IN_PROGRESS: "In Progress",
    TicketStatus.PENDING_USER: "Waiting on you",
    TicketStatus.PENDING_ENGINEER: "Waiting on engineer",
    TicketStatus.ESCALATED: "Escalated",
    TicketStatus.RESOLVED: "Resolved",
    TicketStatus.CLOSED: "Closed",
    TicketStatus.REOPENED: "Reopened",
}

TICKET_TYPE_LABELS: dict[TicketType, str] = {
    TicketType.INCIDENT: "Incident",
    TicketType.SERVICE_REQUEST: "Request",
    TicketType.PROBLEM: "Problem",
    TicketType.CHANGE: "Change",
}
