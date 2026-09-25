"""OpenTelemetry → Axiom.

Traces and logs are exported over OTLP/HTTP to Axiom when AXIOM_TOKEN is set.
Instrumented: FastAPI requests, SQLAlchemy queries, outbound httpx calls
(Supabase Auth/Storage, the LiteLLM proxy, Upstash REST), plus our own spans for
agent runs, LLM calls, investigations and ticket workflow events.

Never recorded: prompts, model outputs, message bodies, credentials. Span
attributes we set go through `safe_attributes`, which drops sensitive keys.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor, SpanExporter
from opentelemetry.trace import Span, Status, StatusCode

from app.config import Settings
from app.core.redaction import is_sensitive_key, scrub, scrub_string

TRACER_NAME = "nexa"
_log = logging.getLogger(__name__)


@dataclass
class TelemetryHandle:
    tracer_provider: TracerProvider
    logger_provider: Any = None
    extra_exporters: list[SpanExporter] = field(default_factory=list)

    def shutdown(self) -> None:
        try:
            self.tracer_provider.shutdown()
        finally:
            if self.logger_provider is not None:
                self.logger_provider.shutdown()


class _RedactingFilter(logging.Filter):
    """Scrub stdlib log records before the OTLP handler exports them."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, dict):
            record.msg = scrub(record.msg)
        elif isinstance(record.msg, str):
            record.msg = scrub_string(record.msg)
        if record.args:
            record.args = tuple(scrub(a) for a in record.args) if isinstance(record.args, tuple) else scrub(record.args)
        return True


def setup_telemetry(settings: Settings, *, span_exporter: SpanExporter | None = None) -> TelemetryHandle:
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )
    provider = TracerProvider(resource=resource)
    handle = TelemetryHandle(tracer_provider=provider)

    if span_exporter is not None:  # tests
        provider.add_span_processor(SimpleSpanProcessor(span_exporter))
        handle.extra_exporters.append(span_exporter)

    if settings.axiom_configured:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        base = f"https://{settings.axiom_domain}"
        headers = {
            "Authorization": f"Bearer {settings.axiom_token.get_secret_value()}",
            "X-Axiom-Dataset": settings.axiom_dataset,
        }
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{base}/v1/traces", headers=headers)))

        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{base}/v1/logs", headers=headers))
        )
        set_logger_provider(logger_provider)
        otel_handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        otel_handler.addFilter(_RedactingFilter())
        otel_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, structlog.processors.JSONRenderer()],
                foreign_pre_chain=[structlog.stdlib.add_log_level, structlog.processors.TimeStamper(fmt="iso", utc=True)],
            )
        )
        otel_handler.set_name("nexa-otlp")
        logging.getLogger().addHandler(otel_handler)
        handle.logger_provider = logger_provider
        _log.info("telemetry.axiom_export_enabled", extra={"dataset": settings.axiom_dataset})

    if settings.otel_console_export:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument(tracer_provider=provider)
    return handle


def instrument_fastapi(app: Any, handle: TelemetryHandle) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=handle.tracer_provider,
        excluded_urls="health,health/ready",
        # Never capture request/response headers (Authorization lives there).
        http_capture_headers_server_request=[],
        http_capture_headers_server_response=[],
    )


def instrument_sqlalchemy(engine: Any, handle: TelemetryHandle) -> None:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    # Statement text is parameterised (no values), so it is safe to record.
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine, tracer_provider=handle.tracer_provider, enable_commenter=False)


def tracer() -> trace.Tracer:
    return trace.get_tracer(TRACER_NAME)


def safe_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in attributes.items():
        if value is None or is_sensitive_key(key.split(".")[-1]):
            continue
        if isinstance(value, (str, bool, int, float)):
            out[key] = scrub_string(value) if isinstance(value, str) else value
        else:
            out[key] = scrub_string(str(value))
    return out


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    """Start a span with scrubbed attributes; records exceptions and error status."""
    with tracer().start_as_current_span(name, attributes=safe_attributes(attributes)) as current:
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise


def set_span_attributes(current: Span, **attributes: Any) -> None:
    current.set_attributes(safe_attributes(attributes))


def current_trace_id() -> str | None:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx and ctx.is_valid else None
