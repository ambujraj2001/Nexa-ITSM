"""Structured logging.

JSON logs in deployed environments, readable console output locally. Every
event carries request/trace correlation ids and passes through secret redaction.
Standard-library loggers (uvicorn, SQLAlchemy, httpx, LiteLLM) share the same
pipeline, so nothing bypasses the scrubber.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from opentelemetry import trace

from app.core.context import request_id_var, user_id_var
from app.core.redaction import scrub


def _add_correlation(_: Any, __: str, event: dict[str, Any]) -> dict[str, Any]:
    if (rid := request_id_var.get()) and "request_id" not in event:
        event["request_id"] = rid
    if (uid := user_id_var.get()) and "user_id" not in event:
        event["user_id"] = uid
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx and ctx.is_valid:
        event.setdefault("trace_id", format(ctx.trace_id, "032x"))
        event.setdefault("span_id", format(ctx.span_id, "016x"))
    return event


def _redact(_: Any, __: str, event: dict[str, Any]) -> dict[str, Any]:
    return scrub(event)


def configure_logging(level: str = "INFO", *, json_output: bool = True) -> None:
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_correlation,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _redact,
    ]
    renderer: Any = structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.set_name("nexa-console")

    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if h.get_name() not in {"nexa-console"}]
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Quiet, and never let third parties log request/response bodies.
    for noisy in ("httpx", "httpcore", "LiteLLM", "litellm", "LiteLLM Router", "LiteLLM Proxy", "urllib3", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    for uv in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(uv)
        lg.handlers = []
        lg.propagate = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
