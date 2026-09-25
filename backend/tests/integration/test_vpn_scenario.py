"""Primary acceptance scenario (spec §55/§77), exercised through the service layer:

employee reports "My VPN isn't working" → AI triage → proposal → ticket → AI
investigation (knowledge + history + diagnosis + plan) → assignment → engineer
works the plan manually → asks the requester → escalates to L2 → L2 resolves →
AI summarises → employee sees the resolution and confirms.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.container import Container
from app.core.errors import PermissionDenied
from app.domain.enums import CommentVisibility, EscalationReason, ResolutionCode, StepStatus
from app.models import AgentRun, AuditEvent
from app.schemas.tickets import CommentCreate, EmployeeTicketDetail, EscalateRequest, ReopenRequest, ResolveRequest, StepCreate, StepReorder, StepUpdate, TicketDetail
from app.services.base import Repos
from app.services.conversation_service import ConversationService
from app.services.dashboard_service import DashboardService
from app.services.ticket_service import TicketService
from tests.integration.conftest import World

pytestmark = pytest.mark.integration


async def _actions(repos: Repos, ticket_id) -> list[str]:  # type: ignore[no-untyped-def]
    return [e.action for e in await repos.audit.for_ticket(ticket_id)]


async def test_vpn_incident_end_to_end(repos: Repos, container: Container, world: World) -> None:
    # ── 1. Employee describes the problem in the assistant ──────────────────
    assistant = ConversationService(repos, container, world.employee)
    conversation = await assistant.current()
    sent = await assistant.send(conversation.id, "My VPN isn't working since this morning. AnyConnect says CERT_AUTHORITY_INVALID.")
    proposal = sent.messages[-1]
    assert proposal.message_type == "triage_proposal"
    assert proposal.payload["category"] == "Network" and proposal.payload["subcategory"] == "VPN"
    assert proposal.payload["priority"] == "P2"  # individual × critical, from the deterministic matrix
    assert proposal.payload["team_name"] == world.network.name  # routing preview from rules, not the model
    assert "INC-" not in proposal.content  # the model never states ticket facts

    # ── 2. Employee confirms → ticket created and investigated ─────────────
    confirmed = await assistant.confirm(conversation.id, proposal.id)
    ticket_id = confirmed.ticket.id
    assert confirmed.messages[-1].message_type == "ticket_created"

    engineer_tickets = TicketService(repos, container, world.l1)
    detail = await engineer_tickets.view(str(ticket_id))
    assert isinstance(detail, TicketDetail)
    assert detail.ticket_number.startswith("INC-")
    assert detail.ai_status == "completed" and detail.status == "assigned"
    assert detail.assignee and detail.assignee.id == world.l1.profile_id  # least-loaded L1 in the rule's team
    assert detail.team and detail.team.id == world.network.id
    assert detail.service and detail.service.id == world.vpn.id
    assert detail.sla.due_at is not None and detail.sla.state in ("on_track", "at_risk")

    analysis = detail.analysis
    assert analysis and analysis.diagnosis == "The VPN client certificate may have expired."
    refs = [e.reference for e in analysis.evidence]
    assert any(r and r.startswith("KB-") for r in refs)  # cites an article retrieval actually returned (seed data may outrank the test's)
    assert "INC-99999" not in refs  # invented evidence is dropped …
    assert analysis.confidence is not None and analysis.confidence <= 0.6  # … and confidence is capped
    assert analysis.below_threshold and analysis.confidence_label == "medium"
    assert [s.value for s in analysis.signals] == ["CERT_AUTHORITY_INVALID"]

    steps = detail.steps
    assert len(steps) == 4, [s.description for s in steps]
    assert all(s.source == "ai" and s.status == "pending" for s in steps)
    assert not any("restarted" in s.description.lower() for s in steps), "no step may claim an action was taken"
    assert steps[0].is_current
    assert any(s.technical_details for s in steps)

    actions = await _actions(repos, ticket_id)
    for expected in ("ticket.created", "ai.triage_completed", "ai.analysis_generated", "ai.plan_generated", "ticket.assigned"):
        assert expected in actions
    runs = (await repos.session.execute(select(AgentRun).where(AgentRun.ticket_id == ticket_id))).scalars().all()
    assert {r.agent_name for r in runs} == {"nexa-diagnosis", "nexa-resolution-planner"}
    assert all(r.status == "completed" and r.tool_calls >= 0 for r in runs)

    # Engineer's dashboard shows it as a new assignment
    dashboard = await DashboardService(repos, container, world.l1).engineer()
    assert dashboard.metrics.assigned_to_me == 1 and dashboard.metrics.urgent == 1
    item = next(i for i in dashboard.needs_attention if i.ticket.id == ticket_id)
    assert {r.code for r in item.reasons} >= {"new_assignment", "ai_uncertain"}

    # ── 3. Engineer works the plan by hand ─────────────────────────────────
    await engineer_tickets.update_step(str(ticket_id), steps[0].id, StepUpdate(status=StepStatus.COMPLETED, notes="Handshake fails at cert validation."))
    await engineer_tickets.update_step(str(ticket_id), steps[1].id, StepUpdate(description="Verify certificate expiry in Keychain"))
    added = await engineer_tickets.add_step(str(ticket_id), StepCreate(description="Confirm with requester"))
    await engineer_tickets.delete_step(str(ticket_id), steps[3].id)
    detail = await engineer_tickets.view(str(ticket_id))
    ids = [s.id for s in detail.steps]
    await engineer_tickets.reorder_steps(str(ticket_id), StepReorder(step_ids=[ids[0], ids[2], ids[1], ids[3]]))
    detail = await engineer_tickets.view(str(ticket_id))
    assert detail.status == "in_progress" and detail.first_response_at is not None
    completed = next(s for s in detail.steps if s.id == steps[0].id)
    assert completed.status == "completed" and completed.completed_by and completed.completed_by.id == world.l1.profile_id
    edited = next(s for s in detail.steps if s.id == steps[1].id)
    assert edited.edited and edited.description == "Verify certificate expiry in Keychain"
    assert any(s.id == added.id and s.source == "engineer" for s in detail.steps)
    assert steps[3].id not in [s.id for s in detail.steps]

    await engineer_tickets.restore_ai_steps(str(ticket_id))
    restored = await engineer_tickets.view(str(ticket_id))
    assert steps[3].id in [s.id for s in restored.steps]  # deleted AI step is back
    assert next(s for s in restored.steps if s.id == steps[1].id).description == steps[1].description  # wording reverted
    assert next(s for s in restored.steps if s.id == steps[0].id).status == "completed"  # completion kept

    # Teammates can view but not work it; employees never can.
    with pytest.raises(PermissionDenied):
        await TicketService(repos, container, world.teammate).update_step(str(ticket_id), steps[2].id, StepUpdate(status=StepStatus.COMPLETED))

    # ── 4. Engineer ↔ requester communication ──────────────────────────────
    await engineer_tickets.add_comment(str(ticket_id), CommentCreate(content="Internal: gateway CA looks fine.", visibility=CommentVisibility.INTERNAL))
    await engineer_tickets.add_comment(str(ticket_id), CommentCreate(content="Did this start right after the macOS update?", visibility=CommentVisibility.REQUESTER, request_info=True))
    assert (await engineer_tickets.view(str(ticket_id))).status == "pending_user"

    employee_tickets = TicketService(repos, container, world.employee)
    employee_view = await employee_tickets.view(str(ticket_id))
    assert isinstance(employee_view, EmployeeTicketDetail)
    assert employee_view.waiting_on == "you"
    assert not hasattr(employee_view, "analysis")  # no evidence or internal context for employees
    employee_comments = await employee_tickets.comments(str(ticket_id))
    assert all(c.visibility == "requester" for c in employee_comments)
    assert not any("gateway CA" in c.content for c in employee_comments)

    # Employee answers in the assistant — Nexa adds it to the ticket
    await assistant.send(conversation.id, "Yes, it started right after I installed the update this morning.")
    assert (await engineer_tickets.view(str(ticket_id))).status == "pending_engineer"

    # Status questions are answered from the database, without a model call
    # (the only model call allowed is writing the follow-up suggestion chips)
    factual = lambda: [c for c in container.structured_llm.calls if c[1] != "FollowUps"]  # noqa: E731
    calls_before = len(factual())
    status = (await assistant.send(conversation.id, "Who is handling it?")).messages[-1]
    assert status.message_type == "ticket_status"
    assert status.payload["tickets"][0]["assignee_name"] == world.l1.name
    assert len(factual()) == calls_before

    # ── 5. Escalate to L2 with full context ────────────────────────────────
    await engineer_tickets.escalate(str(ticket_id), EscalateRequest(reason=EscalationReason.ELEVATED_ACCESS, note="Needs gateway access."))
    l2_tickets = TicketService(repos, container, world.l2)
    l2_view = await l2_tickets.view(str(ticket_id))
    assert isinstance(l2_view, TicketDetail)
    assert l2_view.status == "escalated" and l2_view.support_level == "L2"
    assert l2_view.assignee and l2_view.assignee.id == world.l2.profile_id
    assert l2_view.escalation and l2_view.escalation.reason == "requires_elevated_access" and l2_view.escalation.note == "Needs gateway access."
    assert l2_view.analysis and l2_view.analysis.diagnosis and l2_view.analysis.handoff and l2_view.analysis.handoff.suggested_next
    assert [s.id for s in l2_view.steps] == [s.id for s in restored.steps]  # plan and completions preserved
    l1_view = await engineer_tickets.view(str(ticket_id))
    assert isinstance(l1_view, TicketDetail) and not l1_view.permissions.can_work  # L1 keeps read access only

    # ── 6. L2 resolves; AI summarises for the employee ─────────────────────
    await l2_tickets.resolve(str(ticket_id), ResolveRequest(resolution_summary="Client certificate expired; re-pushed via MDM and verified the tunnel.", resolution_code=ResolutionCode.FIXED))
    final = await l2_tickets.view(str(ticket_id))
    assert final.status == "resolved" and final.resolution and final.resolution.resolved_by and final.resolution.resolved_by.id == world.l2.profile_id
    assert final.resolved_at is not None
    indexed = (await repos.session.execute(text("select count(*) from public.incident_embeddings where ticket_id = :t"), {"t": ticket_id})).scalar()
    assert indexed == 1  # becomes searchable history

    employee_view = await employee_tickets.view(str(ticket_id))
    assert employee_view.resolution and "renewed" in (employee_view.resolution.summary or "")
    assert employee_view.permissions.can_close and employee_view.permissions.can_reopen

    await employee_tickets.close(str(ticket_id))
    assert (await employee_tickets.view(str(ticket_id))).status == "closed"
    await employee_tickets.reopen(str(ticket_id), ReopenRequest(reason="It broke again after restart."))
    assert (await employee_tickets.view(str(ticket_id))).status == "reopened"

    actions = await _actions(repos, ticket_id)
    for expected in ("step.completed", "step.edited", "step.added", "step.deleted", "step.reordered", "step.restored", "ticket.escalated",
                     "ai.handoff_generated", "ticket.resolved", "ai.resolution_summary_generated", "ticket.closed", "ticket.reopened"):
        assert expected in actions, expected
    ai_events = (await repos.session.execute(select(AuditEvent).where(AuditEvent.ticket_id == ticket_id, AuditEvent.action.like("ai.%")))).scalars().all()
    assert ai_events and all(e.actor_type in ("ai", "system") and e.actor_id is None for e in ai_events)
