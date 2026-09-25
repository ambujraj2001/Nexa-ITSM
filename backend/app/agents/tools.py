"""Read-only tools for Nexa's Deep Agents.

Every tool is a lookup. Context (which ticket, which requester) is bound
server-side when the tool set is built — the model can't pass an arbitrary ID
to reach someone else's data. Tools share the job's DB session under a lock
(LangGraph may run tool calls concurrently) and record every knowledge/incident
reference they return, so the diagnosis can be checked against them afterwards.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import StructuredTool

from app.container import Container
from app.domain.enums import STATUS_LABELS, TicketStatus
from app.domain.sla import format_duration
from app.infrastructure.telemetry import span
from app.services.base import Repos
from app.utils.text import truncate


@dataclass
class ToolContext:
    repos: Repos
    container: Container
    ticket_id: uuid.UUID | None = None
    requester_id: uuid.UUID | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    seen_references: set[str] = field(default_factory=set)
    calls: int = 0

    def remember(self, *refs: str | None) -> None:
        for ref in refs:
            if ref:
                self.seen_references.add(ref.strip().upper())


def _dump(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


def _tool(ctx: ToolContext, name: str, description: str, fn: Callable[..., Awaitable[str]]) -> StructuredTool:
    async def wrapped(**kwargs: Any) -> str:
        with span("agent.tool", **{"nexa.tool": name, "nexa.ticket_id": str(ctx.ticket_id) if ctx.ticket_id else None}):
            async with ctx.lock:
                ctx.calls += 1
                try:
                    return await fn(**kwargs)
                except Exception as exc:  # noqa: BLE001 — tell the model, let it continue
                    return f"Tool error ({type(exc).__name__}). Continue with the information you have."

    wrapped.__name__ = name
    wrapped.__doc__ = description
    # Reuse the undecorated function's signature for the argument schema.
    schema_source = StructuredTool.from_function(coroutine=fn, name=name, description=description)
    return StructuredTool.from_function(coroutine=wrapped, name=name, description=description, args_schema=schema_source.args_schema)


# ── individual tool implementations ────────────────────────────────────────


def _search_knowledge(ctx: ToolContext) -> StructuredTool:
    async def search_knowledge(query: str, category: str | None = None) -> str:
        from app.services.knowledge_service import KnowledgeService

        hits = await KnowledgeService(ctx.repos, ctx.container).search_articles(query, category=category, limit=5)
        ctx.remember(*(h.article_number for h in hits))
        if not hits:
            return "No matching knowledge articles."
        return _dump(
            [
                {"reference": h.article_number, "title": h.title, "category": h.category, "excerpt": truncate(h.excerpt, 600), "updated": h.updated_at.date().isoformat()}
                for h in hits
            ]
        )

    return _tool(ctx, "search_knowledge", "Search published IT knowledge articles and runbooks. Use specific terms (error codes, product names). Returns up to 5 articles with their KB reference.", search_knowledge)


def _search_incidents(ctx: ToolContext) -> StructuredTool:
    async def search_historical_incidents(query: str) -> str:
        from app.services.knowledge_service import KnowledgeService

        hits = await KnowledgeService(ctx.repos, ctx.container).search_incidents(query, exclude_ticket_id=ctx.ticket_id, limit=5)
        ctx.remember(*(h.ticket_number for h in hits))
        if not hits:
            return "No similar resolved incidents."
        return _dump(
            [
                {
                    "reference": h.ticket_number,
                    "title": h.title,
                    "category": " / ".join(filter(None, [h.category, h.subcategory])),
                    "problem": truncate(h.excerpt, 300),
                    "resolution": truncate(h.resolution_summary, 400),
                    "resolved_in": format_duration((h.resolved_at - h.created_at).total_seconds()) if h.resolved_at else None,
                }
                for h in hits
            ]
        )

    return _tool(ctx, "search_historical_incidents", "Search resolved past incidents similar to this problem. Treat them as supporting evidence, not as the answer.", search_historical_incidents)


def _get_ticket(ctx: ToolContext) -> StructuredTool:
    async def get_ticket() -> str:
        ticket = await ctx.repos.tickets.get(ctx.ticket_id) if ctx.ticket_id else None
        if ticket is None:
            return "No ticket in context."
        analysis = await ctx.repos.tickets.get_analysis(ticket.id)
        team = await ctx.repos.users.get_team(ticket.assignment_team_id) if ticket.assignment_team_id else None
        assignee = await ctx.repos.users.get(ticket.assigned_to) if ticket.assigned_to else None
        return _dump(
            {
                "ticket_number": ticket.ticket_number,
                "type": ticket.ticket_type,
                "title": ticket.title,
                "description": truncate(ticket.description, 2500),
                "priority": ticket.priority,
                "status": STATUS_LABELS[TicketStatus(ticket.status)],
                "category": ticket.category,
                "subcategory": ticket.subcategory,
                "team": team.name if team else None,
                "assignee": assignee.name if assignee else None,
                "support_level": ticket.support_level,
                "reported_at": ticket.created_at.isoformat(),
                "sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None,
                "diagnosis": analysis.diagnosis if analysis else None,
                "signals": analysis.signals if analysis else [],
            }
        )

    return _tool(ctx, "get_ticket", "Get the current ticket's details (status, priority, team, description, diagnosis).", get_ticket)


def _get_ticket_steps(ctx: ToolContext) -> StructuredTool:
    async def get_ticket_steps() -> str:
        if not ctx.ticket_id:
            return "No ticket in context."
        steps = await ctx.repos.tickets.list_steps(ctx.ticket_id)
        if not steps:
            return "No resolution steps yet."
        return _dump(
            [
                {"position": s.position + 1, "step": s.description, "status": s.status, "source": s.source, "note": s.notes, "completed_at": s.completed_at.isoformat() if s.completed_at else None}
                for s in steps
            ]
        )

    return _tool(ctx, "get_ticket_steps", "Get the resolution plan steps with their status and engineer notes.", get_ticket_steps)


def _get_ticket_notes(ctx: ToolContext) -> StructuredTool:
    async def get_ticket_notes() -> str:
        if not ctx.ticket_id:
            return "No ticket in context."
        comments = await ctx.repos.tickets.list_comments(ctx.ticket_id, include_internal=True)
        people = await ctx.repos.users.get_many([c.author_id for c in comments])
        if not comments:
            return "No notes or messages yet."
        return _dump(
            [
                {"at": c.created_at.isoformat(), "author": people[c.author_id].name if c.author_id in people else c.author_type, "visibility": c.visibility, "kind": c.kind, "text": truncate(c.content, 600)}
                for c in comments[-15:]
            ]
        )

    return _tool(ctx, "get_ticket_notes", "Get recent internal notes and requester messages on the current ticket.", get_ticket_notes)


def _get_user(ctx: ToolContext) -> StructuredTool:
    async def get_user() -> str:
        profile = await ctx.repos.users.get(ctx.requester_id) if ctx.requester_id else None
        if profile is None:
            return "Requester unknown."
        return _dump({"name": profile.name, "job_title": profile.job_title, "department": profile.department, "location": profile.location})

    return _tool(ctx, "get_user", "Get the requester's role, department and location.", get_user)


def _get_asset(ctx: ToolContext) -> StructuredTool:
    async def get_asset() -> str:
        if not ctx.requester_id:
            return "Requester unknown."
        assets = await ctx.repos.settings.assets_for_owner(ctx.requester_id)
        if not assets:
            return "No assets registered to the requester."
        return _dump([{"name": a.name, "type": a.asset_type, "details": a.metadata_} for a in assets[:10]])

    return _tool(ctx, "get_asset", "Get devices and applications registered to the requester (models, OS and client versions).", get_asset)


def _get_service(ctx: ToolContext) -> StructuredTool:
    async def get_service(name: str) -> str:
        services = await ctx.repos.settings.services()
        wanted = name.strip().lower()
        matches = [s for s in services if wanted in s.name.lower() or s.name.lower() in wanted][:3]
        if not matches:
            return _dump({"message": "No matching service.", "available_services": [s.name for s in services]})
        teams = await ctx.repos.users.teams_by_ids([s.owner_team_id for s in matches])
        return _dump(
            [{"name": s.name, "criticality": s.criticality, "owner_team": teams[s.owner_team_id].name if s.owner_team_id in teams else None, "description": s.description} for s in matches]
        )

    return _tool(ctx, "get_service", "Look up a service in the catalogue by name (criticality, owning team).", get_service)


def _get_team(ctx: ToolContext) -> StructuredTool:
    async def get_team(name: str) -> str:
        team = await ctx.repos.users.get_team_by_name(name)
        if team is None:
            teams = await ctx.repos.users.list_teams()
            return _dump({"message": "No such team.", "teams": [t.name for t in teams]})
        counts = (await ctx.repos.users.staff_counts_by_team()).get(team.id, {})
        return _dump({"name": team.name, "description": team.description, "service_desk": team.is_service_desk, "l1_engineers": counts.get("L1", 0), "l2_engineers": counts.get("L2", 0)})

    return _tool(ctx, "get_team", "Get a support team's description and staffing (L1/L2).", get_team)


def _get_sla_policy(ctx: ToolContext) -> StructuredTool:
    async def get_sla_policy(priority: str) -> str:
        policy = await ctx.repos.settings.active_sla_policy(priority.strip().upper())
        if policy is None:
            return "No active SLA policy for that priority."
        return _dump({"priority": policy.priority, "response_minutes": policy.response_time_minutes, "resolution_minutes": policy.resolution_time_minutes})

    return _tool(ctx, "get_sla_policy", "Get the response and resolution targets for a priority (P1–P4).", get_sla_policy)


def _recommend_assignment(ctx: ToolContext) -> StructuredTool:
    async def recommend_assignment(category: str, subcategory: str | None = None, priority: str | None = None) -> str:
        from app.domain.taxonomy import normalize_category
        from app.services.assignment_service import AssignmentService
        from app.services.audit_service import AuditService

        cat, sub = normalize_category(category, subcategory)
        ticket = await ctx.repos.tickets.get(ctx.ticket_id) if ctx.ticket_id else None
        decision = await AssignmentService(ctx.repos, AuditService(ctx.repos.audit)).route(
            category=cat, subcategory=sub, priority=priority, ticket_type=ticket.ticket_type if ticket else None,
            service_id=ticket.service_id if ticket else None,
        )
        return _dump({"team": decision.team_name, "support_level": decision.support_level, "basis": decision.reason})

    return _tool(ctx, "recommend_assignment", "Preview which team the deterministic routing rules would assign for a category.", recommend_assignment)


def _get_my_tickets(ctx: ToolContext) -> StructuredTool:
    async def list_my_tickets() -> str:
        if not ctx.requester_id:
            return "Unknown user."
        tickets = await ctx.repos.tickets.requested_by(ctx.requester_id, limit=10)
        if not tickets:
            return "The user has no tickets."
        people = await ctx.repos.users.get_many([t.assigned_to for t in tickets])
        return _dump(
            [
                {"ticket_number": t.ticket_number, "title": t.title, "status": STATUS_LABELS[TicketStatus(t.status)], "handled_by": people[t.assigned_to].name if t.assigned_to in people else None, "updated": t.updated_at.date().isoformat()}
                for t in tickets
            ]
        )

    return _tool(ctx, "list_my_tickets", "List the current employee's recent tickets with real status from the database ('Waiting on you' means IT asked them something).", list_my_tickets)


_BARE_NUMBER = re.compile(r"(?:(INC|REQ|PRB|CHG)[-\s#]*)?#?(\d{3,7})", re.IGNORECASE)


def _get_my_ticket(ctx: ToolContext) -> StructuredTool:
    async def get_my_ticket(ticket_ref: str) -> str:
        """Look up ONE of the employee's own tickets by number ("10227", "#10227", "INC-10227")."""
        if not ctx.requester_id:
            return "Unknown user."
        match = _BARE_NUMBER.search(ticket_ref or "")
        if not match:
            return "Give a ticket number such as INC-10227."
        prefix, digits = match.group(1), match.group(2)
        mine = await ctx.repos.tickets.requested_by(ctx.requester_id, limit=200)
        found = [t for t in mine if t.ticket_number.split("-")[-1] == digits and (not prefix or t.ticket_number.upper().startswith(prefix.upper()))]
        if not found:
            return f"Ticket {ticket_ref.strip()} was not found among this employee's tickets. Do not describe any other ticket."
        t = found[0]
        people = await ctx.repos.users.get_many([t.assigned_to])
        return _dump({"ticket_number": t.ticket_number, "title": t.title, "status": STATUS_LABELS[TicketStatus(t.status)], "handled_by": people[t.assigned_to].name if t.assigned_to in people else None})

    return _tool(ctx, "get_my_ticket", "Look up one of the current employee's own tickets by number; accepts bare numbers like 10227. Returns 'not found' for tickets they did not raise.", get_my_ticket)


