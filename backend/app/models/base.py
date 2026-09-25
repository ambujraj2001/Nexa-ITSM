"""Declarative base. The schema itself is owned by `supabase/migrations`; these
models mirror it (they never create tables)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, FetchedValue, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    # Pull server-generated values (defaults, trigger-set columns) back on
    # INSERT/UPDATE via RETURNING, so objects are never stale after a flush.
    __mapper_args__ = {"eager_defaults": True}


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Maintained by the set_updated_at() trigger.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=FetchedValue()
    )
