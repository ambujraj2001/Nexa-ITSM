"""Building and running Nexa's Deep Agents.

`build_agent` is the only way agents are constructed, so every agent gets the
human-execution guardrails. `run_agent` wraps an invocation with a trace span
and an `agent_runs` record (identifiers, model, outcome, timing, token counts —
never prompts, messages or reasoning).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, TypeVar

from deepagents import create_deep_agent
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.agents.guardrails import HumanExecutionBoundary, assert_read_only_tools, register_harness_profile
from app.core.errors import AIUnavailable
from app.core.logging import get_logger
from app.infrastructure.telemetry import span
from app.models import AgentRun
from app.repositories.audit_repository import AuditRepository
from app.services.base import utcnow

log = get_logger(__name__)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


def build_agent(*, model: Any, tools: list[Any], system_prompt: str, response_format: type[BaseModel], name: str) -> Any:
    register_harness_profile()
    allowed = assert_read_only_tools(tools)
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[
            # Minimal virtual (in-memory) filesystem; its tools are excluded anyway.
            FilesystemMiddleware(tools=["read_file"]),
            HumanExecutionBoundary(allowed),
        ],
        response_format=ToolStrategy(response_format),
        name=name,
    )


@dataclass
class AgentRunResult:
    output: Any
    run_id: uuid.UUID
    tool_calls: int
    duration_ms: int


async def run_agent(
    agent: Any,
    *,
    messages: list[dict[str, Any]],
    schema: type[SchemaT],
    audit: AuditRepository,
    agent_name: str,
    operation: str,
    model_label: str | None,
    ticket_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    tool_calls_counter: Any = None,
    recursion_limit: int = 30,
    timeout_seconds: float = 180.0,
) -> AgentRunResult:
    run = AgentRun(
        ticket_id=ticket_id, conversation_id=conversation_id, agent_name=agent_name, operation=operation, model=model_label, status="running"
    )
    await audit.add_run(run)
    started = time.perf_counter()
    attributes = {
        "nexa.agent": agent_name,
        "nexa.agent_run_id": str(run.id),
        "nexa.operation": operation,
        "nexa.ticket_id": str(ticket_id) if ticket_id else None,
        "gen_ai.request.model": model_label,
    }
    with span("agent.run", **attributes) as current:
        try:
            result = await asyncio.wait_for(
                agent.ainvoke(
                    {"messages": messages},
                    config={
                        "recursion_limit": recursion_limit,
                        "run_name": agent_name,
                        "metadata": {"agent_run_id": str(run.id), "ticket_id": str(ticket_id) if ticket_id else None},
                    },
                ),
                timeout=timeout_seconds,
            )
            output = result.get("structured_response") if isinstance(result, dict) else None
            if not isinstance(output, schema):
                if isinstance(output, dict):
                    output = schema.model_validate(output)
                else:
                    raise AIUnavailable(f"{agent_name} returned no structured result.")
            input_tokens = output_tokens = 0
            for message in result.get("messages", []):
                usage = getattr(message, "usage_metadata", None) if isinstance(message, AIMessage) else None
                if usage:
                    input_tokens += int(usage.get("input_tokens") or 0)
                    output_tokens += int(usage.get("output_tokens") or 0)
            run.status = "completed"
            run.input_tokens, run.output_tokens = input_tokens or None, output_tokens or None
            return AgentRunResult(output=output, run_id=run.id, tool_calls=getattr(tool_calls_counter, "calls", 0), duration_ms=int((time.perf_counter() - started) * 1000))
        except Exception as exc:
            run.status = "failed"
            run.error_code = type(exc).__name__
            current.set_attribute("nexa.agent.error", type(exc).__name__)
            log.warning("agent.run_failed", agent=agent_name, agent_run_id=str(run.id), error=type(exc).__name__)
            if isinstance(exc, AIUnavailable):
                raise
            raise AIUnavailable(f"{agent_name} could not complete.") from exc
        finally:
            run.completed_at = utcnow()
            run.duration_ms = int((time.perf_counter() - started) * 1000)
            run.tool_calls = getattr(tool_calls_counter, "calls", 0)
            current.set_attribute("nexa.agent.tool_calls", run.tool_calls)
            current.set_attribute("nexa.agent.status", run.status)
