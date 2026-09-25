"""Conversational Deep Agents: the employee knowledge assistant and the engineer copilot."""

from __future__ import annotations

import uuid
from typing import Any

from app.agents import prompts
from app.agents.guardrails import neutralise_execution_claims
from app.agents.runner import build_agent, run_agent
from app.agents.schemas import AssistantDecision, CopilotAnswer, KnowledgeAnswer
from app.agents.skills import skills_index
from app.agents.tools import ToolContext, assistant_agent_tools, assistant_tools, copilot_tools
from app.container import Container
from app.services.base import Repos

NOT_ENOUGH_INFO = "I don't have enough information to confirm that."


async def answer_knowledge_question(
    repos: Repos,
    container: Container,
    *,
    question: str,
    history: list[dict[str, str]],
    requester_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> tuple[KnowledgeAnswer, set[str]]:
    ctx = ToolContext(repos=repos, container=container, requester_id=requester_id)
    agent = build_agent(
        model=container.chat_model("assistant", conversation_id=str(conversation_id)),
        tools=assistant_tools(ctx),
        system_prompt=prompts.ASSISTANT_KNOWLEDGE,
        response_format=KnowledgeAnswer,
        name="nexa-assistant",
    )
    messages: list[dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    messages.append({"role": "user", "content": question})
    result = await run_agent(
        agent,
        messages=messages,
        schema=KnowledgeAnswer,
        audit=repos.audit,
        agent_name="nexa-assistant",
        operation="knowledge_answer",
        model_label=container.settings.model_for_task("assistant") or None,
        conversation_id=conversation_id,
        tool_calls_counter=ctx,
        recursion_limit=16,
        timeout_seconds=60.0,
    )
    answer: KnowledgeAnswer = result.output
    # Only sources the tool actually returned count; ungrounded answers are replaced.
    sources = [s.strip().upper() for s in answer.sources if s.strip().upper() in ctx.seen_references]
    if not answer.grounded or not sources:
        answer = KnowledgeAnswer(answer=NOT_ENOUGH_INFO, sources=[], grounded=False, suggest_ticket=True)
    else:
        answer = answer.model_copy(update={"answer": neutralise_execution_claims(answer.answer), "sources": sources})
    return answer, ctx.seen_references


async def decide_assistant_turn(
    repos: Repos,
    container: Container,
    *,
    message: str,
    history: list[dict[str, str]],
    requester_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> tuple[AssistantDecision, ToolContext]:
    """The employee assistant: a Deep Agent that picks a skill, uses read-only tools, decides."""
    ctx = ToolContext(repos=repos, container=container, requester_id=requester_id)
    agent = build_agent(
        model=container.chat_model("assistant", conversation_id=str(conversation_id)),
        tools=assistant_agent_tools(ctx),
        system_prompt=prompts.assistant_agent_prompt(skills_index()),
        response_format=AssistantDecision,
        name="nexa-assistant-router",
    )
    messages: list[dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in history[-8:]]
    messages.append({"role": "user", "content": message})
    result = await run_agent(
        agent,
        messages=messages,
        schema=AssistantDecision,
        audit=repos.audit,
        agent_name="nexa-assistant-router",
        operation="assistant_turn",
        model_label=container.settings.model_for_task("assistant") or None,
        conversation_id=conversation_id,
        tool_calls_counter=ctx,
        recursion_limit=16,
        timeout_seconds=45.0,
    )
    return result.output, ctx


async def ask_copilot(
    repos: Repos,
    container: Container,
    *,
    ticket_id: uuid.UUID,
    requester_id: uuid.UUID,
    ticket_number: str,
    question: str,
    history: list[dict[str, str]],
) -> CopilotAnswer:
    ctx = ToolContext(repos=repos, container=container, ticket_id=ticket_id, requester_id=requester_id)
    agent = build_agent(
        model=container.chat_model("copilot", ticket_id=str(ticket_id)),
        tools=copilot_tools(ctx),
        system_prompt=prompts.COPILOT + f"\n\nThe ticket in context is {ticket_number}. Start by calling get_ticket.",
        response_format=CopilotAnswer,
        name="nexa-copilot",
    )
    messages: list[dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in history[-8:]]
    messages.append({"role": "user", "content": question})
    result = await run_agent(
        agent,
        messages=messages,
        schema=CopilotAnswer,
        audit=repos.audit,
        agent_name="nexa-copilot",
        operation="copilot",
        model_label=container.settings.model_for_task("copilot") or None,
        ticket_id=ticket_id,
        tool_calls_counter=ctx,
        recursion_limit=20,
        timeout_seconds=90.0,
    )
    answer: CopilotAnswer = result.output
    refs = [r.strip().upper() for r in answer.references if r.strip().upper() in ctx.seen_references or r.strip().upper() == ticket_number.upper()]
    return answer.model_copy(
        update={
            "answer": neutralise_execution_claims(answer.answer) or "",
            "draft_message": neutralise_execution_claims(answer.draft_message),
            "references": refs,
        }
    )
