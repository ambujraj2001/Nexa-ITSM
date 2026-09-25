"""Process-wide dependencies, built once at startup (see app.main.lifespan)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.config import Settings
from app.core.errors import ServiceUnavailable
from app.core.security import TokenVerifier
from app.infrastructure.cache import JobLock, JsonCache, RateLimiter
from app.infrastructure.db import SessionProvider
from app.infrastructure.litellm import ModelRouter
from app.infrastructure.redis import KeyValueStore
from app.infrastructure.supabase import SupabaseAdmin
from app.infrastructure.telemetry import TelemetryHandle
from app.jobs import BackgroundJobs

# (task, metadata) -> LangChain chat model. Tests inject scripted models here.
ChatModelFactory = Callable[[str, dict[str, Any]], Any]


@dataclass
class Container:
    settings: Settings
    store: KeyValueStore
    models: ModelRouter
    supabase: SupabaseAdmin
    verifier: TokenVerifier
    jobs: BackgroundJobs
    database: SessionProvider | None = None
    telemetry: TelemetryHandle | None = None
    chat_model_factory: ChatModelFactory | None = None
    # Object exposing `structured(task, messages, schema, ...)`; defaults to ModelRouter.
    structured_llm: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def db(self) -> SessionProvider:
        if self.database is None:
            raise ServiceUnavailable("The database is not configured. Set SUPABASE_DB_URL.")
        return self.database

    @property
    def rate_limiter(self) -> RateLimiter:
        return RateLimiter(self.store)

    @property
    def locks(self) -> JobLock:
        return JobLock(self.store)

    @property
    def cache(self) -> JsonCache:
        return JsonCache(self.store)

    def chat_model(self, task: str, **metadata: Any) -> Any:
        if self.chat_model_factory is not None:
            return self.chat_model_factory(task, metadata)
        model = self.models.chat_model(task)
        model.model_kwargs = {**(model.model_kwargs or {}), "metadata": {"nexa_task": task, **metadata}}
        return model

    @property
    def llm(self) -> Any:
        return self.structured_llm or self.models

    @property
    def ai_available(self) -> bool:
        return self.structured_llm is not None or self.chat_model_factory is not None or self.models.available()
