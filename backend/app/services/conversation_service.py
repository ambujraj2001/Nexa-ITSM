"""The employee AI assistant.

Flow: employee message → fast-model triage → a proposal card (AI analysis +
"Create incident") → on confirmation, a ticket is created and investigated in
the background while the UI shows progress.

Ticket facts in replies (status, who's handling it, what's needed, SLA) are
composed deterministically from the database — the model never states them.
"""

from __future__ import annotations

import asyncio

import re
import uuid
from collections.abc import Sequence
from typing import Any

from app.agents import prompts
from app.agents.guardrails import clean_list, neutralise_execution_claims, strip_reasoning
from app.agents.nex_agent import NOT_ENOUGH_INFO, answer_knowledge_question, decide_assistant_turn
from app.agents.schemas import AssistantDecision, FollowUps, TriageResult
from app.agents.tools import ToolContext
from app.container import Container
from app.core.errors import AIUnavailable, Conflict, NotFound, ValidationFailed
from app.core.logging import get_logger
from app.domain.enums import (
    DONE_STATUSES,
    OPEN_STATUSES,
    STATUS_LABELS,
    TICKET_TYPE_LABELS,
    CommentVisibility,
    Priority,
    TicketSource,
    TicketStatus,
    TicketType,
)
from app.domain.policies import Principal
from app.domain.priority import determine_priority
from app.infrastructure.cache import key as cache_key
from app.infrastructure.telemetry import span
from app.models import Conversation, ConversationMessage, Ticket
from app.schemas.misc import ConfirmProposalResponse, ConversationView, MessageView, SendMessageResponse
from app.schemas.tickets import CommentCreate
from app.services.assignment_service import AssignmentService
from app.services.audit_service import AuditService
from app.services.base import Repos, Service
from app.services.presenters import confidence_label
from app.services.sla_service import SlaService
from app.services.ticket_service import NewTicket, TicketService, derive_title, store_attachment
from app.services.triage_service import TriageService
from app.utils.text import truncate

log = get_logger(__name__)

PRIORITY_LABELS = {"P1": "Critical", "P2": "High", "P3": "Normal", "P4": "Low"}
STATUS_FOLLOW_UPS = ["What is the status?", "Who is handling it?", "Is there anything I need to do?"]
# Short follow-ups that are unambiguously about an existing ticket. Anything
# longer goes through triage, which sees the user's open tickets.
_STATUS_PATTERN = re.compile(
    r"(what('?s| is) the status|status of my|any (update|news)|who('?s| is) (handling|working on) (it|this|my)|"
    r"what('?s| is) happening with (it|my)|why is it taking|taking (so )?long|need from me|anything i need to do|"
    r"what do you need|where are we)",
    re.IGNORECASE,
)
_HOW_TO = re.compile(r"^\s*(how (do|can|should) (i|we)|how to|where (do|can) i|can i|what is the (process|policy))\b", re.IGNORECASE)
_TICKET_REF = re.compile(r"\b(INC|REQ|PRB|CHG)-\d{3,7}\b", re.IGNORECASE)


def message_view(m: ConversationMessage) -> MessageView:
    return MessageView(id=m.id, role=m.role, content=m.content, message_type=m.message_type, payload=m.payload or {}, ticket_id=m.ticket_id, created_at=m.created_at)


