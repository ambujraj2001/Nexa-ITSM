from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator

from app.domain.enums import (
    CommentVisibility,
    EscalationReason,
    Priority,
    ResolutionCode,
    StepStatus,
    TicketStatus,
    TicketType,
)
from app.schemas.common import PersonRef, Schema, ServiceRef, SlaInfo, TeamRef


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


# ── views ──────────────────────────────────────────────────────────────────


class TicketSummary(Schema):
    id: uuid.UUID
    ticket_number: str
    title: str
    ticket_type: str
    type_label: str
    priority: str
    status: str
    status_label: str
    category: str | None = None
    subcategory: str | None = None
    requester: PersonRef
    assignee: PersonRef | None = None
    team: TeamRef | None = None
    support_level: str
    sla: SlaInfo
    ai_status: str
    ai_headline: str | None = None
    summary: str | None = None
    steps_done: int = 0
    steps_total: int = 0
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class EvidenceView(Schema):
    source_type: str
    reference: str | None = None
    title: str | None = None
    summary: str
    ref_id: uuid.UUID | None = None


class HypothesisView(Schema):
    cause: str
    likelihood: str
    how_to_verify: str | None = None


class SignalView(Schema):
    label: str
    value: str
    kind: str = "other"


class HandoffView(Schema):
    summary: str
    completed_checks: list[str] = []
    ruled_out: list[str] = []
    open_questions: list[str] = []
    suggested_next: list[str] = []
    generated_at: datetime | None = None


class AnalysisView(Schema):
    category: str | None = None
    subcategory: str | None = None
    priority: str | None = None
    summary: str | None = None
    diagnosis: str | None = None
    confidence: float | None = None
    confidence_label: Literal["high", "medium", "low"] | None = None
    below_threshold: bool = False
    rationale: str | None = None
    evidence: list[EvidenceView] = []
    hypotheses: list[HypothesisView] = []
    signals: list[SignalView] = []
    missing_information: list[str] = []
    recommended_team: TeamRef | None = None
    handoff: HandoffView | None = None
    updated_at: datetime | None = None


class StepView(Schema):
    id: uuid.UUID
    position: int
    description: str
    details: str | None = None
    technical_details: str | None = None
    status: str
    source: str
    edited: bool
    notes: str | None = None
    created_by: PersonRef | None = None
    completed_by: PersonRef | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    is_current: bool = False


class CommentView(Schema):
    id: uuid.UUID
    author: PersonRef | None = None
    author_type: str
    author_label: str
    content: str
    visibility: str
    kind: str
    created_at: datetime


class ActivityItem(Schema):
    id: uuid.UUID
    at: datetime
    actor_type: str
    actor_label: str
    action: str
    summary: str
    detail: str | None = None


class ProgressStage(Schema):
    key: str
    label: str
    state: Literal["done", "active", "pending", "failed", "skipped"]


class ProgressView(Schema):
    ticket_id: uuid.UUID
    ticket_number: str
    status: str
    ai_status: str
    ai_stage: str | None = None
    stages: list[ProgressStage]
    error: str | None = None
    team: TeamRef | None = None
    assignee: PersonRef | None = None


class TicketPermissions(Schema):
    can_work: bool = False
    can_self_assign: bool = False
    can_reassign: bool = False
    can_escalate: bool = False
    can_resolve: bool = False
    can_reopen: bool = False
    can_close: bool = False
    can_comment_internal: bool = False
    can_reply: bool = False
    can_retry_ai: bool = False


class EscalationInfo(Schema):
    escalated_at: datetime
    from_person: PersonRef | None = None
    to_team: TeamRef | None = None
    reason: str
    reason_label: str
    note: str | None = None


class ResolutionView(Schema):
    summary: str | None = None
    employee_summary: str | None = None
    code: str | None = None
    resolved_by: PersonRef | None = None
    resolved_at: datetime | None = None
    completed_steps: list[str] = []


class AttachmentView(Schema):
    id: uuid.UUID
    file_name: str
    content_type: str | None = None
    size_bytes: int | None = None
    uploaded_by: PersonRef | None = None
    created_at: datetime
    url: str | None = None


class TicketDetail(TicketSummary):
    """Engineer/admin view: everything, including internal context."""

    view: Literal["engineer"] = "engineer"
    description: str
    impact: str | None = None
    urgency: str | None = None
    source: str
    service: ServiceRef | None = None
    sla_response_due_at: datetime | None = None
    first_response_at: datetime | None = None
    ai_error: str | None = None
    ai_stage: str | None = None
    ai_recommended_team: TeamRef | None = None
    assignment_reason: str | None = None
    analysis: AnalysisView | None = None
    steps: list[StepView] = []
    escalation: EscalationInfo | None = None
    resolution: ResolutionView | None = None
    permissions: TicketPermissions
    escalation_count: int = 0
    reopen_count: int = 0


