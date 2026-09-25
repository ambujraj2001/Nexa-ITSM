"""Authorization, V1 policy enforcement, AI failure handling and retrieval."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.container import Container
from app.core.errors import NotFound, PermissionDenied, PolicyViolation
from app.domain.enums import CommentVisibility, StepStatus, TicketSource
from app.schemas.misc import AiSettingsUpdate
from app.schemas.tickets import CommentCreate, StepUpdate
from app.services.base import Repos
from app.services.knowledge_service import KnowledgeService
from app.services.settings_service import SettingsService
from app.services.ticket_service import NewTicket, TicketService
from tests.integration.conftest import World

pytestmark = pytest.mark.integration


async def _file(repos: Repos, container: Container, world: World, text_: str = "VPN is down, AnyConnect shows CERT_AUTHORITY_INVALID"):  # type: ignore[no-untyped-def]
    return await TicketService(repos, container, world.employee).create(NewTicket(description=text_, source=TicketSource.PORTAL))


async def test_employees_cannot_see_or_touch_other_peoples_tickets(repos: Repos, container: Container, world: World) -> None:
    ticket = await _file(repos, container, world)
    with pytest.raises(NotFound):
        await TicketService(repos, container, world.other_employee).view(str(ticket.id))
    detail = await TicketService(repos, container, world.l1).view(str(ticket.id))
    with pytest.raises(PermissionDenied):
        await TicketService(repos, container, world.employee).update_step(str(ticket.id), detail.steps[0].id, StepUpdate(status=StepStatus.COMPLETED))
    # Employees asking for internal visibility get a requester-visible comment instead.
    await TicketService(repos, container, world.employee).add_comment(str(ticket.id), CommentCreate(content="More info", visibility=CommentVisibility.INTERNAL))
    comments = await TicketService(repos, container, world.l1).comments(str(ticket.id))
    assert comments[-1].visibility == "requester"


async def test_ai_settings_are_admin_only_and_v1_policy_is_enforced(repos: Repos, container: Container, world: World) -> None:
    with pytest.raises(PermissionDenied):
        await SettingsService(repos, container, world.employee).ai_settings()
    with pytest.raises(PermissionDenied):
        await SettingsService(repos, container, world.l1).update_ai(AiSettingsUpdate(ai_triage_enabled=False))
    admin = SettingsService(repos, container, world.admin)
    with pytest.raises(PolicyViolation):
        await admin.update_ai(AiSettingsUpdate(automatic_actions_enabled=True))
    with pytest.raises(PolicyViolation):
        await admin.update_ai(AiSettingsUpdate(human_approval_required=False))
    updated = await admin.update_ai(AiSettingsUpdate(confidence_threshold=0.7))
    assert updated.confidence_threshold == pytest.approx(0.7) and not updated.automatic_actions_enabled
    assert "settings.ai_updated" in [e.action for e in await repos.audit.search(entity_type="ai_configuration", limit=5)]


async def test_database_itself_refuses_autonomous_execution(repos: Repos) -> None:
    savepoint = await repos.session.begin_nested()
    with pytest.raises((IntegrityError, DBAPIError)):
        await repos.session.execute(text("update public.ai_configuration set automatic_actions_enabled = true"))
    await savepoint.rollback()


async def test_ai_failure_still_routes_the_ticket(repos: Repos, container: Container, world: World) -> None:
    container.chat_model_factory = lambda task, meta: (_ for _ in ()).throw(RuntimeError("model down"))  # type: ignore[assignment]
    ticket = await _file(repos, container, world)
    detail = await TicketService(repos, container, world.l1).view(str(ticket.id))
    assert detail.ai_status == "failed" and detail.ai_error == "AI investigation failed. You can continue manually."
    assert detail.status == "assigned" and detail.team and detail.team.id == world.network.id
    assert detail.steps == [] and detail.permissions.can_retry_ai


async def test_disabling_ai_diagnosis_skips_it(repos: Repos, container: Container, world: World) -> None:
    await SettingsService(repos, container, world.admin).update_ai(AiSettingsUpdate(ai_diagnosis_enabled=False))
    ticket = await _file(repos, container, world)
    detail = await TicketService(repos, container, world.l1).view(str(ticket.id))
    assert detail.analysis and detail.analysis.evidence == []  # only triage output, no diagnosis stage
    assert len(detail.steps) == 4  # plans still generated


async def test_hybrid_search_finds_published_articles_without_embeddings(repos: Repos, container: Container, world: World) -> None:
    hits = await KnowledgeService(repos, container).search_articles("anyconnect zorblaxian certificate expired", limit=5)
    assert world.article.article_number in [h.article_number for h in hits]
    assert all("lexical" in h.matched_by or "article" in h.matched_by for h in hits)
