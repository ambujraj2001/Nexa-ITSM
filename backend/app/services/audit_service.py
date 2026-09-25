"""Audit trail: every meaningful state change records who, what, when, old → new,
and whether a person (user), the AI or the system did it."""

from __future__ import annotations

import uuid
from typing import Any

from app.core.context import current_request_id
from app.domain.enums import ActorType
from app.domain.policies import Principal
from app.infrastructure.telemetry import current_trace_id
from app.models import AuditEvent
from app.repositories.audit_repository import AuditRepository


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)


class AuditService:
    def __init__(self, repo: AuditRepository) -> None:
        self.repo = repo

    async def record(
        self,
        action: str,
        *,
        actor: Principal | None = None,
        actor_type: ActorType | None = None,
        ticket_id: uuid.UUID | None = None,
        entity_type: str = "ticket",
        entity_id: uuid.UUID | None = None,
        old_value: Any = None,
        new_value: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        resolved_type = actor_type or (ActorType.USER if actor else ActorType.SYSTEM)
        meta = dict(metadata or {})
        if (rid := current_request_id()) is not None:
            meta.setdefault("request_id", rid)
        if (tid := current_trace_id()) is not None:
            meta.setdefault("trace_id", tid)
        event = AuditEvent(
            ticket_id=ticket_id,
            entity_type=entity_type,
            entity_id=entity_id or ticket_id,
            actor_id=actor.profile_id if actor and resolved_type == ActorType.USER else None,
            actor_type=resolved_type.value,
            actor_role=actor.role.value if actor and resolved_type == ActorType.USER else None,
            action=action,
            old_value=_jsonable(old_value),
            new_value=_jsonable(new_value),
            metadata_=_jsonable(meta),
        )
        return await self.repo.add(event)
