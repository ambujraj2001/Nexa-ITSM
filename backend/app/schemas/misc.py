"""Schemas for conversations, dashboards, settings, admin, knowledge, catalogue and auth."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import EmailStr, Field

from app.domain.enums import Priority, Role, SupportLevel, TicketType
from app.schemas.common import PersonRef, Schema, ServiceRef, TeamRef
from app.schemas.tickets import TicketSummary

# ── auth ───────────────────────────────────────────────────────────────────


class MeView(Schema):
    id: uuid.UUID
    name: str
    email: str
    role: str
    engineer_level: str | None = None
    team: TeamRef | None = None
    job_title: str | None = None
    department: str | None = None
    location: str | None = None
    avatar_url: str | None = None
    home_path: str


class ProfileUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    job_title: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)


# ── conversations ──────────────────────────────────────────────────────────


class MessageView(Schema):
    id: uuid.UUID
    role: str
    content: str
    message_type: str
    payload: dict[str, Any] = {}
    ticket_id: uuid.UUID | None = None
    created_at: datetime


class ConversationView(Schema):
    id: uuid.UUID
    title: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageView] = []


class SendMessageRequest(Schema):
    content: str = Field(min_length=1, max_length=4000)


class SendMessageResponse(Schema):
    conversation_id: uuid.UUID
    messages: list[MessageView]


class ConfirmProposalResponse(Schema):
    ticket: TicketSummary
    messages: list[MessageView]


# ── dashboards ─────────────────────────────────────────────────────────────


class DashboardMetrics(Schema):
    assigned_to_me: int
    urgent: int
    urgent_at_risk: int
    due_soon: int
    team_queue: int


class AttentionReason(Schema):
    code: str
    label: str


class AiLine(Schema):
    kind: Literal["diagnosis", "needs_info", "failed", "running", "plan_ready", "disabled", "none"]
    label: str
    text: str | None = None


class AttentionItem(Schema):
    ticket: TicketSummary
    reasons: list[AttentionReason]
    ai: AiLine
    action_label: str


class EngineerDashboard(Schema):
    metrics: DashboardMetrics
    needs_attention: list[AttentionItem]
    my_tickets: list[TicketSummary]
    team_queue: list[TicketSummary]
    shift_label: str
    generated_at: datetime


class EmployeeDashboard(Schema):
    active: list[TicketSummary]
    recent: list[TicketSummary]
    waiting_on_you: int
    open_count: int


# ── settings ───────────────────────────────────────────────────────────────


class ModelRouteView(Schema):
    gateway: str
    configured: bool
    fast_model: str | None = None
    strong_model: str | None = None
    embedding_model: str | None = None
    fallback_models: list[str] = []
    routes: dict[str, str | None] = {}


class KnowledgeSourceView(Schema):
    id: uuid.UUID
    name: str
    source_type: str
    description: str | None = None
    enabled: bool
    item_count: int = 0
    indexed_count: int = 0
    last_indexed_at: datetime | None = None


class KnowledgeSourceUpdate(Schema):
    enabled: bool


class IntegrationView(Schema):
    id: uuid.UUID
    provider: str
    display_name: str
    category: str
    description: str | None = None
    enabled: bool
    status: str
    config: dict[str, Any] = {}
    secret_ref: str | None = None
    secret_present: bool = False
    available: bool = True
    status_detail: str | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None


class IntegrationUpdate(Schema):
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class AiPolicyView(Schema):
    automatic_actions_locked: bool = True
    human_approval_locked: bool = True
    statement: str = "AI investigates and recommends. Engineers execute every change and resolve every ticket."


class AiSettingsView(Schema):
    ai_triage_enabled: bool
    ai_diagnosis_enabled: bool
    resolution_plans_enabled: bool
    automatic_actions_enabled: bool
    human_approval_required: bool
    confidence_threshold: float
    policy: AiPolicyView
    models: ModelRouteView
    knowledge_sources: list[KnowledgeSourceView]
    integrations: list[IntegrationView]
    updated_at: datetime
    updated_by: PersonRef | None = None
    can_edit: bool


class AiSettingsUpdate(Schema):
    ai_triage_enabled: bool | None = None
    ai_diagnosis_enabled: bool | None = None
    resolution_plans_enabled: bool | None = None
    automatic_actions_enabled: bool | None = None
    human_approval_required: bool | None = None
    confidence_threshold: float | None = Field(default=None, ge=0.5, le=0.98)


class SlaPolicyView(Schema):
    id: uuid.UUID
    name: str
    priority: str
    response_time_minutes: int
    resolution_time_minutes: int
    enabled: bool
    updated_at: datetime


class SlaPolicyUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    response_time_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 30)
    resolution_time_minutes: int | None = Field(default=None, ge=1, le=60 * 24 * 90)
    enabled: bool | None = None


class AssignmentRuleView(Schema):
    id: uuid.UUID
    name: str
    category: str | None = None
    subcategory: str | None = None
    priority: str | None = None
    ticket_type: str | None = None
    service: ServiceRef | None = None
    team: TeamRef
    support_level: str
    sort_order: int
    enabled: bool
    updated_at: datetime


class AssignmentRuleWrite(Schema):
    name: str = Field(min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    subcategory: str | None = Field(default=None, max_length=80)
    priority: Priority | None = None
    ticket_type: TicketType | None = None
    service_id: uuid.UUID | None = None
    team_id: uuid.UUID
    support_level: SupportLevel = SupportLevel.L1
    sort_order: int = Field(default=100, ge=0, le=10000)
    enabled: bool = True


class RoutingPreviewRequest(Schema):
    category: str | None = None
    subcategory: str | None = None
    priority: Priority | None = None
    ticket_type: TicketType = TicketType.INCIDENT
    service_id: uuid.UUID | None = None


class RoutingPreview(Schema):
    team: TeamRef | None = None
    support_level: str
    reason: str
    rule_name: str | None = None
    engineer: PersonRef | None = None


# ── admin ──────────────────────────────────────────────────────────────────


class UserView(Schema):
    id: uuid.UUID
    name: str
    email: str
    role: str
    engineer_level: str | None = None
    team: TeamRef | None = None
    job_title: str | None = None
    department: str | None = None
    location: str | None = None
    is_active: bool
    has_login: bool
    created_at: datetime


class UserUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Role | None = None
    engineer_level: SupportLevel | None = None
    clear_engineer_level: bool = False
    team_id: uuid.UUID | None = None
    clear_team: bool = False
    job_title: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class UserInvite(Schema):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: Role = Role.EMPLOYEE
    engineer_level: SupportLevel | None = None
    team_id: uuid.UUID | None = None


class TeamView(Schema):
    id: uuid.UUID
    name: str
    description: str | None = None
    is_service_desk: bool
    member_count: int = 0
    l1_count: int = 0
    l2_count: int = 0


class TeamWrite(Schema):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    is_service_desk: bool = False


class AuditEventView(Schema):
    id: uuid.UUID
    created_at: datetime
    actor_type: str
    actor_label: str
    actor_role: str | None = None
    action: str
    summary: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    ticket_id: uuid.UUID | None = None
    ticket_number: str | None = None
    old_value: Any = None
    new_value: Any = None
    metadata: dict[str, Any] = {}


# ── knowledge ──────────────────────────────────────────────────────────────


class ArticleSummary(Schema):
    id: uuid.UUID
    article_number: str
    title: str
    summary: str | None = None
    category: str | None = None
    subcategory: str | None = None
    status: str
    embedding_status: str
    service: ServiceRef | None = None
    updated_at: datetime


class ArticleDetail(ArticleSummary):
    content: str
    created_by: PersonRef | None = None
    updated_by: PersonRef | None = None
    created_at: datetime


class ArticleWrite(Schema):
    title: str = Field(min_length=3, max_length=200)
    summary: str | None = Field(default=None, max_length=600)
    content: str = Field(min_length=10, max_length=100_000)
    category: str | None = Field(default=None, max_length=80)
    subcategory: str | None = Field(default=None, max_length=80)
    service_id: uuid.UUID | None = None
    status: Literal["draft", "published", "archived"] = "draft"


class ArticlePatch(Schema):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    summary: str | None = Field(default=None, max_length=600)
    content: str | None = Field(default=None, min_length=10, max_length=100_000)
    category: str | None = Field(default=None, max_length=80)
    subcategory: str | None = Field(default=None, max_length=80)
    service_id: uuid.UUID | None = None
    status: Literal["draft", "published", "archived"] | None = None


class KnowledgeSearchHit(Schema):
    article_id: uuid.UUID
    article_number: str
    title: str
    category: str | None = None
    excerpt: str
    similarity: float | None = None
    matched_by: list[str] = []
    updated_at: datetime


class KnowledgeSearchRequest(Schema):
    query: str = Field(min_length=2, max_length=500)
    category: str | None = None
    limit: int = Field(default=8, ge=1, le=20)


# ── catalogue ──────────────────────────────────────────────────────────────


class ServiceView(Schema):
    id: uuid.UUID
    name: str
    description: str | None = None
    category: str | None = None
    criticality: str
    owner_team: TeamRef | None = None
    open_tickets: int = 0
    asset_count: int = 0
    updated_at: datetime


class ServiceWrite(Schema):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=80)
    criticality: Literal["low", "medium", "high", "critical"] = "medium"
    owner_team_id: uuid.UUID | None = None


class AssetView(Schema):
    id: uuid.UUID
    name: str
    asset_type: str
    owner: PersonRef | None = None
    service: ServiceRef | None = None
    metadata: dict[str, Any] = {}
    updated_at: datetime


class AssetWrite(Schema):
    name: str = Field(min_length=1, max_length=120)
    asset_type: Literal["laptop", "desktop", "mobile", "peripheral", "server", "application", "network_device", "other"]
    owner_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    metadata: dict[str, Any] = {}


# ── search & notifications ─────────────────────────────────────────────────


class SearchResults(Schema):
    tickets: list[TicketSummary]
    articles: list[ArticleSummary]


class NotificationView(Schema):
    id: uuid.UUID
    at: datetime
    ticket_id: uuid.UUID | None = None
    ticket_number: str | None = None
    ticket_title: str | None = None
    summary: str
    unread: bool


class NotificationsResponse(Schema):
    items: list[NotificationView]
    unread: int
