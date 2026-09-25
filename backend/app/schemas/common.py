from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PersonRef(Schema):
    id: uuid.UUID
    name: str
    email: str | None = None
    avatar_url: str | None = None
    job_title: str | None = None
    department: str | None = None
    location: str | None = None
    role: str | None = None
    engineer_level: str | None = None
    team_name: str | None = None


class TeamRef(Schema):
    id: uuid.UUID
    name: str


class ServiceRef(Schema):
    id: uuid.UUID
    name: str
    criticality: str


class SlaInfo(Schema):
    state: Literal["on_track", "at_risk", "due_soon", "breached", "met", "missed", "none"]
    label: str
    due_at: datetime | None = None
    response_due_at: datetime | None = None
    remaining_seconds: int | None = None
    policy_name: str | None = None


class Page(Schema, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class OkResponse(Schema):
    ok: bool = True
