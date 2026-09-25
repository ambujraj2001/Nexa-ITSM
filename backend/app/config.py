"""Application settings.

Everything is read from the environment (and `backend/.env` in local
development). Secrets are `SecretStr` so they never appear in reprs, logs or
tracebacks. Nothing here is ever sent to the browser.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent

ModelTask = Literal[
    "triage",
    "assistant",
    "summary",
    "diagnosis",
    "resolution_plan",
    "escalation_analysis",
    "copilot",
]

# Which tier each task uses unless overridden with NEXA_MODEL_<TASK>.
TASK_TIERS: dict[str, Literal["fast", "strong"]] = {
    "triage": "fast",
    "assistant": "fast",
    "summary": "fast",
    "diagnosis": "strong",
    "resolution_plan": "strong",
    "escalation_analysis": "strong",
    "copilot": "strong",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production", "test"] = "development"
    app_version: str = "0.1.0"
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = ""
    log_level: str = "INFO"

    # ── Supabase ─────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")
    supabase_db_url: SecretStr = SecretStr("")
    supabase_jwt_secret: SecretStr = SecretStr("")

    # ── LiteLLM ──────────────────────────────────────────────────────────
    litellm_base_url: str = ""
    litellm_api_key: SecretStr = SecretStr("")
    nexa_model_fast: str = ""
    nexa_model_strong: str = ""
    nexa_model_embedding: str = ""
    # Direct provider key for embeddings named "mistral/<model>" (bypasses the LiteLLM proxy).
    mistral_api_key: SecretStr = SecretStr("")
    nexa_model_fallbacks: str = ""
    nexa_model_triage: str = ""
    nexa_model_assistant: str = ""
    nexa_model_summary: str = ""
    nexa_model_diagnosis: str = ""
    nexa_model_resolution_plan: str = ""
    nexa_model_escalation_analysis: str = ""
    nexa_model_copilot: str = ""
    nexa_embedding_dimensions: int = 1536
    llm_timeout_seconds: float = 60.0

    # ── Upstash Redis ────────────────────────────────────────────────────
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: SecretStr = SecretStr("")

    # ── Observability ────────────────────────────────────────────────────
    axiom_token: SecretStr = SecretStr("")
    axiom_dataset: str = "nexa"
    axiom_domain: str = "api.axiom.co"
    otel_service_name: str = "nexa-backend"
    otel_console_export: bool = False

    # ── Behaviour tunables ───────────────────────────────────────────────
    investigation_timeout_seconds: int = 600
    stale_investigation_minutes: int = 15
    due_soon_minutes: int = 60
    assistant_messages_per_minute: int = 20
    copilot_messages_per_minute: int = 20
    ai_drafts_per_minute: int = 10
    max_upload_bytes: int = 10 * 1024 * 1024

    # ── Development seed ─────────────────────────────────────────────────
    seed_user_password: SecretStr = SecretStr("")

    @field_validator("supabase_url", "litellm_base_url", "backend_url", "frontend_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.strip().rstrip("/")

    # ── Derived values ───────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def allowed_origins(self) -> list[str]:
        extra = [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        return sorted({self.frontend_url, *extra})

    @property
    def database_configured(self) -> bool:
        return bool(self.supabase_db_url.get_secret_value())

    @property
    def async_database_url(self) -> str:
        """The Supabase connection string, rewritten for SQLAlchemy + asyncpg."""
        url = self.supabase_db_url.get_secret_value().strip()
        for prefix in ("postgresql+asyncpg://", "postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix):]
        return url

    @property
    def uses_transaction_pooler(self) -> bool:
        """Supavisor transaction mode (port 6543) can't use prepared statements."""
        url = self.supabase_db_url.get_secret_value()
        return ":6543/" in url or "pgbouncer=true" in url

    @property
    def supabase_auth_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @property
    def supabase_admin_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key.get_secret_value())

    @property
    def llm_configured(self) -> bool:
        return bool(self.nexa_model_fast or self.nexa_model_strong)

    @property
    def embeddings_configured(self) -> bool:
        return bool(self.nexa_model_embedding)

    @property
    def redis_configured(self) -> bool:
        return bool(self.upstash_redis_rest_url and self.upstash_redis_rest_token.get_secret_value())

    @property
    def axiom_configured(self) -> bool:
        return bool(self.axiom_token.get_secret_value() and self.axiom_dataset)

    @property
    def model_fallbacks(self) -> list[str]:
        return [m.strip() for m in self.nexa_model_fallbacks.split(",") if m.strip()]

    def model_for_task(self, task: str) -> str:
        """Resolve the configured model alias for an AI task (see TASK_TIERS)."""
        override = getattr(self, f"nexa_model_{task}", "") or ""
        if override:
            return override
        tier = TASK_TIERS.get(task, "fast")
        if tier == "strong":
            return self.nexa_model_strong or self.nexa_model_fast
        return self.nexa_model_fast or self.nexa_model_strong


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()

