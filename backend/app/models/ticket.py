from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, FetchedValue, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class Ticket(UUIDPk, Timestamps, Base):
    __tablename__ = "tickets"

    # Assigned by the tickets_assign_number trigger (INC-/REQ-/PRB-/CHG-).
    ticket_number: Mapped[str] = mapped_column(Text, server_default=FetchedValue())
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    ticket_type: Mapped[str] = mapped_column(String, server_default="incident")
    priority: Mapped[str] = mapped_column(String, server_default="P3")
    status: Mapped[str] = mapped_column(String, server_default="new")
    category: Mapped[str | None] = mapped_column(Text)
    subcategory: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(String)
    urgency: Mapped[str | None] = mapped_column(String)
    requester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    assignment_team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"))
    ai_recommended_team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"))
    assignment_reason: Mapped[str | None] = mapped_column(Text)
    support_level: Mapped[str] = mapped_column(String, server_default="L1")
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"))
    source: Mapped[str] = mapped_column(String, server_default="assistant")
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    sla_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sla_policies.id"))
    sla_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ai_status: Mapped[str] = mapped_column(String, server_default="pending")
    ai_stage: Mapped[str | None] = mapped_column(String)
    ai_error: Mapped[str | None] = mapped_column(Text)
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    resolution_code: Mapped[str | None] = mapped_column(String)
    resolution_ai_summary: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    escalation_count: Mapped[int] = mapped_column(Integer, server_default="0")
    reopen_count: Mapped[int] = mapped_column(Integer, server_default="0")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TicketAiAnalysis(UUIDPk, Timestamps, Base):
    __tablename__ = "ticket_ai_analysis"

    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"))
    category: Mapped[str | None] = mapped_column(Text)
    subcategory: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    rationale: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    hypotheses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    signals: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default="[]")
    missing_information: Mapped[list[str]] = mapped_column(JSONB, server_default="[]")
    recommended_team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"))
    handoff_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    triage_model: Mapped[str | None] = mapped_column(Text)
    diagnosis_model: Mapped[str | None] = mapped_column(Text)
    plan_model: Mapped[str | None] = mapped_column(Text)


class ResolutionStep(UUIDPk, Timestamps, Base):
    __tablename__ = "ticket_resolution_steps"

    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    details: Mapped[str | None] = mapped_column(Text)
    technical_details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, server_default="pending")
    source: Mapped[str] = mapped_column(String)
    edited: Mapped[bool] = mapped_column(Boolean, server_default="false")
    ai_original: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    completed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))


class TicketComment(UUIDPk, Timestamps, Base):
    __tablename__ = "ticket_comments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    author_type: Mapped[str] = mapped_column(String, server_default="user")
    content: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, server_default="comment")


class TicketAssignment(UUIDPk, Base):
    __tablename__ = "ticket_assignments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"))
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    support_level: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(UUIDPk, Base):
    __tablename__ = "audit_history"

    ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"))
    entity_type: Mapped[str] = mapped_column(Text, server_default="ticket")
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    actor_type: Mapped[str] = mapped_column(String)
    actor_role: Mapped[str | None] = mapped_column(String)
    action: Mapped[str] = mapped_column(Text)
    old_value: Mapped[Any | None] = mapped_column(JSONB)
    new_value: Mapped[Any | None] = mapped_column(JSONB)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversation(UUIDPk, Timestamps, Base):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, server_default="active")


class ConversationMessage(UUIDPk, Base):
    __tablename__ = "conversation_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text, server_default="")
    message_type: Mapped[str] = mapped_column(String, server_default="text")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attachment(UUIDPk, Base):
    __tablename__ = "attachments"

    bucket: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    knowledge_article_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_articles.id"))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
