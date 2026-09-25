"""Engineer "Ask AI" copilot. Session history is transient (Redis, 12h)."""

from __future__ import annotations

import json

from app.agents.nex_agent import ask_copilot
from app.container import Container
from app.core.errors import AIUnavailable
from app.domain import policies
from app.domain.policies import Principal
from app.infrastructure.cache import key as cache_key
from app.schemas.tickets import CopilotReplyView, ResolutionDraftView
from app.services.base import Repos, Service
from app.services.resolution_service import ResolutionService
from app.services.ticket_service import TicketService

_HISTORY_TTL = 12 * 3600
_HISTORY_MAX = 16


class CopilotService(Service):
    def __init__(self, repos: Repos, container: Container, principal: Principal) -> None:
        super().__init__(repos, container)
        self.principal = principal
        self.tickets = TicketService(repos, container, principal)

    async def _ticket(self, ref: str):  # type: ignore[no-untyped-def]
        ticket = await self.tickets.load(ref)
        policies.ensure(policies.can_view_internal(self.principal, await self.tickets.facts(ticket)), "Copilot is available to IT staff.")
        return ticket

    def _key(self, ticket_id: object) -> str:
        return cache_key("copilot", ticket_id, self.principal.profile_id)

    async def history(self, ref: str) -> list[dict[str, str]]:
        ticket = await self._ticket(ref)
        raw = await self.container.store.list_range(self._key(ticket.id), 0, _HISTORY_MAX - 1)
        out = []
        for item in reversed(raw):
            try:
                out.append(json.loads(item))
            except ValueError:
                continue
        return out

    async def ask(self, ref: str, message: str) -> CopilotReplyView:
        ticket = await self._ticket(ref)
        if not self.container.ai_available:
            raise AIUnavailable("AI is not configured for this workspace.")
        await self.container.rate_limiter.hit("copilot", str(self.principal.profile_id), limit=self.settings.copilot_messages_per_minute)
        history = await self.history(ref)
        answer = await ask_copilot(
            self.repos, self.container, ticket_id=ticket.id, requester_id=ticket.requester_id,
            ticket_number=ticket.ticket_number, question=message, history=history,
        )
        await self.commit()  # persists the agent_runs record
        key_name = self._key(ticket.id)
        await self.container.store.push_capped(key_name, json.dumps({"role": "user", "content": message}), max_len=_HISTORY_MAX, ttl_seconds=_HISTORY_TTL)
        await self.container.store.push_capped(key_name, json.dumps({"role": "assistant", "content": answer.answer}), max_len=_HISTORY_MAX, ttl_seconds=_HISTORY_TTL)
        return CopilotReplyView(answer=answer.answer, references=answer.references, draft_message=answer.draft_message, model=self.settings.model_for_task("copilot") or None)

    async def draft_resolution(self, ref: str) -> ResolutionDraftView:
        ticket = await self.tickets.load(ref)
        policies.ensure(policies.can_work_ticket(self.principal, await self.tickets.facts(ticket)), "Only the assigned engineer can resolve this ticket.")
        if not self.container.ai_available:
            return ResolutionDraftView(resolution_summary="", employee_summary="", generated=False)
        await self.container.rate_limiter.hit("ai_draft", str(self.principal.profile_id), limit=self.settings.ai_drafts_per_minute)
        return await ResolutionService(self.repos, self.container).draft_resolution(ticket)
