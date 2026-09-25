"""Seed a development workspace with fictional data. Safe to re-run (idempotent).

    uv run python -m scripts.seed                 # teams, services, rules, users, knowledge, history
    uv run python -m scripts.seed --demo-queue    # also file a few open tickets through the real
                                                  # pipeline (runs AI investigation if configured)

Demo accounts use @example.com addresses (never deliverable). Their password is
SEED_USER_PASSWORD, or a random one printed once at the end.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import string
import uuid
from datetime import timedelta

from sqlalchemy import select

from app.config import get_settings
from app.domain.enums import ActorType, AIStage, AIStatus, CommentKind, CommentVisibility, Role, StepSource, StepStatus, SupportLevel, TicketSource
from app.domain.policies import Principal
from app.infrastructure.db import Database
from app.infrastructure.supabase import SupabaseAdmin
from app.main import build_container
from app.models import (
    Asset,
    AssignmentRule,
    KnowledgeArticle,
    Profile,
    ResolutionStep,
    Service,
    Team,
    Ticket,
    TicketAssignment,
    TicketComment,
)
from app.services.audit_service import AuditService
from app.services.base import Repos, utcnow
from app.services.knowledge_service import KnowledgeService
from app.services.sla_service import SlaService
from scripts import seed_data as data

DOMAIN = "example.com"


def _password() -> tuple[str, bool]:
    configured = get_settings().seed_user_password.get_secret_value()
    if configured:
        return configured, False
    alphabet = string.ascii_letters + string.digits
    return "Nexa-" + "".join(secrets.choice(alphabet) for _ in range(14)) + "!9", True


async def seed(demo_queue: bool) -> None:
    settings = get_settings()
    if not settings.database_configured:
        raise SystemExit("SUPABASE_DB_URL is not set.")
    db = Database(settings)
    admin_api = SupabaseAdmin(settings)
    password, generated = _password()
    people: dict[str, Profile] = {}

    async with db.session() as session:
        repos = Repos.for_session(session)
        audit = AuditService(repos.audit)

        # ── teams, services, rules ───────────────────────────────────────
        teams: dict[str, Team] = {}
        for name, description, desk in data.TEAMS:
            team = await repos.users.get_team_by_name(name)
            if team is None:
                team = await repos.users.add_team(Team(name=name, description=description, is_service_desk=desk))
            teams[name] = team
        services: dict[str, Service] = {}
        for name, description, category, owner, criticality in data.SERVICES:
            service = await repos.settings.get_service_by_name(name)
            if service is None:
                service = Service(name=name, description=description, category=category, owner_team_id=teams[owner].id, criticality=criticality)
                await repos.settings.add(service)
            services[name] = service
        existing_rules = {r.name for r in await repos.settings.assignment_rules()}
        for name, category, subcategory, team, level, order in data.RULES:
            if name not in existing_rules:
                await repos.settings.add(AssignmentRule(name=name, category=category, subcategory=subcategory, team_id=teams[team].id, support_level=level, sort_order=order))
        await session.commit()
        print(f"✓ {len(teams)} teams, {len(services)} services, {len(data.RULES)} assignment rules")

        # ── people ───────────────────────────────────────────────────────
        created_logins = 0
        for key, name, local, role, level, team, title, department, location in data.USERS:
            email = f"{local}@{DOMAIN}"
            profile = await repos.users.get_by_email(email)
            if settings.supabase_admin_configured and (profile is None or profile.auth_user_id is None):
                user = await admin_api.find_user_by_email(email)
                if user is None:
                    user = await admin_api.create_user(email=email, password=password, full_name=name)
                    created_logins += 1
                await session.commit()
                profile = await repos.users.get_by_email(email)
                if profile is None:  # trigger not installed yet → create directly
                    profile = await repos.users.add(Profile(auth_user_id=uuid.UUID(user.id), email=email, name=name))
                elif profile.auth_user_id is None:
                    profile.auth_user_id = uuid.UUID(user.id)
            if profile is None:
                profile = await repos.users.add(Profile(email=email, name=name))
            profile.name, profile.role, profile.engineer_level = name, role, level
            profile.team_id = teams[team].id if team else None
            profile.job_title, profile.department, profile.location = title, department, location
            profile.is_active = True
            people[key] = profile
        await session.commit()
        print(f"✓ {len(people)} people ({created_logins} new sign-in accounts)")

        # ── assets ───────────────────────────────────────────────────────
        for owner, name, asset_type, service, metadata in data.ASSETS:
            existing = [a for a in await repos.settings.assets_for_owner(people[owner].id) if a.name == name]
            if not existing:
                await repos.settings.add(Asset(name=name, asset_type=asset_type, owner_id=people[owner].id, service_id=services[service].id, metadata_=metadata))
        await session.commit()

        # ── knowledge ────────────────────────────────────────────────────
        source = await repos.settings.knowledge_source_by_type("internal_articles")
        knowledge = KnowledgeService(repos, build_container_like(settings, db))
        article_ids = []
        for article in data.ARTICLES:
            row = (await session.execute(select(KnowledgeArticle).where(KnowledgeArticle.title == article["title"]))).scalar_one_or_none()
            if row is None:
                row = KnowledgeArticle(
                    title=article["title"], summary=article["summary"], content=article["content"], category=article["category"],
                    subcategory=article["subcategory"], service_id=services[article["service"]].id, source_id=source.id if source else None,
                    status="published", created_by=people["admin"].id, updated_by=people["admin"].id,
                )
                await repos.knowledge.add(row)
            article_ids.append(row.id)
        await session.commit()
        statuses = [await knowledge.index_article(aid) for aid in article_ids]
        print(f"✓ {len(article_ids)} knowledge articles (index: {', '.join(sorted(set(statuses)))})")

        # ── historical resolved incidents ────────────────────────────────
        sla = SlaService(repos.settings)
        created_history = 0
        for item in data.HISTORY:
            requester = people[item["requester"]]
            exists = (await session.execute(select(Ticket).where(Ticket.title == item["title"], Ticket.requester_id == requester.id))).scalar_one_or_none()
            if exists is not None:
                continue
            engineer = people[item["engineer"]]
            team = teams[item["team"]]
            opened = utcnow() - timedelta(days=item["days_ago"])
            resolved = opened + timedelta(minutes=item["minutes"])
            ticket = Ticket(
                title=item["title"], description=item["description"], ticket_type="incident", priority=item["priority"],
                status="closed", category=item["category"], subcategory=item["subcategory"], requester_id=requester.id,
                assigned_to=engineer.id, assignment_team_id=team.id, ai_recommended_team_id=team.id,
                assignment_reason="rule", support_level="L2" if item.get("escalated") else "L1",
                service_id=services[item["service"]].id, source=TicketSource.ASSISTANT.value, created_at=opened,
                first_response_at=opened + timedelta(minutes=5), ai_status=AIStatus.COMPLETED.value, ai_stage=AIStage.DONE.value,
                resolution_summary=item["resolution"], resolution_code="fixed", resolved_by=engineer.id, resolved_at=resolved,
                closed_at=resolved + timedelta(hours=2), escalation_count=1 if item.get("escalated") else 0,
            )
            await repos.tickets.add(ticket)
            await sla.apply(ticket, start=opened)
            await repos.tickets.upsert_analysis(
                ticket.id, category=item["category"], subcategory=item["subcategory"], priority=item["priority"],
                summary=item["description"], diagnosis=item["diagnosis"], confidence=0.78, rationale="Seeded historical incident.",
                recommended_team_id=team.id,
            )
            for position, description in enumerate(item["steps"]):
                await repos.tickets.add_step(
                    ResolutionStep(ticket_id=ticket.id, position=position, description=description, status=StepStatus.COMPLETED.value,
                                   source=StepSource.AI.value, completed_by=engineer.id, completed_at=opened + timedelta(minutes=10 + position * 5))
                )
            if item.get("escalated"):
                l1 = people[item["l1"]]
                await repos.tickets.add_assignment(TicketAssignment(ticket_id=ticket.id, team_id=team.id, assignee_id=l1.id, support_level="L1", reason="rule", created_at=opened))
            await repos.tickets.add_assignment(TicketAssignment(ticket_id=ticket.id, team_id=team.id, assignee_id=engineer.id, support_level=ticket.support_level, reason="escalation" if item.get("escalated") else "rule", created_at=opened))
            await repos.tickets.add_comment(TicketComment(ticket_id=ticket.id, author_id=engineer.id, content=item["resolution"], visibility=CommentVisibility.REQUESTER.value, kind=CommentKind.RESOLUTION.value))
            actor = Principal(profile_id=engineer.id, auth_user_id=engineer.auth_user_id, role=Role.ENGINEER, name=engineer.name, email=engineer.email, engineer_level=SupportLevel(engineer.engineer_level) if engineer.engineer_level else None, team_id=engineer.team_id)
            await audit.record("ticket.created", actor_type=ActorType.SYSTEM, ticket_id=ticket.id, metadata={"seed": True})
            await audit.record("ticket.resolved", actor=actor, ticket_id=ticket.id, new_value={"status": "resolved", "summary": item["resolution"]}, metadata={"seed": True})
            await session.commit()
            await knowledge.index_resolved_ticket(ticket.id)
            created_history += 1
        print(f"✓ {created_history} historical incidents added ({len(data.HISTORY)} total)")

    if demo_queue:
        await file_demo_queue(settings, people)

    await db.dispose()
    await admin_api.close()
    print("\nDemo accounts (all @example.com):")
    for key, name, local, role, level, team, *_ in data.USERS:
        print(f"  {role:<9} {level or '':<3} {name:<16} {local}@{DOMAIN}" + (f"  ({team})" if team else ""))
    if not settings.supabase_admin_configured:
        print("\n! SUPABASE_SERVICE_ROLE_KEY is not set: profiles were created without sign-in accounts.")
    elif generated and created_logins:
        print(f"\nPassword for new demo accounts: {password}\n(Set SEED_USER_PASSWORD to choose your own; existing accounts keep their password.)")


def build_container_like(settings, db):  # type: ignore[no-untyped-def]
    return build_container(settings, inline_jobs=True, database=db)


async def file_demo_queue(settings, people: dict[str, Profile]) -> None:  # type: ignore[no-untyped-def]
    """File open tickets as real employees would, through the full pipeline."""
    from app.services.ticket_service import NewTicket, TicketService

    container = build_container(settings, inline_jobs=True)  # wait for each investigation
    samples = [
        ("maya", "Outlook keeps asking for my password since this morning and I can't get to my calendar before the finance close."),
        ("alex", "Wi-Fi in the Berlin office drops every few minutes on Corp-Secure. Several of us on the 3rd floor are affected."),
    ]
    for key, text in samples:
        p = people[key]
        principal = Principal(profile_id=p.id, auth_user_id=p.auth_user_id, role=Role.EMPLOYEE, name=p.name, email=p.email)
        async with container.db.session() as session:
            ticket = await TicketService(Repos.for_session(session), container, principal).create(NewTicket(description=text, source=TicketSource.PORTAL))
            print(f"✓ filed {ticket.ticket_number} for {p.name} (AI: {ticket.ai_status})")
    await container.jobs.drain()
    if container.database is not None:
        await container.database.dispose()  # type: ignore[attr-defined]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo-queue", action="store_true", help="also file open demo tickets through the AI pipeline")
    args = parser.parse_args()
    asyncio.run(seed(args.demo_queue))


if __name__ == "__main__":
    main()
