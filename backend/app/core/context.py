"""Per-request correlation identifiers carried through logs and traces."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex


def current_request_id() -> str | None:
    return request_id_var.get()
