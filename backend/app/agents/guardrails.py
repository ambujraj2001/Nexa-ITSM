"""The V1 human-execution boundary, enforced in code.

Four layers keep Nexa's agents on the "investigate and recommend" side:

1. Build-time check — `assert_read_only_tools` refuses to build an agent whose
   tools look like actions (restart/delete/modify/run/execute…). Nexa's tools
   are all read-only lookups.
2. Deep Agents harness profile — removes the built-in `execute`, filesystem and
   `task` subagent tools for every model served through LiteLLM.
3. `HumanExecutionBoundary` middleware — an allowlist applied on every model
   call *and* every tool call, so a tool not declared by Nexa can neither be
   offered to the model nor run, even if a future library version adds one.
4. Output sanitisation — strips reasoning-trace markup and rewrites any claim
   that an action was performed; plans are phrased as work for an engineer.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

FORBIDDEN_TOOL_NAMES = frozenset(
    {
        "restart_server",
        "delete_resource",
        "modify_production_config",
        "run_production_command",
        "execute",
        "shell",
        "bash",
        "run_command",
        "write_file",
        "edit_file",
    }
)
_ACTION_VERBS = re.compile(
    r"^(restart|reboot|shutdown|stop|start|delete|drop|remove|kill|terminate|deploy|rollback|"
    r"modify|update|set|patch|apply|write|edit|execute|exec|run|create_user|grant|revoke|rotate|push)(_|$)",
    re.IGNORECASE,
)
_READ_ONLY_PREFIXES = ("search_", "get_", "list_", "recommend_", "lookup_")

DEEPAGENT_BUILTIN_TOOLS = frozenset({"ls", "read_file", "write_file", "edit_file", "glob", "grep", "execute", "task"})


class UnsafeToolError(RuntimeError):
    pass


def assert_read_only_tools(tools: Iterable[Any]) -> list[str]:
    names: list[str] = []
    for tool in tools:
        name = getattr(tool, "name", None) or getattr(tool, "__name__", "")
        if name in FORBIDDEN_TOOL_NAMES or _ACTION_VERBS.match(name) or not name.startswith(_READ_ONLY_PREFIXES):
            raise UnsafeToolError(f"Tool '{name}' is not allowed in V1: agents may only investigate, never act.")
        names.append(name)
    return names


def _tool_name(tool: Any) -> str | None:
    if isinstance(tool, dict):
        return tool.get("name") or (tool.get("function") or {}).get("name")
    return getattr(tool, "name", None)


class HumanExecutionBoundary(AgentMiddleware):
    """Allowlist Nexa's own read-only tools on every model and tool call."""

    def __init__(self, allowed: Iterable[str]) -> None:
        super().__init__()
        self.allowed = frozenset(allowed)

    @property
    def name(self) -> str:  # type: ignore[override]
        return "NexaHumanExecutionBoundary"

    def _filter(self, request: Any) -> Any:
        tools = [t for t in request.tools if _tool_name(t) in self.allowed]
        return request.override(tools=tools) if len(tools) != len(request.tools) else request

    def wrap_model_call(self, request, handler):  # type: ignore[no-untyped-def]
        return handler(self._filter(request))

    async def awrap_model_call(self, request, handler):  # type: ignore[no-untyped-def]
        return await handler(self._filter(request))

    def _blocked(self, request: Any) -> ToolMessage | None:
        call = request.tool_call
        if call.get("name") in self.allowed:
            return None
        return ToolMessage(
            content="This tool is not available. Nexa can investigate and recommend, but engineers perform all actions.",
            tool_call_id=call.get("id", ""),
            name=call.get("name", "unknown"),
            status="error",
        )

    def wrap_tool_call(self, request, handler):  # type: ignore[no-untyped-def]
        return self._blocked(request) or handler(request)

    async def awrap_tool_call(self, request, handler):  # type: ignore[no-untyped-def]
        return self._blocked(request) or await handler(request)


_profile_registered = False


def register_harness_profile() -> None:
    """Strip Deep Agents' shell/filesystem/subagent tools for LiteLLM-served models."""
    global _profile_registered
    if _profile_registered:
        return
    from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile

    register_harness_profile(
        "litellm",
        HarnessProfile(
            excluded_tools=DEEPAGENT_BUILTIN_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    _profile_registered = True


# ── output sanitisation ────────────────────────────────────────────────────

_THINK_BLOCKS = re.compile(r"<(think|thinking|reasoning|scratchpad)>.*?</\1>", re.IGNORECASE | re.DOTALL)
_EXECUTION_CLAIM = re.compile(
    r"\b(I|we|Nexa|the (AI|assistant|system))\s+(have\s+|has\s+|just\s+)?"
    r"(restarted|rebooted|deleted|removed|renewed|reset|changed|modified|updated|deployed|rotated|fixed|applied|executed|ran|granted|revoked|reissued)\b",
    re.IGNORECASE,
)


def strip_reasoning(text: str | None) -> str | None:
    if text is None:
        return None
    return _THINK_BLOCKS.sub("", text).strip()


def contains_execution_claim(text: str | None) -> bool:
    return bool(text and _EXECUTION_CLAIM.search(text))


def neutralise_execution_claims(text: str | None) -> str | None:
    """Rewrite 'I restarted X' into a recommendation; V1 AI never acts."""
    text = strip_reasoning(text)
    if not text or not contains_execution_claim(text):
        return text
    return _EXECUTION_CLAIM.sub(lambda m: f"an engineer may need to verify whether it was {m.group(4).lower()}", text)


def clean_list(items: Iterable[str] | None, *, limit: int, max_len: int = 240) -> list[str]:
    out: list[str] = []
    for item in items or []:
        cleaned = neutralise_execution_claims(str(item)) or ""
        cleaned = cleaned.strip()[:max_len]
        if cleaned and cleaned not in out:
            out.append(cleaned)
        if len(out) >= limit:
            break
    return out