class ConversationService(Service):
    def __init__(self, repos: Repos, container: Container, principal: Principal) -> None:
        super().__init__(repos, container)
        self.principal = principal
        self.audit = AuditService(repos.audit)
        self.sla = SlaService(repos.settings, due_soon_minutes=container.settings.due_soon_minutes)

    # ── conversations ────────────────────────────────────────────────────
    async def _own(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self.repos.conversations.get(conversation_id)
        if conversation is None or conversation.user_id != self.principal.profile_id:
            raise NotFound("Conversation not found.")
        return conversation

    async def current(self) -> ConversationView:
        conversation = await self.repos.conversations.latest_active(self.principal.profile_id)
        if conversation is None:
            conversation = await self.repos.conversations.add(Conversation(user_id=self.principal.profile_id))
            await self.commit()
        return await self.view(conversation.id)

    async def start_new(self) -> ConversationView:
        latest = await self.repos.conversations.latest_active(self.principal.profile_id)
        if latest is not None:
            latest.status = "archived"
        conversation = await self.repos.conversations.add(Conversation(user_id=self.principal.profile_id))
        await self.commit()
        return await self.view(conversation.id)

    async def view(self, conversation_id: uuid.UUID) -> ConversationView:
        conversation = await self._own(conversation_id)
        messages = await self.repos.conversations.messages(conversation.id)
        return ConversationView(
            id=conversation.id, title=conversation.title, status=conversation.status, created_at=conversation.created_at,
            updated_at=conversation.updated_at, messages=[message_view(m) for m in messages],
        )

    async def _supersede_open_proposals(self, conversation: Conversation) -> None:
        for m in await self.repos.conversations.recent_messages(conversation.id, limit=30):
            if m.message_type == "triage_proposal" and (m.payload or {}).get("status") == "proposed":
                m.payload = {**m.payload, "status": "superseded"}

    async def _suggest(self, reply: str, message_type: str) -> list[str]:
        """Up to three follow-ups the employee might send next, written by the fast model for this reply."""
        if not self.container.ai_available or message_type not in ("text", "ticket_status", "knowledge_answer", "ticket_created"):
            return []
        try:
            out, _ = await asyncio.wait_for(
                self.container.llm.structured(
                    "summary",
                    [
                        {"role": "system", "content": prompts.FOLLOW_UPS},
                        {"role": "user", "content": f"Assistant reply ({message_type}):\n{truncate(reply, 1500)}"},
                    ],
                    FollowUps, max_tokens=200,
                ),
                timeout=6.0,
            )
        except Exception:  # noqa: BLE001 — suggestions are optional
            return []
        return clean_list(out.suggestions, limit=3, max_len=60)

    async def _say(self, conversation: Conversation, content: str, message_type: str = "text", payload: dict[str, Any] | None = None, ticket_id: uuid.UUID | None = None) -> ConversationMessage:
        payload = dict(payload or {})
        if not payload.pop("fixed_suggestions", False) and message_type != "triage_proposal":
            payload["suggestions"] = await self._suggest(content, message_type)
        return await self.repos.conversations.add_message(
            ConversationMessage(conversation_id=conversation.id, role="assistant", content=content, message_type=message_type, payload=payload, ticket_id=ticket_id)
        )

    # ── sending a message ────────────────────────────────────────────────
    async def send(self, conversation_id: uuid.UUID, content: str) -> SendMessageResponse:
        conversation = await self._own(conversation_id)
        await self.container.rate_limiter.hit("assistant", str(self.principal.profile_id), limit=self.settings.assistant_messages_per_minute)
        busy = cache_key("conv", conversation.id, "busy")
        if not await self.container.store.set(busy, "1", ttl_seconds=90, only_if_absent=True):
            raise Conflict("I'm still working on your last message.", code="conversation_busy")
        try:
            with span("assistant.message", **{"nexa.conversation_id": str(conversation.id)}):
                user_message = await self.repos.conversations.add_message(
                    ConversationMessage(conversation_id=conversation.id, role="user", content=content.strip(), message_type="text")
                )
                if not conversation.title:
                    conversation.title = truncate(content, 80)
                replies = await self._respond(conversation, content.strip())
                conversation.updated_at = user_message.created_at
                await self.commit()
                return SendMessageResponse(conversation_id=conversation.id, messages=[message_view(user_message), *[message_view(r) for r in replies]])
        finally:
            await self.container.store.delete(busy)

    async def _history(self, conversation: Conversation) -> list[ConversationMessage]:
        return await self.repos.conversations.recent_messages(conversation.id, limit=14)

    def _issue_thread(self, history: Sequence[ConversationMessage]) -> list[ConversationMessage]:
        """User messages since the last ticket/proposal boundary — the current issue."""
        thread: list[ConversationMessage] = []
        for m in reversed(history):
            if m.role == "assistant" and (m.message_type == "ticket_created" or (m.message_type == "triage_proposal" and (m.payload or {}).get("status") in ("created", "dismissed"))):
                break
            if m.role == "user":
                thread.append(m)
        return list(reversed(thread))

    async def _respond(self, conversation: Conversation, content: str) -> list[ConversationMessage]:
        history = await self._history(conversation)
        open_tickets = list(await self.repos.tickets.requested_by(self.principal.profile_id, limit=10, open_only=True))
        recent_tickets = list(await self.repos.tickets.requested_by(self.principal.profile_id, limit=10))
        referenced = {m.group(0).upper() for m in _TICKET_REF.finditer(content)}

        # A number that is one of the employee's own tickets, in a short message → answer from
        # the database straight away (no model call). Unknown numbers go to the agent.
        digits = set(re.findall(r"(?<![\d.])\d{4,7}(?![\d.])", content))
        own = {t.ticket_number.upper() for t in recent_tickets if t.ticket_number.split("-")[-1] in digits}
        if own and len(content) <= 120 and not _HOW_TO.search(content):
            return [await self._status_reply(conversation, content, recent_tickets, own)]

        # Status questions are answered from the database without a model call.
        if (referenced or (len(content) <= 90 and _STATUS_PATTERN.search(content) and not re.search(r"\d{3,}", content))) and recent_tickets:
            return [await self._status_reply(conversation, content, recent_tickets, referenced)]

        config = await self.repos.settings.ai_configuration()
        if not config.ai_triage_enabled or not self.container.ai_available:
            return [await self._manual_proposal(conversation, history, reason="AI triage is turned off for this workspace, but I can still file this for the IT team.")]

        turns = [{"role": m.role, "content": m.content} for m in history if m.message_type in ("text", "clarification", "knowledge_answer", "triage_proposal")]

        # The assistant agent decides what to do (skills + read-only tools). Anything it
        # can't settle — or any AI failure — falls through to the triage flow below.
        forced_intent: str | None = None
        try:
            decision, ctx = await decide_assistant_turn(
                self.repos, self.container, message=content, history=turns[:-1],
                requester_id=self.principal.profile_id, conversation_id=conversation.id,
            )
        except Exception:  # noqa: BLE001 — degrade to the deterministic triage path
            decision = None
        if decision is not None:
            handled = await self._act_on_decision(conversation, content, decision, ctx, open_tickets, recent_tickets, history)
            if handled is not None:
                return handled
            forced_intent = "report_issue" if decision.action == "propose_ticket" else None
        try:
            me = await self.repos.users.get(self.principal.profile_id)
            triage, model = await TriageService(self.repos, self.container).triage(
                turns, requester=me, open_tickets=open_tickets, metadata={"conversation_id": str(conversation.id)}
            )
        except AIUnavailable:
            return [await self._manual_proposal(conversation, history, reason="I couldn't analyse that right now, but I can still file it for the IT team.")]

        if forced_intent and triage.intent not in ("report_issue", "service_request"):
            triage = triage.model_copy(update={"intent": forced_intent})
        if triage.intent == "ticket_status" and not referenced and _HOW_TO.search(content):
            triage = triage.model_copy(update={"intent": "knowledge_question"})  # "how do I…" is never a status question
        if triage.intent == "ticket_status" and recent_tickets:
            refs = referenced | ({triage.referenced_ticket_number} if triage.referenced_ticket_number else set())
            return [await self._status_reply(conversation, content, recent_tickets, refs)]
        # IT asked this person a question on exactly one ticket: a reply that isn't a question
        # or a status check is their answer — deterministically, whatever the model guessed.
        awaiting = [t for t in open_tickets if t.status == TicketStatus.PENDING_USER.value]
        answers_it = len(awaiting) == 1 and triage.intent == "report_issue" and not content.rstrip().endswith("?")
        if (triage.intent == "provide_information" and open_tickets) or answers_it:
            return [await self._add_information(conversation, content, awaiting or open_tickets, triage)]
        if triage.intent == "knowledge_question":
            return await self._knowledge_reply(conversation, content, history, triage)
        if triage.intent in ("report_issue", "service_request") or (triage.intent == "provide_information" and not open_tickets):
            thread = self._issue_thread(history)
            asked_before = any(m.role == "assistant" and m.message_type == "clarification" for m in history[-4:])
            if triage.needs_clarification and triage.clarifying_question and not asked_before and len(thread) < 3:
                return [await self._say(conversation, triage.clarifying_question, "clarification", {"suggestions": []})]
            return [await self._proposal(conversation, thread, triage, model)]
        return [
            await self._say(
                conversation,
                triage.reply or "Hi! Tell me what's going wrong, or ask me anything about IT.",
                "text",
                {"suggestions": ["Report an issue", "Request access", "Check a ticket"]},
            )
        ]

    # ── proposal → ticket ────────────────────────────────────────────────
    async def _routing_preview(self, category: str | None, subcategory: str | None, priority: str, ticket_type: str, service_id: uuid.UUID | None) -> str | None:
        decision = await AssignmentService(self.repos, self.audit).route(
            category=category, subcategory=subcategory, priority=priority, ticket_type=ticket_type, service_id=service_id
        )
        return decision.team_name

    async def _proposal(self, conversation: Conversation, thread: Sequence[ConversationMessage], triage: TriageResult, model: str | None) -> ConversationMessage:
        ticket_type = TicketType(triage.ticket_type or ("service_request" if triage.intent == "service_request" else "incident"))
        service = await self.repos.settings.get_service_by_name(triage.service_hint) if triage.service_hint else None
        decision = determine_priority(
            impact=triage.impact, urgency=triage.urgency, ai_suggestion=triage.suggested_priority, ticket_type=ticket_type,
            category=triage.category, service_criticality=service.criticality if service else None,
        )
        team_name = await self._routing_preview(triage.category, triage.subcategory, decision.priority.value, ticket_type.value, service.id if service else None)
        description = "\n\n".join(m.content for m in thread) or triage.summary or ""
        type_label = TICKET_TYPE_LABELS[ticket_type].lower()
        routing = f" I can create {'an' if type_label[0] in 'aeiou' else 'a'} {type_label} and route it to {team_name}." if team_name else f" I can create {'an' if type_label[0] in 'aeiou' else 'a'} {type_label} for the IT team."
        payload = {
            "proposal_id": str(uuid.uuid4()),
            "status": "proposed",
            "ticket_type": ticket_type.value,
            "type_label": TICKET_TYPE_LABELS[ticket_type],
            "title": triage.title or derive_title(description),
            "summary": triage.summary,
            "category": triage.category,
            "subcategory": triage.subcategory,
            "priority": decision.priority.value,
            "priority_label": PRIORITY_LABELS[decision.priority.value],
            "likely_cause": triage.likely_cause,
            "confidence_label": confidence_label(triage.confidence) if triage.likely_cause else None,
            "team_name": team_name,
            "service_name": service.name if service else None,
            "signals": [s.model_dump() for s in triage.signals],
            "description": description,
            "triage": triage.model_dump(),
            "triage_model": model,
            "ticket_id": None,
            "ticket_number": None,
        }
        await self._supersede_open_proposals(conversation)
        return await self._say(conversation, (triage.reply or "Thanks for the details.").strip() + routing, "triage_proposal", payload)

    async def _manual_proposal(self, conversation: Conversation, history: Sequence[ConversationMessage], *, reason: str) -> ConversationMessage:
        thread = self._issue_thread(history)
        description = "\n\n".join(m.content for m in thread)
        payload = {
            "proposal_id": str(uuid.uuid4()), "status": "proposed", "ticket_type": "incident", "type_label": "Incident",
            "title": derive_title(description), "summary": None, "category": None, "subcategory": None,
            "priority": Priority.P3.value, "priority_label": PRIORITY_LABELS["P3"], "likely_cause": None, "confidence_label": None,
            "team_name": None, "service_name": None, "signals": [], "description": description, "triage": None,
            "triage_model": None, "ticket_id": None, "ticket_number": None, "manual": True,
        }
        await self._supersede_open_proposals(conversation)
        return await self._say(conversation, reason, "triage_proposal", payload)

    async def confirm(self, conversation_id: uuid.UUID, message_id: uuid.UUID) -> ConfirmProposalResponse:
        conversation = await self._own(conversation_id)
        message = await self.repos.conversations.get_message(message_id)
        if message is None or message.conversation_id != conversation.id or message.message_type != "triage_proposal":
            raise NotFound("Proposal not found.")
        payload = dict(message.payload or {})
        if payload.get("status") != "proposed":
            raise Conflict("This request was already handled.", code="proposal_handled")
        description = (payload.get("description") or "").strip()
        if len(description) < 3:
            raise ValidationFailed("Describe the problem first.")

        triage = TriageResult.model_validate(payload["triage"]) if payload.get("triage") else None
        tickets = TicketService(self.repos, self.container, self.principal)
        ticket = await tickets.create(
            NewTicket(
                description=description,
                title=payload.get("title"),
                ticket_type=TicketType(payload.get("ticket_type") or "incident"),
                source=TicketSource.ASSISTANT,
                conversation_id=conversation.id,
            ),
            triage=triage,
            triage_model=payload.get("triage_model"),
        )
        payload.update({"status": "created", "ticket_id": str(ticket.id), "ticket_number": ticket.ticket_number})
        message.payload = payload
        message.ticket_id = ticket.id
        type_label = TICKET_TYPE_LABELS[TicketType(ticket.ticket_type)]
        investigating = ticket.ai_status in ("pending", "running")
        # Record the employee's decision in the thread, before the confirmation.
        choice = ConversationMessage(conversation_id=conversation.id, role="user", content=f"Yes, create the {type_label.lower()}.", message_type="text")
        self.repos.session.add(choice)
        await self.repos.session.flush()
        text = (
            f"{type_label} {ticket.ticket_number} has been created. I'm investigating it now and will route it to the right team."
            if investigating
            else f"{type_label} {ticket.ticket_number} has been created and sent to the IT team."
        )
        created = await self._say(
            conversation, text, "ticket_created",
            {"ticket_id": str(ticket.id), "ticket_number": ticket.ticket_number, "ticket_type": ticket.ticket_type, "type_label": type_label, "title": ticket.title, "suggestions": STATUS_FOLLOW_UPS},
            ticket_id=ticket.id,
        )
        await self.commit()
        [summary] = await (await tickets.presenter()).summaries([ticket])
        return ConfirmProposalResponse(ticket=summary, messages=[message_view(message), message_view(choice), message_view(created)])

    async def dismiss(self, conversation_id: uuid.UUID, message_id: uuid.UUID) -> SendMessageResponse:
        conversation = await self._own(conversation_id)
        message = await self.repos.conversations.get_message(message_id)
        if message is None or message.conversation_id != conversation.id or message.message_type != "triage_proposal":
            raise NotFound("Proposal not found.")
        if (message.payload or {}).get("status") == "proposed":
            message.payload = {**message.payload, "status": "dismissed"}
        reply = await self._say(conversation, "No problem — I won't file anything. Tell me if anything changes.", "text", {"suggestions": ["Report an issue", "Check a ticket"]})
        await self.commit()
        return SendMessageResponse(conversation_id=conversation.id, messages=[message_view(message), message_view(reply)])

    # ── ticket facts, from the database ──────────────────────────────────
    async def _status_reply(self, conversation: Conversation, question: str, tickets: Sequence[Ticket], refs: set[str]) -> ConversationMessage:
        chosen = [t for t in tickets if t.ticket_number.upper() in refs] if refs else []
        if refs and not chosen:
            return await self._say(conversation, f"I couldn't find {', '.join(sorted(refs))} among your tickets. {NOT_ENOUGH_INFO}", "text", {"suggestions": ["What is the status?"]})
        if not chosen:
            # "Who is handling it?" right after filing means the ticket from this conversation.
            # The ticket in focus: the latest reply that was about exactly one ticket.
            history = await self._history(conversation)
            current = None
            for m in reversed(history):
                if m.role != "assistant":
                    continue
                cards = (m.payload or {}).get("tickets") or []
                if m.message_type == "ticket_created" and m.ticket_id:
                    current = str(m.ticket_id)
                elif m.message_type == "ticket_status" and len(cards) == 1:
                    current = cards[0].get("ticket_id")
                if current:
                    break
            chosen = [t for t in tickets if str(t.id) == current]
        if not chosen:
            open_ones = [t for t in tickets if TicketStatus(t.status) in OPEN_STATUSES]
            if len(open_ones) > 1:
                # Ambiguous: ask the employee rather than guessing (human in the loop).
                choices = [f"Status of {t.ticket_number} — {truncate(t.title, 40)}" for t in open_ones[:4]]
                return await self._say(conversation, f"You have {len(open_ones)} open tickets. Which one do you mean?", "clarification", {"suggestions": choices, "fixed_suggestions": True})
            chosen = open_ones[:1] or list(tickets[:1])
        people = await self.repos.users.get_many([t.assigned_to for t in chosen])
        teams = await self.repos.users.teams_by_ids([t.assignment_team_id for t in chosen])
        progress = await self.repos.tickets.step_progress([t.id for t in chosen])
        questions = await self.repos.tickets.latest_comments([t.id for t in chosen if t.status == TicketStatus.PENDING_USER.value])
        asks_why = bool(re.search(r"\b(why|long|slow|delay)\b", question, re.IGNORECASE))
        cards: list[dict[str, Any]] = []
        sentences: list[str] = []
        for t in chosen:
            status = TicketStatus(t.status)
            assignee = people.get(t.assigned_to) if t.assigned_to else None
            team = teams.get(t.assignment_team_id) if t.assignment_team_id else None
            done, total = progress.get(t.id, (0, 0))
            snap = self.sla.snapshot(t)
            parts = [f"{t.ticket_number} ({truncate(t.title, 60)}) is {STATUS_LABELS[status].lower()}."]
            if status in DONE_STATUSES:
                if t.resolution_ai_summary or t.resolution_summary:
                    parts.append(f"Resolution: {truncate(t.resolution_ai_summary or t.resolution_summary, 300)}")
            elif t.ai_status in ("pending", "running") and status in (TicketStatus.NEW, TicketStatus.TRIAGING):
                parts.append("I'm still investigating it before routing it to the right team.")
            elif assignee:
                parts.append(f"{assignee.name}" + (f" from {team.name}" if team else "") + " is handling it.")
            elif team:
                parts.append(f"It's in the {team.name} queue; an engineer will pick it up.")
            waiting_text = None
            if status == TicketStatus.PENDING_USER:
                q = questions.get(t.id)
                waiting_text = f"The engineer is waiting on you: “{truncate(q.content, 200)}”" if q else "The engineer is waiting on a reply from you."
                parts.append(waiting_text + " You can reply here.")
            elif status not in DONE_STATUSES:
                parts.append("Nothing is needed from you right now.")
            if total and status not in DONE_STATUSES:
                parts.append(f"{done} of {total} resolution steps are done.")
            if asks_why and status not in DONE_STATUSES:
                if t.escalation_count:
                    parts.append("It was escalated to a specialist (L2) team, which can take longer.")
                parts.append(f"It's {t.priority} ({PRIORITY_LABELS[t.priority].lower()} priority); the target is {snap.label.replace(' left', '')} from now." if snap.remaining_seconds and snap.remaining_seconds > 0 else f"It's {t.priority} priority and past its target time — it's been flagged to the team.")
            if len(chosen) == 1 and status not in DONE_STATUSES and re.search(r"\b(meanwhile|in the meantime|workaround|try|self[- ]help)\b", question, re.IGNORECASE):
                # "What can I try meanwhile?" → self-help from the knowledge base for this ticket's problem.
                from types import SimpleNamespace
                history = await self._history(conversation)
                replies = await self._knowledge_reply(conversation, question, history, SimpleNamespace(knowledge_query=f"{t.title}. {truncate(t.description, 300)} workaround self-help"))
                return replies[-1]
            focused = self._focused_answer(question, t, status, assignee, team, done, total, snap, questions.get(t.id)) if len(chosen) == 1 else None
            sentences.append(focused or " ".join(parts))
            cards.append(
                {
                    "ticket_id": str(t.id), "ticket_number": t.ticket_number, "title": t.title, "status": t.status,
                    "status_label": STATUS_LABELS[status], "priority": t.priority, "assignee_name": assignee.name if assignee else None,
                    "team_name": team.name if team else None, "waiting_on": "you" if status == TicketStatus.PENDING_USER else ("it_team" if status not in DONE_STATUSES else None),
                    "steps_done": done, "steps_total": total, "sla_label": snap.label if status not in DONE_STATUSES else None,
                    "updated_at": t.updated_at.isoformat(),
                }
            )
        return await self._say(conversation, "\n\n".join(sentences), "ticket_status", {"tickets": cards, "suggestions": STATUS_FOLLOW_UPS})

    @staticmethod
    def _focused_answer(question: str, t: Ticket, status: TicketStatus, assignee: Any, team: Any, done: int, total: int, snap: Any, pending_q: Any) -> str | None:
        """Answer the specific thing asked (when / who / what's needed / steps) from database facts."""
        q = question.lower()
        who = (f"{assignee.name}" + (f" from {team.name}" if team else "")) if assignee else (f"the {team.name} team" if team else "the IT team")
        if status in DONE_STATUSES:
            return None
        if re.search(r"\b(when|how long|eta|expect|timeline|fixed by|resolved by|deadline)\b", q):
            target = (f"The target is to resolve it within {snap.label.replace(' left', '')} ({t.priority}, {PRIORITY_LABELS[t.priority].lower()} priority)."
                      if snap.remaining_seconds and snap.remaining_seconds > 0 else f"It's past its {t.priority} target time, so it's been flagged to the team.")
            progress = f" {who} has completed {done} of {total} resolution steps so far." if total else f" {who} is working on it."
            return f"I can't promise an exact time, but for {t.ticket_number}: {target}{progress} I'll let you know here if anything is needed from you."
        if re.search(r"\b(steps?|progress|how far)\b", q):
            if not total:
                return f"{who} hasn't set out resolution steps for {t.ticket_number} yet."
            return f"{who} has completed {done} of {total} resolution steps on {t.ticket_number}. The steps themselves are the engineer's technical checklist — you'll hear from them here if they need anything from you."
        if re.search(r"\b(who|handling|assigned|working on)\b", q):
            return f"{who} is handling {t.ticket_number}." + (" You can reply here and I'll pass it on." if assignee else "")
        if re.search(r"\b(need|anything i|do i|should i|from me)\b", q):
            if status == TicketStatus.PENDING_USER:
                return f"Yes — {who} is waiting on you for {t.ticket_number}: “{truncate(pending_q.content, 200)}”. Reply here and I'll add it to the ticket." if pending_q else f"Yes — {who} is waiting on a reply from you for {t.ticket_number}. Reply here and I'll add it."
            return f"Nothing is needed from you right now for {t.ticket_number}. {who} will reach out here if they need anything."
        return None

    async def _act_on_decision(
        self, conversation: Conversation, content: str, decision: AssistantDecision, ctx: ToolContext,
        open_tickets: Sequence[Ticket], recent_tickets: Sequence[Ticket], history: Sequence[ConversationMessage],
    ) -> list[ConversationMessage] | None:
        """Carry out the agent's decision. Ticket facts always come from the database."""
        mine = {t.ticket_number.upper(): t for t in recent_tickets}
        if decision.action == "status":
            refs = {n.strip().upper() for n in decision.ticket_numbers if n.strip().upper() in mine}
            asked_digits = {d for r in decision.requested_refs for d in re.findall(r"\d{3,7}", r)}
            if asked_digits:
                refs = {r for r in refs if r.split("-")[-1] in asked_digits}
            if not refs and decision.requested_refs:
                asked = ", ".join(sorted({r.strip() for r in decision.requested_refs if r.strip()}))
                return [await self._say(conversation, f"I couldn't find ticket {asked} among your tickets. You can only check tickets you raised — ask me about one of those, or describe the problem and I'll file a new one.", "text", {"suggestions": ["What is the status?"]})]
            if not recent_tickets:
                return [await self._say(conversation, "You don't have any tickets yet. Describe the problem and I'll get it to the right team.", "text", {"suggestions": ["Report an issue"]})]
            return [await self._status_reply(conversation, content, recent_tickets, refs)]
        if decision.action == "clarify" and decision.clarifying_question:
            return [await self._say(conversation, neutralise_execution_claims(decision.clarifying_question) or decision.clarifying_question, "clarification", {"suggestions": []})]
        if decision.action == "add_information" and open_tickets:
            target = (decision.target_ticket_number or "").strip().upper()
            ordered = [t for t in open_tickets if t.ticket_number.upper() == target] + [t for t in open_tickets if t.ticket_number.upper() != target]
            return [await self._add_information(conversation, content, ordered, None)]
        if decision.action == "knowledge":
            sources = [s.strip().upper() for s in decision.knowledge_sources if s.strip().upper() in ctx.seen_references]
            if not sources or not decision.reply.strip():
                return None  # let the dedicated knowledge flow answer (or say it doesn't know)
            articles = await self.repos.knowledge.get_many_by_number(sources)
            payload = {"sources": [{"article_number": a.article_number, "title": a.title, "id": str(a.id)} for a in articles.values()], "grounded": True, "suggest_ticket": False, "suggestions": []}
            return [await self._say(conversation, neutralise_execution_claims(strip_reasoning(decision.reply)) or decision.reply, "knowledge_answer", payload)]
        if decision.action == "reply" and decision.reply.strip():
            return [await self._say(conversation, neutralise_execution_claims(strip_reasoning(decision.reply)) or decision.reply, "text", {"suggestions": ["Report an issue", "Request access", "Check a ticket"]})]
        return None  # propose_ticket and anything unresolved → triage builds the proposal

    async def _add_information(self, conversation: Conversation, content: str, open_tickets: Sequence[Ticket], triage: TriageResult | None) -> ConversationMessage:
        target = None
        if triage and triage.referenced_ticket_number:
            target = next((t for t in open_tickets if t.ticket_number.upper() == triage.referenced_ticket_number), None)
        target = target or next((t for t in open_tickets if t.status == TicketStatus.PENDING_USER.value), None) or open_tickets[0]
        tickets = TicketService(self.repos, self.container, self.principal)
        await tickets.add_comment(str(target.id), CommentCreate(content=content, visibility=CommentVisibility.REQUESTER))
        assignee = await self.repos.users.get(target.assigned_to) if target.assigned_to else None
        who = f" and let {assignee.name} know" if assignee else ""
        return await self._say(conversation, f"Thanks — I've added that to {target.ticket_number}{who}.", "text", {"suggestions": STATUS_FOLLOW_UPS}, ticket_id=target.id)

    async def _knowledge_reply(self, conversation: Conversation, content: str, history: Sequence[ConversationMessage], triage: TriageResult) -> list[ConversationMessage]:
        # Only earlier how-to exchanges give useful context; ticket chatter would make the model
        # restate ticket facts, which must come from the database, never from a model.
        turns = [{"role": m.role, "content": m.content} for m in history[:-1] if m.message_type == "knowledge_answer" or (m.role == "user" and _HOW_TO.search(m.content or ""))][-4:]
        try:
            answer, _ = await answer_knowledge_question(
                self.repos, self.container, question=triage.knowledge_query or content, history=turns,
                requester_id=self.principal.profile_id, conversation_id=conversation.id,
            )
        except AIUnavailable:
            return [await self._manual_proposal(conversation, history, reason="I couldn't look that up right now. If you need help, I can file it for the IT team.")]
        articles = await self.repos.knowledge.get_many_by_number(answer.sources)
        sources = [{"article_number": a.article_number, "title": a.title, "id": str(a.id)} for a in articles.values()]
        payload = {"sources": sources, "grounded": answer.grounded, "suggest_ticket": answer.suggest_ticket, "suggestions": ["That didn't help — create a ticket"] if answer.suggest_ticket else []}
        return [await self._say(conversation, answer.answer, "knowledge_answer", payload)]

    # ── attachments before a ticket exists ──────────────────────────────
    async def upload(self, conversation_id: uuid.UUID, *, file_name: str, content: bytes, content_type: str | None) -> dict[str, Any]:
        conversation = await self._own(conversation_id)
        attachment = await store_attachment(
            self.container, self.repos, ticket_id=None, conversation_id=conversation.id, uploaded_by=self.principal.profile_id,
            file_name=file_name, content=content, content_type=content_type,
        )
        await self.commit()
        return {"id": str(attachment.id), "file_name": attachment.file_name, "size_bytes": attachment.size_bytes}

