"""Integration fixtures.

Runs against a migrated Postgres (TEST_DATABASE_URL, else SUPABASE_DB_URL).
Every test runs inside one outer transaction that is rolled back afterwards —
service commits become SAVEPOINT releases — so nothing persists in the database
(sequences such as ticket numbers do advance). Inside the transaction the test
world disables pre-existing assignment rules/service desks so routing is
deterministic even on a database that already holds seed data.
"""

from __future__ import annotations

import os
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.config import Settings, get_settings
from app.container import Container
from app.core.security import TokenVerifier
from app.domain.enums import Role, SupportLevel
from app.domain.policies import Principal
from app.infrastructure.litellm import ModelRouter
from app.infrastructure.redis import InMemoryStore
from app.infrastructure.supabase import SupabaseAdmin
from app.jobs import BackgroundJobs
from app.models import AssignmentRule, KnowledgeArticle, Profile, Service, Team
from app.services.base import Repos
from tests.fakes import VPN_PLAN, VPN_TRIAGE, FakeAgentModel, FakeLLM, agent_factory


def _database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or get_settings().supabase_db_url.get_secret_value()
    return url.strip()


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    url = _database_url()
    if not url:
        pytest.skip("Integration tests need SUPABASE_DB_URL (or TEST_DATABASE_URL) pointing at a migrated database.")
    settings = Settings(_env_file=None, supabase_db_url=url)  # type: ignore[call-arg]
    from app.infrastructure.db import Database

    db = Database(settings)
    async with db.engine.connect() as conn:
        exists = (await conn.execute(text("select to_regclass('public.tickets') is not null"))).scalar()
    if not exists:
        await db.dispose()
        pytest.skip("Database isn't migrated — run `uv run python -m scripts.migrate` first.")
    yield db.engine
    await db.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    conn = await engine.connect()
    outer = await conn.begin()
    s = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False, autoflush=False)
    try:
        yield s
    finally:
        await s.close()
        await outer.rollback()
        await conn.close()