class EmployeeStepView(Schema):
    id: uuid.UUID
    position: int
    description: str
    status: str
    completed_at: datetime | None = None


class EmployeeTicketDetail(Schema):
    """What the requester sees: status, who, progress, what's needed — no internals."""

    view: Literal["employee"] = "employee"
    id: uuid.UUID
    ticket_number: str
    title: str
    description: str
    ticket_type: str
    type_label: str
    priority: str
    status: str
    status_label: str
    category: str | None = None
    subcategory: str | None = None
    likely_cause: str | None = None
    summary: str | None = None
    assignee: PersonRef | None = None
    team: TeamRef | None = None
    ai_status: str
    waiting_on: Literal["you", "it_team"] | None = None
    steps: list[EmployeeStepView] = []
    steps_done: int = 0
    steps_total: int = 0
    resolution: ResolutionView | None = None
    permissions: TicketPermissions
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class TicketListResponse(Schema):
    items: list[TicketSummary]
    total: int
    limit: int
    offset: int


class RelatedIncident(Schema):
    ticket_id: uuid.UUID
    ticket_number: str
    title: str
    resolution_summary: str | None = None
    resolved_in: str | None = None
    similarity: float | None = None


class RelatedArticle(Schema):
    article_id: uuid.UUID
    article_number: str
    title: str
    excerpt: str | None = None
    updated_at: datetime
    similarity: float | None = None


class RelatedView(Schema):
    similar_incidents: list[RelatedIncident]
    knowledge: list[RelatedArticle]


class CopilotReplyView(Schema):
    answer: str
    references: list[str] = []
    draft_message: str | None = None
    model: str | None = None


class ResolutionDraftView(Schema):
    resolution_summary: str
    employee_summary: str
    generated: bool = True


# ── requests ───────────────────────────────────────────────────────────────


class TicketCreate(Schema):
    title: str | None = Field(default=None, max_length=200)
    description: str = Field(min_length=3, max_length=8000)
    ticket_type: TicketType = TicketType.INCIDENT
    priority: Priority | None = None
    service_id: uuid.UUID | None = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return _clean(value) if isinstance(value, str) else value


class TicketUpdate(Schema):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    priority: Priority | None = None
    status: TicketStatus | None = None
    ticket_type: TicketType | None = None
    service_id: uuid.UUID | None = None
    category: str | None = Field(default=None, max_length=80)
    subcategory: str | None = Field(default=None, max_length=80)


class ReassignRequest(Schema):
    assignee_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=2000)


class EscalateRequest(Schema):
    reason: EscalationReason
    note: str | None = Field(default=None, max_length=4000)
    target_team_id: uuid.UUID | None = None


class ResolveRequest(Schema):
    resolution_summary: str = Field(min_length=10, max_length=8000)
    resolution_code: ResolutionCode = ResolutionCode.FIXED


class ReopenRequest(Schema):
    reason: str = Field(min_length=3, max_length=4000)


class StepCreate(Schema):
    description: str = Field(min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=2000)
    technical_details: str | None = Field(default=None, max_length=4000)
    position: int | None = Field(default=None, ge=0)


class StepUpdate(Schema):
    description: str | None = Field(default=None, min_length=1, max_length=300)
    details: str | None = Field(default=None, max_length=2000)
    technical_details: str | None = Field(default=None, max_length=4000)
    status: StepStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)


class StepReorder(Schema):
    step_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class CommentCreate(Schema):
    content: str = Field(min_length=1, max_length=10000)
    visibility: CommentVisibility = CommentVisibility.REQUESTER
    # Engineer asks the requester for information → ticket moves to pending_user.
    request_info: bool = False


class CopilotRequest(Schema):
    message: str = Field(min_length=1, max_length=2000)


class TicketListParams(Schema):
    scope: Literal["visible", "assigned", "team", "requested"] = "visible"
    ticket_type: TicketType | None = None
    status: list[TicketStatus] = []
    priority: Priority | None = None
    open_only: bool = False
    q: str | None = Field(default=None, max_length=200)
    sort: Literal["updated", "sla", "priority", "created"] = "updated"
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


JSON = dict[str, Any]

# Response type for endpoints that return the role-appropriate ticket view.
AnyTicketView = Annotated[TicketDetail | EmployeeTicketDetail, Field(discriminator="view")]
