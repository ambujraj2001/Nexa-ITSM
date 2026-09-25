"""Nexa API — FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api import admin, assignments, catalog, conversations, dashboards, knowledge, me, settings as settings_api, tickets
from app.config import Settings, get_settings
from app.container import Container
from app.core.context import new_request_id, request_id_var, user_id_var
from app.core.errors import AppError, RateLimited
from app.core.logging import configure_logging, get_logger
from app.core.security import TokenVerifier
from app.infrastructure.litellm import ModelRouter, install_litellm_telemetry
from app.infrastructure.redis import create_store
from app.infrastructure.supabase import SupabaseAdmin
from app.infrastructure.telemetry import instrument_fastapi, instrument_sqlalchemy, setup_telemetry
from app.jobs import BackgroundJobs

log = get_logger("nexa")


def build_container(settings: Settings, *, inline_jobs: bool = False, database: object | None = None) -> Container:
    from app.infrastructure.db import Database

    supabase = SupabaseAdmin(settings)
    if database is None and settings.database_configured:
        database = Database(settings)
    return Container(
        settings=settings,
        store=create_store(settings),
        models=ModelRouter(settings),
        supabase=supabase,
        verifier=TokenVerifier(settings, supabase),
        jobs=BackgroundJobs(inline=inline_jobs),
        database=database,  # type: ignore[arg-type]
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container: Container = app.state.container
    if container.database is not None and container.telemetry is not None:
        instrument_sqlalchemy(container.database.engine, container.telemetry)  # type: ignore[attr-defined]
    log.info(
        "nexa.startup",
        environment=container.settings.app_env,
        database=container.settings.database_configured,
        ai=container.ai_available,
        embeddings=container.settings.embeddings_configured,
        redis=container.store.backend_name,
        telemetry=container.settings.axiom_configured,
    )
    if container.database is not None and container.extras.get("recover_on_startup", True):
        try:
            from app.services.base import Repos
            from app.services.investigation_service import InvestigationService

            async with container.db.session() as session:
                recovered = await InvestigationService(Repos.for_session(session), container).recover_stale()
            if recovered:
                log.info("investigation.recovered_stale", count=recovered)
        except Exception as exc:  # noqa: BLE001 — never block startup on recovery
            log.warning("investigation.recovery_failed", error=type(exc).__name__)
    try:
        yield
    finally:
        await container.jobs.shutdown()
        await container.store.close()
        await container.supabase.close()
        await container.verifier.close()
        if container.database is not None:
            await container.database.dispose()  # type: ignore[attr-defined]
        if container.telemetry is not None:
            container.telemetry.shutdown()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if incoming.isalnum() and len(incoming) <= 64 else new_request_id()
        token = request_id_var.set(rid)
        user_token = user_id_var.set(None)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
            user_id_var.reset(user_token)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        return response


def _error(status: int, code: str, message: str, details: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}, "request_id": request_id_var.get()},
        headers=headers,
    )


def create_app(settings: Settings | None = None, *, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.app_env in ("production", "staging"))
    telemetry = setup_telemetry(settings) if container is None else container.telemetry
    install_litellm_telemetry()

    app = FastAPI(
        title="Nexa API",
        version=settings.app_version,
        description="AI-native IT service management. AI investigates; humans resolve.",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
    )
    app.state.container = container or build_container(settings)
    if app.state.container.telemetry is None:
        app.state.container.telemetry = telemetry

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        max_age=600,
    )

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, RateLimited) else None
        if exc.status_code >= 500:
            log.warning("request.app_error", code=exc.code, status=exc.status_code)
        return _error(exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [{"loc": [str(p) for p in e.get("loc", [])], "message": e.get("msg", "Invalid value")} for e in exc.errors()]
        return _error(422, "validation_failed", "Some fields are invalid.", {"fields": fields})

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("request.unhandled_error", error=type(exc).__name__)
        return _error(500, "internal_error", "Something went wrong on our side. Please try again.")

    for module in (me, conversations, tickets, dashboards, knowledge, settings_api, assignments, admin, catalog):
        app.include_router(module.router)

    if telemetry is not None:
        instrument_fastapi(app, telemetry)
    return app


app = create_app()
