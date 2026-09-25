"""LiteLLM: the only path from Nexa to a language model.

Business logic asks for a *task* ("triage", "diagnosis", …); `ModelRouter`
maps it to a configured model alias (fast vs strong tier, per-task overrides,
fallbacks). With LITELLM_BASE_URL set, every call goes to your LiteLLM proxy as
`litellm_proxy/<alias>` using LITELLM_API_KEY; otherwise aliases are passed to
the LiteLLM SDK directly (provider keys from the environment).

Telemetry records model, task, latency, token counts and outcome — never
prompts or completions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

import litellm
from litellm.integrations.custom_logger import CustomLogger
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.core.errors import AIUnavailable
from app.core.logging import get_logger
from app.infrastructure.telemetry import TRACER_NAME, safe_attributes, span

log = get_logger(__name__)
SchemaT = TypeVar("SchemaT", bound=BaseModel)

# Global, process-wide LiteLLM hygiene.
litellm.drop_params = True  # drop params a provider doesn't support instead of erroring
litellm.turn_off_message_logging = True  # callbacks never see message content
litellm.suppress_debug_info = True
if hasattr(litellm, "telemetry"):
    litellm.telemetry = False


@dataclass(frozen=True)
class ModelConfig:
    task: str
    alias: str
    litellm_model: str
    api_base: str | None
    api_key: str | None

    def call_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"model": self.litellm_model}
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        return kwargs


@dataclass(frozen=True)
class ModelCallInfo:
    model: str
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


class _TelemetryCallback(CustomLogger):
    """Emits an `llm.call` span per LiteLLM request with metadata only."""

    def _emit(self, kwargs: dict[str, Any], response_obj: Any, start: datetime, end: datetime, ok: bool) -> None:
        tracer = trace.get_tracer(TRACER_NAME)
        usage = getattr(response_obj, "usage", None) if ok else None
        metadata = (kwargs.get("litellm_params") or {}).get("metadata") or {}
        attributes = safe_attributes(
            {
                "gen_ai.system": "litellm",
                "gen_ai.request.model": kwargs.get("model"),
                "nexa.ai.task": metadata.get("nexa_task"),
                "nexa.ticket_id": metadata.get("ticket_id"),
                "nexa.agent_run_id": metadata.get("agent_run_id"),
                "gen_ai.usage.input_tokens": getattr(usage, "prompt_tokens", None),
                "gen_ai.usage.output_tokens": getattr(usage, "completion_tokens", None),
                "llm.call_type": kwargs.get("call_type"),
                "llm.duration_ms": int((end - start).total_seconds() * 1000),
            }
        )
        current = tracer.start_span("llm.call", start_time=int(start.timestamp() * 1e9), attributes=attributes)
        if not ok:
            exc = kwargs.get("exception")
            current.set_status(Status(StatusCode.ERROR, type(exc).__name__ if exc else "error"))
        current.end(end_time=int(end.timestamp() * 1e9))

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):  # type: ignore[override]
        self._emit(kwargs, response_obj, start_time, end_time, ok=True)

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):  # type: ignore[override]
        self._emit(kwargs, response_obj, start_time, end_time, ok=False)


_callback_installed = False


def install_litellm_telemetry() -> None:
    global _callback_installed
    if not _callback_installed:
        litellm.callbacks = [*(litellm.callbacks or []), _TelemetryCallback()]
        _callback_installed = True


def _structured_instructions(schema: type[BaseModel]) -> str:
    return (
        "Respond with a single JSON object and nothing else. It must validate against this JSON Schema:\n"
        + json.dumps(schema.model_json_schema(), separators=(",", ":"))
    )


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):] if "{" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ── configuration ────────────────────────────────────────────────────
    def _to_litellm_name(self, alias: str) -> str:
        if self._settings.litellm_base_url and not alias.startswith("litellm_proxy/"):
            return f"litellm_proxy/{alias}"
        return alias

    def _config_for_alias(self, task: str, alias: str) -> ModelConfig:
        proxy = bool(self._settings.litellm_base_url)
        return ModelConfig(
            task=task,
            alias=alias,
            litellm_model=self._to_litellm_name(alias),
            api_base=self._settings.litellm_base_url or None,
            api_key=(self._settings.litellm_api_key.get_secret_value() or None) if proxy else None,
        )

    def available(self, task: str = "triage") -> bool:
        return bool(self._settings.model_for_task(task))

    def resolve(self, task: str) -> ModelConfig:
        alias = self._settings.model_for_task(task)
        if not alias:
            raise AIUnavailable("No AI model is configured (set NEXA_MODEL_FAST / NEXA_MODEL_STRONG).")
        return self._config_for_alias(task, alias)

    def candidates(self, task: str) -> list[ModelConfig]:
        primary = self.resolve(task)
        chain = [primary]
        for alias in self._settings.model_fallbacks:
            if alias != primary.alias:
                chain.append(self._config_for_alias(task, alias))
        return chain

    def describe(self) -> dict[str, Any]:
        """Non-secret summary for the settings screen."""
        tasks = ["triage", "assistant", "summary", "diagnosis", "resolution_plan", "escalation_analysis", "copilot"]
        return {
            "gateway": "litellm_proxy" if self._settings.litellm_base_url else "litellm_sdk",
            "configured": self._settings.llm_configured,
            "fast_model": self._settings.nexa_model_fast or None,
            "strong_model": self._settings.nexa_model_strong or None,
            "embedding_model": self._settings.nexa_model_embedding or None,
            "fallback_models": self._settings.model_fallbacks,
            "routes": {t: self._settings.model_for_task(t) or None for t in tasks},
        }

    # ── LangChain model for Deep Agents ──────────────────────────────────
    def chat_model(self, task: str, *, temperature: float = 0.1, max_tokens: int = 2000, alias: str | None = None):  # type: ignore[no-untyped-def]
        from langchain_litellm import ChatLiteLLM

        config = self._config_for_alias(task, alias) if alias else self.resolve(task)
        return ChatLiteLLM(
            model=config.litellm_model,
            api_base=config.api_base,
            api_key=config.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=self._settings.llm_timeout_seconds,
            max_retries=1,
            model_kwargs={"metadata": {"nexa_task": task}},
        )

    # ── Direct completions ───────────────────────────────────────────────
    async def _complete(self, config: ModelConfig, messages: list[dict[str, Any]], **params: Any) -> Any:
        return await litellm.acompletion(
            **config.call_kwargs(),
            messages=messages,
            timeout=self._settings.llm_timeout_seconds,
            num_retries=1,
            **params,
        )

    async def structured(
        self,
        task: str,
        messages: list[dict[str, Any]],
        schema: type[SchemaT],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1500,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[SchemaT, ModelCallInfo]:
        """Structured output validated by Pydantic, with one repair attempt."""
        meta = {"nexa_task": task, **(metadata or {})}
        last_error: Exception | None = None
        for config in self.candidates(task):
            started = time.perf_counter()
            with span("ai.structured_completion", **{"nexa.ai.task": task, "gen_ai.request.model": config.alias}) as current:
                try:
                    response = await self._structured_call(config, messages, schema, temperature, max_tokens, meta)
                    text = response.choices[0].message.content or ""
                    try:
                        parsed = schema.model_validate(_extract_json(text))
                    except (ValueError, ValidationError) as exc:
                        current.add_event("ai.repair_attempt")
                        repair = [
                            *messages,
                            {"role": "assistant", "content": text[:4000]},
                            {"role": "user", "content": f"That output was invalid ({str(exc)[:500]}). Return only the corrected JSON object."},
                        ]
                        response = await self._structured_call(config, repair, schema, temperature, max_tokens, meta)
                        parsed = schema.model_validate(_extract_json(response.choices[0].message.content or ""))
                    usage = getattr(response, "usage", None)
                    return parsed, ModelCallInfo(
                        model=config.alias,
                        duration_ms=int((time.perf_counter() - started) * 1000),
                        input_tokens=getattr(usage, "prompt_tokens", None),
                        output_tokens=getattr(usage, "completion_tokens", None),
                    )
                except (ValueError, ValidationError) as exc:
                    last_error = exc
                    log.warning("ai.structured_output_invalid", task=task, model=config.alias)
                except Exception as exc:  # noqa: BLE001 — provider/network errors → next candidate
                    last_error = exc
                    log.warning("ai.completion_failed", task=task, model=config.alias, error=type(exc).__name__)
        raise AIUnavailable("The AI model could not produce a valid response.") from last_error

    async def _structured_call(
        self,
        config: ModelConfig,
        messages: list[dict[str, Any]],
        schema: type[BaseModel],
        temperature: float,
        max_tokens: int,
        metadata: dict[str, Any],
    ) -> Any:
        json_schema = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema(), "strict": False}}
        try:
            return await self._complete(
                config, messages, response_format=json_schema, temperature=temperature, max_tokens=max_tokens, metadata=metadata
            )
        except (litellm.BadRequestError, litellm.UnsupportedParamsError):
            # Model/proxy without json_schema support: fall back to JSON mode + schema in the prompt.
            fallback = [{"role": "system", "content": _structured_instructions(schema)}, *messages]
            return await self._complete(
                config, fallback, response_format={"type": "json_object"}, temperature=temperature, max_tokens=max_tokens, metadata=metadata
            )

    # ── Embeddings ───────────────────────────────────────────────────────
    @property
    def embeddings_available(self) -> bool:
        return self._settings.embeddings_configured

    async def embed(self, texts: list[str]) -> tuple[list[list[float]], str]:
        """Embed texts into the schema's fixed dimensionality (zero-padding smaller models)."""
        if not self._settings.embeddings_configured:
            raise AIUnavailable("No embedding model is configured.")
        dims = self._settings.nexa_embedding_dimensions
        alias = self._settings.nexa_model_embedding
        if alias.startswith("mistral/") and self._settings.mistral_api_key.get_secret_value():
            config = ModelConfig(task="embedding", alias=alias, litellm_model=alias, api_base=None, api_key=self._settings.mistral_api_key.get_secret_value())
        else:
            config = self._config_for_alias("embedding", alias)
        with span("ai.embedding", **{"gen_ai.request.model": config.alias, "nexa.batch_size": len(texts)}):
            response = await litellm.aembedding(**config.call_kwargs(), input=texts, timeout=self._settings.llm_timeout_seconds)
            vectors = [list(item["embedding"]) for item in response.data]
            if vectors and len(vectors[0]) > dims:
                response = await litellm.aembedding(
                    **config.call_kwargs(), input=texts, dimensions=dims, timeout=self._settings.llm_timeout_seconds
                )
                vectors = [list(item["embedding"]) for item in response.data]
        out: list[list[float]] = []
        for vector in vectors:
            if len(vector) > dims:
                raise AIUnavailable(f"Embedding model returns {len(vector)} dimensions; the schema stores {dims}.")
            out.append(vector + [0.0] * (dims - len(vector)))
        return out, config.alias