def _get_skill(ctx: ToolContext) -> StructuredTool:
    async def get_skill(name: str) -> str:
        from app.agents.skills import load_skills

        skill = load_skills().get((name or "").strip())
        return skill.body if skill else "Unknown skill. Available: " + ", ".join(load_skills())

    return _tool(ctx, "get_skill", "Load the full instructions of a skill from the skills index before acting on it.", get_skill)


# ── tool sets per agent ────────────────────────────────────────────────────


def investigation_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _search_knowledge(ctx), _search_incidents(ctx), _get_ticket(ctx), _get_user(ctx), _get_asset(ctx),
        _get_service(ctx), _get_team(ctx), _get_sla_policy(ctx), _recommend_assignment(ctx),
    ]


def resolution_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [_search_knowledge(ctx), _get_ticket(ctx), _get_asset(ctx)]


def copilot_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        _get_ticket(ctx), _get_ticket_steps(ctx), _get_ticket_notes(ctx), _get_user(ctx), _get_asset(ctx),
        _search_knowledge(ctx), _search_incidents(ctx), _get_service(ctx),
    ]


def assistant_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [_search_knowledge(ctx), _get_my_tickets(ctx)]


def assistant_agent_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [_get_skill(ctx), _get_my_ticket(ctx), _get_my_tickets(ctx), _search_knowledge(ctx)]

