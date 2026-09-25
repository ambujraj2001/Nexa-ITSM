from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class Service(UUIDPk, Timestamps, Base):
    __tablename__ = "services"

    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    owner_team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"))
    criticality: Mapped[str] = mapped_column(String, server_default="medium")


class Asset(UUIDPk, Timestamps, Base):
    __tablename__ = "assets"

    name: Mapped[str] = mapped_column(Text)
    asset_type: Mapped[str] = mapped_column(String)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default="{}")


class SlaPolicy(UUIDPk, Timestamps, Base):
    __tablename__ = "sla_policies"

    name: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String)
    response_time_minutes: Mapped[int] = mapped_column(Integer)
    resolution_time_minutes: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")


class AssignmentRule(UUIDPk, Timestamps, Base):
    __tablename__ = "assignment_rules"

    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    subcategory: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String)
    ticket_type: Mapped[str | None] = mapped_column(String)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id"))
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id"))
    support_level: Mapped[str] = mapped_column(String, server_default="L1")
    sort_order: Mapped[int] = mapped_column(Integer, server_default="100")
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")


class AiConfiguration(Timestamps, Base):
    __tablename__ = "ai_configuration"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default="1")
    ai_triage_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    ai_diagnosis_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    resolution_plans_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    automatic_actions_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    human_approval_required: Mapped[bool] = mapped_column(Boolean, server_default="true")
    confidence_threshold: Mapped[Decimal] = mapped_column(Numeric(3, 2), server_default="0.80")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"))


class Integration(UUIDPk, Timestamps, Base):
    __tablename__ = "integrations"

    provider: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    status: Mapped[str] = mapped_column(String, server_default="not_configured")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    secret_ref: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class KnowledgeSource(UUIDPk, Timestamps, Base):
    __tablename__ = "knowledge_sources"

    name: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(UUIDPk, Base):
    __tablename__ = "agent_runs"

    ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    agent_name: Mapped[str] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, server_default="running")
    error_code: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[int] = mapped_column(Integer, server_default="0")
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default="{}")
