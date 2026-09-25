"""Fast-model triage of employee messages (intent, classification, extraction)."""

from __future__ import annotations

from collections.abc import Sequence

from app.agents import prompts
from app.agents.guardrails import neutralise_execution_claims, strip_reasoning
from app.agents.schemas import ExtractedSignal, TriageResult
from app.domain.enums import STATUS_LABELS, TicketStatus
from app.domain.taxonomy import normalize_category
from app.infrastructure.telemetry import span
from app.models import Profile, Ticket
from app.services.base import Service
from app.utils.text import truncate


class TriageService(Service):
    async def triage(
        self,
        history: Sequence[dict[str, str]],
        *,
        requester: Profile,
        open_tickets: Sequence[Ticket],
        metadata: dict | None = None,
    ) -> tuple[TriageResult, str]:
        services = await self.repos.settings.services()
        catalogue = ", ".join(s.name for s in services) or "(none configured)"
        tickets = "\n".join(
            f"- {t.ticket_number}: {truncate(t.title, 90)} [{STATUS_LABELS[TicketStatus(t.status)]}]" for t in open_tickets[:8]
        ) or "(none)"
        context = (
            f"Employee: {requester.name}"
            + (f", {requester.job_title}" if requester.job_title else "")
            + (f", {requester.department}" if requester.department else "")
            + (f", {requester.location}" if requester.location else "")
            + f"\nService catalogue: {catalogue}\nTheir open tickets:\n{tickets}"
        )
        messages = [{"role": "system", "content": prompts.TRIAGE}, {"role": "system", "content": context}]
        for turn in history[-8:]:
            messages.append({"role": "assistant" if turn["role"] == "assistant" else "user", "content": truncate(turn["content"], 2000)})

        with span("ai.triage", **{"nexa.history_turns": len(history)}):
            result, info = await self.container.llm.structured("triage", messages, TriageResult, temperature=0.0, max_tokens=900, metadata=metadata)
        return self.postprocess(result), info.model

    @staticmethod
    def postprocess(result: TriageResult) -> TriageResult:
        category, subcategory = normalize_category(result.category, result.subcategory) if result.category else (None, result.subcategory)
        signals = [ExtractedSignal.model_validate(s.model_dump()) for s in result.signals[:6]]
        return result.model_copy(
            update={
                "category": category,
                "subcategory": subcategory,
                "reply": neutralise_execution_claims(result.reply) or "",
                "likely_cause": neutralise_execution_claims(strip_reasoning(result.likely_cause)),
                "signals": signals,
                "referenced_ticket_number": (result.referenced_ticket_number or "").strip().upper() or None,
            }
        )