class SharedSession:
    """SessionProvider that hands background jobs the test's session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        try:
            yield self._session
        except Exception:
            await self._session.rollback()
            raise


def diagnosis_from_context(messages: list) -> dict:  # type: ignore[type-arg]
    """Cite the first KB article the investigation actually retrieved, plus one invented incident."""
    blob = "\n".join(str(m.content) for m in messages if type(m).__name__ == "ToolMessage")  # only what tools returned
    kb = re.search(r"\bKB-[A-Z0-9]+\b", blob)
    evidence = [{"source_type": "user_report", "reference": None, "summary": "Requester reports CERT_AUTHORITY_INVALID."}]
    if kb:
        evidence.insert(0, {"source_type": "knowledge_article", "reference": kb.group(0), "summary": "Article covers expired VPN client certificates."})
    evidence.append({"source_type": "historical_incident", "reference": "INC-99999", "summary": "An incident that does not exist."})
    return {
        "summary": "VPN authentication fails with a certificate error.",
        "diagnosis": "The VPN client certificate may have expired.",
        "confidence": 0.9,
        "evidence": evidence,
        "hypotheses": [{"cause": "Cached credentials", "likelihood": "low", "how_to_verify": "Check auth log"}],
        "rationale": "The reported error matches the certificate-expiry article.",
        "missing_information": ["Did it start after an OS update?"],
        "recommended_team": "Test Network",
    }


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM(
        {
            "TriageResult": {**VPN_TRIAGE, "service_hint": "Test VPN"},
            "ResolutionDraft": {"resolution_summary": "Client certificate expired; re-pushed via MDM and verified.", "employee_summary": "Your VPN certificate had expired. We renewed it."},
            "EmployeeResolutionSummary": {"employee_summary": "Your VPN certificate had expired — we renewed it and you're good to go."},
            "HandoffBrief": {"summary": "L1 verified the client; certificate renewal needs gateway access.", "completed_checks": ["Checked client status"], "ruled_out": [], "open_questions": ["Is the issuing CA healthy?"], "suggested_next": ["Check gateway CA chain"]},
        }
    )


@pytest.fixture
def fake_agent() -> FakeAgentModel:
    return FakeAgentModel(
        canned={
            "DiagnosisReport": diagnosis_from_context,
            "ResolutionPlan": VPN_PLAN,
            "KnowledgeAnswer": lambda m: {"answer": "Use the self-service portal.", "sources": ["KB-NOPE"], "grounded": True},
            "CopilotAnswer": {"answer": "Verify the certificate next.", "references": [], "draft_message": "We're renewing your certificate."},
        },
        first_tool={"DiagnosisReport": ("search_knowledge", {"query": "vpn certificate"})},
    )


@pytest.fixture
def container(session: AsyncSession, fake_llm: FakeLLM, fake_agent: FakeAgentModel) -> Container:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, app_env="test", supabase_url="http://supabase.test", supabase_anon_key="anon",
        nexa_model_fast="fake-fast", nexa_model_strong="fake-strong",
    )
    supabase = SupabaseAdmin(settings)
    c = Container(
        settings=settings, store=InMemoryStore(), models=ModelRouter(settings), supabase=supabase,
        verifier=TokenVerifier(settings, supabase), jobs=BackgroundJobs(inline=True), database=SharedSession(session),  # type: ignore[arg-type]
        chat_model_factory=agent_factory(fake_agent), structured_llm=fake_llm,
    )
    c.extras["recover_on_startup"] = False
    return c


@dataclass
class World:
    network: Team
    desk: Team
    applications: Team
    vpn: Service
    article: KnowledgeArticle
    employee: Principal
    other_employee: Principal
    l1: Principal
    l2: Principal
    teammate: Principal
    admin: Principal


def _principal(p: Profile) -> Principal:
    return Principal(
        profile_id=p.id, auth_user_id=p.auth_user_id, role=Role(p.role), name=p.name, email=p.email,
        engineer_level=SupportLevel(p.engineer_level) if p.engineer_level else None, team_id=p.team_id,
    )


@pytest.fixture
async def world(session: AsyncSession) -> World:
    repos = Repos.for_session(session)
    # Deterministic routing inside the rolled-back transaction.
    await session.execute(text("update public.assignment_rules set enabled = false"))
    await session.execute(text("update public.teams set is_service_desk = false where is_service_desk"))
    await session.execute(text(
        "update public.ai_configuration set ai_triage_enabled = true, ai_diagnosis_enabled = true, resolution_plans_enabled = true, confidence_threshold = 0.80"
    ))
    tag = uuid.uuid4().hex[:6]
    desk = await repos.users.add_team(Team(name=f"Test Service Desk {tag}", is_service_desk=True))
    network = await repos.users.add_team(Team(name="Test Network" if not await repos.users.get_team_by_name("Test Network") else f"Test Network {tag}"))
    applications = await repos.users.add_team(Team(name=f"Test Applications {tag}"))
    vpn = Service(name="Test VPN" if not await repos.settings.get_service_by_name("Test VPN") else f"Test VPN {tag}", owner_team_id=network.id, criticality="high", category="Network")
    await repos.settings.add(vpn)
    await repos.settings.add(AssignmentRule(name=f"test-vpn-{tag}", category="Network", subcategory="VPN", team_id=network.id, support_level="L1", sort_order=1))

    def person(name: str, role: str, team: Team | None = None, level: str | None = None) -> Profile:
        return Profile(name=name, email=f"{name.lower().replace(' ', '.')}.{tag}@example.com", role=role, team_id=team.id if team else None, engineer_level=level, department="QA", location="Test Lab")

    profiles = {
        "employee": person("Erin Employee", "employee"),
        "other": person("Olly Other", "employee"),
        "l1": person("Lee One", "engineer", network, "L1"),
        "l2": person("Lou Two", "engineer", network, "L2"),
        "teammate": person("Tam Mate", "engineer", network, "L1"),
        "admin": person("Ada Admin", "admin", desk),
    }
    for p in profiles.values():
        await repos.users.add(p)
    article = KnowledgeArticle(
        article_number=f"KB-T{tag.upper()}", title="VPN certificate expired zorblaxian", summary="CERT_AUTHORITY_INVALID means the client certificate expired.",
        content="## Symptoms\nAnyConnect shows CERT_AUTHORITY_INVALID zorblaxian.\n\n## Fix\nRe-push the certificate profile via MDM.",
        category="Network", subcategory="VPN", status="published",
    )
    await repos.knowledge.add(article)
    await repos.knowledge.replace_chunks(article.id, [article.content], None, None, {})
    await session.commit()
    # Teammate should be "busier" so least-loaded routing picks Lee One deterministically.
    return World(
        network=network, desk=desk, applications=applications, vpn=vpn, article=article,
        employee=_principal(profiles["employee"]), other_employee=_principal(profiles["other"]), l1=_principal(profiles["l1"]),
        l2=_principal(profiles["l2"]), teammate=_principal(profiles["teammate"]), admin=_principal(profiles["admin"]),
    )


@pytest.fixture
def repos(session: AsyncSession) -> Repos:
    return Repos.for_session(session)
