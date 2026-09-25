"""Deterministic stand-ins for the model layer.

`FakeLLM` replaces ModelRouter.structured() for direct calls (triage, drafts…).
`FakeAgentModel` is a real LangChain chat model that drives Deep Agents graphs:
on its first turn it calls a read-only tool, then it returns the structured
output tool call for whichever schema the agent bound. It also records every
tool name it was offered, so tests can assert what the model could see.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import BaseModel, Field

from app.infrastructure.litellm import ModelCallInfo

_ids = itertools.count(1)


class FakeLLM:
    """outputs: schema class name → dict | BaseModel | callable(messages) → dict."""

    def __init__(self, outputs: dict[str, Any] | None = None, fail: set[str] | None = None) -> None:
        self.outputs = outputs or {}
        self.fail = fail or set()
        self.calls: list[tuple[str, str]] = []

    async def structured(self, task: str, messages: list[dict[str, Any]], schema: type[BaseModel], **_: Any) -> tuple[BaseModel, ModelCallInfo]:
        self.calls.append((task, schema.__name__))
        if schema.__name__ in self.fail or task in self.fail:
            from app.core.errors import AIUnavailable

            raise AIUnavailable("fake failure")
        value = self.outputs[schema.__name__]
        if callable(value):
            value = value(messages)
        if isinstance(value, BaseModel):
            value = value.model_dump()
        return schema.model_validate(value), ModelCallInfo(model=f"fake-{task}", duration_ms=1)


class FakeAgentModel(BaseChatModel):
    canned: dict[str, Any] = Field(default_factory=dict)  # schema name → args (or callable(messages) → args)
    first_tool: dict[str, tuple[str, dict[str, Any]]] = Field(default_factory=dict)  # schema → (tool, args)
    offered: list[list[str]] = Field(default_factory=list)
    bound: list[str] = Field(default_factory=list)
    fail_with: str | None = None
    force_first_tool: bool = False  # call first_tool even if it wasn't offered (simulates a hallucinated tool)

    @property
    def _llm_type(self) -> str:
        return "fake-agent"

    def _get_ls_params(self, stop: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        # Look like a LiteLLM model so Nexa's Deep Agents harness profile applies.
        return {"ls_provider": "litellm", "ls_model_name": "fake"}

    def bind_tools(self, tools: Any, **kwargs: Any) -> "FakeAgentModel":  # type: ignore[override]
        names = []
        for tool in tools:
            name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None) or getattr(tool, "__name__", None)
            if isinstance(tool, dict) and not name:
                name = (tool.get("function") or {}).get("name")
            names.append(name)
        self.offered.append(names)
        clone = self.model_copy()
        clone.bound = names
        clone.offered = self.offered  # share the log
        return clone

    def _respond(self, messages: list[BaseMessage]) -> AIMessage:
        if self.fail_with:
            raise RuntimeError(self.fail_with)
        schema = next((n for n in self.bound if n in self.canned), None)
        if schema is None:
            return AIMessage(content="no structured tool bound")
        called = any(isinstance(m, ToolMessage) for m in messages)
        if schema in self.first_tool and not called:
            tool, args = self.first_tool[schema]
            if tool in self.bound or self.force_first_tool:
                return AIMessage(content="", tool_calls=[{"name": tool, "args": args, "id": f"call_{next(_ids)}", "type": "tool_call"}])
        args = self.canned[schema]
        if callable(args):
            args = args(messages)
        return AIMessage(content="", tool_calls=[{"name": schema, "args": args, "id": f"call_{next(_ids)}", "type": "tool_call"}], usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120})

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._respond(messages))])

    async def _agenerate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)


def agent_factory(model: FakeAgentModel) -> Callable[[str, dict[str, Any]], FakeAgentModel]:
    return lambda task, metadata: model


# ── canned AI outputs for the VPN demo scenario ────────────────────────────

VPN_TRIAGE = {
    "intent": "report_issue",
    "reply": "Sorry your VPN is down — that sounds like an authentication problem.",
    "ticket_type": "incident",
    "title": "VPN connection failure",
    "summary": "VPN fails to connect since this morning.",
    "category": "network",
    "subcategory": "vpn",
    "impact": "individual",
    "urgency": "critical",
    "suggested_priority": "P2",
    "service_hint": "VPN",
    "likely_cause": "The VPN client certificate may have expired.",
    "confidence": 0.7,
    "signals": [{"label": "Error", "value": "CERT_AUTHORITY_INVALID", "kind": "error"}],
    "needs_clarification": False,
}

VPN_DIAGNOSIS = {
    "summary": "VPN authentication fails with a certificate error.",
    "diagnosis": "The VPN client certificate may have expired after the macOS update.",
    "confidence": 0.86,
    "evidence": [
        {"source_type": "knowledge_article", "reference": "KB-TEST", "summary": "Article describes CERT_AUTHORITY_INVALID from expired client certificates."},
        {"source_type": "historical_incident", "reference": "INC-99999", "summary": "Invented incident the tools never returned."},
        {"source_type": "user_report", "reference": None, "summary": "Requester reports CERT_AUTHORITY_INVALID."},
    ],
    "hypotheses": [{"cause": "Cached credentials after password change", "likelihood": "low", "how_to_verify": "Check auth log for bad password"}],
    "rationale": "The error text matches the certificate-expiry article.",
    "missing_information": ["Did the error start right after an OS update?"],
    "recommended_team": "Network",
}

VPN_PLAN = {
    "steps": [
        {"description": "Check VPN client authentication status", "details": "Look for certificate errors in AnyConnect."},
        {"description": "Verify certificate validity", "technical_details": "security find-certificate -a -c vpn-client -p | openssl x509 -noout -enddate"},
        {"description": "I have restarted the VPN gateway", "details": "Nexa restarted the gateway."},
        {"description": "Re-push VPN certificate profile via MDM"},
        {"description": "Test user authentication"},
    ]
}
