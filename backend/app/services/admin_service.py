"""Administration: users & roles, teams, audit log. Plus notifications and search."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.container import Container
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.domain import policies
from app.domain.enums import ActorType, Role
from app.domain.policies import Principal
from app.infrastructure.cache import key as cache_key
from app.models import Profile, Team
from app.repositories.ticket_repository import TicketFilters
from app.schemas.misc import (
    AuditEventView,
    NotificationsResponse,
    NotificationView,
    SearchResults,
    TeamView,
    TeamWrite,
    UserInvite,
    UserUpdate,
    UserView,
)
from app.services.audit_service import AuditService
from app.services.base import Repos, Service, utcnow
from app.services.presenters import TicketPresenter, team_ref
from app.services.sla_service import SlaService
from app.services.ticket_service import AI_LABEL, SYSTEM_LABEL, _describe


class AdminService(Service):
    def __init__(self, repos: Repos, container: Container, principal: Principal) -> None:
        super().__init__(repos, container)
        self.principal = principal
        self.audit = AuditService(repos.audit)

    # ── users ────────────────────────────────────────────────────────────
    async def _user_view(self, p: Profile, teams: dict[uuid.UUID, Team]) -> UserView:
        return UserView(
            id=p.id, name=p.name, email=p.email, role=p.role, engineer_level=p.engineer_level,
            team=team_ref(teams.get(p.team_id)) if p.team_id else None, job_title=p.job_title,
            department=p.department, location=p.location, is_active=p.is_active,
            has_login=p.auth_user_id is not None, created_at=p.created_at,
        )

    async def users(self, *, role: str | None, team_id: uuid.UUID | None, query: str | None) -> list[UserView]:
        policies.ensure_admin(self.principal)
        rows = await self.repos.users.list(role=role, team_id=team_id, query=query, include_inactive=True, limit=500)
        teams = await self.repos.users.teams_by_ids([p.team_id for p in rows])
        return [await self._user_view(p, teams) for p in rows]

    async def assignable(self, team_id: uuid.UUID | None) -> list[UserView]:
        policies.ensure_staff(self.principal)
        rows = [p for p in await self.repos.users.list(team_id=team_id, limit=500) if p.engineer_level is not None and p.role in ("engineer", "admin")]
        teams = await self.repos.users.teams_by_ids([p.team_id for p in rows])
        return [await self._user_view(p, teams) for p in rows]

    async def update_user(self, user_id: uuid.UUID, patch: UserUpdate) -> UserView:
        policies.ensure_admin(self.principal)
        profile = await self.repos.users.get(user_id)
        if profile is None:
            raise NotFound("User not found.")
        changes = patch.model_dump(exclude_unset=True)
        if profile.id == self.principal.profile_id and (changes.get("role") not in (None, Role.ADMIN) or changes.get("is_active") is False):
            raise Conflict("You can't remove your own admin access.", code="self_demotion")
        old = {"role": profile.role, "engineer_level": profile.engineer_level, "team_id": str(profile.team_id) if profile.team_id else None, "is_active": profile.is_active}
        if patch.role is not None:
            profile.role = patch.role.value
        if patch.clear_engineer_level or profile.role == Role.EMPLOYEE.value:
            profile.engineer_level = None
        elif patch.engineer_level is not None:
            profile.engineer_level = patch.engineer_level.value
        if patch.clear_team:
            profile.team_id = None
        elif patch.team_id is not None:
            if await self.repos.users.get_team(patch.team_id) is None:
                raise ValidationFailed("Unknown team.")
            profile.team_id = patch.team_id
        for field_name in ("name", "job_title", "department", "location", "is_active"):
            if field_name in changes and changes[field_name] is not None:
                setattr(profile, field_name, changes[field_name])
        new = {"role": profile.role, "engineer_level": profile.engineer_level, "team_id": str(profile.team_id) if profile.team_id else None, "is_active": profile.is_active}
        await self.audit.record("admin.user_updated", actor=self.principal, entity_type="profile", entity_id=profile.id, old_value=old, new_value=new)
        await self.commit()
        if profile.auth_user_id:
            await self.container.store.delete(cache_key("profile", profile.auth_user_id))
        teams = await self.repos.users.teams_by_ids([profile.team_id])
        return await self._user_view(profile, teams)

    async def invite(self, data: UserInvite) -> UserView:
        policies.ensure_admin(self.principal)
        if await self.repos.users.get_by_email(data.email):
            raise Conflict("Someone with that email already has a profile.", code="email_exists")
        if data.team_id and await self.repos.users.get_team(data.team_id) is None:
            raise ValidationFailed("Unknown team.")
        # Pre-provision the profile; the auth trigger links it when the invite is accepted.
        profile = await self.repos.users.add(
            Profile(
                name=data.name.strip(), email=str(data.email).lower(), role=data.role.value,
                engineer_level=data.engineer_level.value if data.engineer_level and data.role != Role.EMPLOYEE else None,
                team_id=data.team_id,
            )
        )
        await self.audit.record("admin.user_invited", actor=self.principal, entity_type="profile", entity_id=profile.id, new_value={"email": profile.email, "role": profile.role})
        await self.commit()
        await self.container.supabase.invite_user(email=profile.email, full_name=profile.name, redirect_to=f"{self.settings.frontend_url}/auth/callback")
        teams = await self.repos.users.teams_by_ids([profile.team_id])
        return await self._user_view(profile, teams)

    # ── teams ────────────────────────────────────────────────────────────
    async def teams(self) -> list[TeamView]:
        policies.ensure_staff(self.principal)
        teams = await self.repos.users.list_teams()
        members = await self.repos.users.team_member_counts()
        levels = await self.repos.users.staff_counts_by_team()
        return [
            TeamView(id=t.id, name=t.name, description=t.description, is_service_desk=t.is_service_desk, member_count=members.get(t.id, 0), l1_count=levels.get(t.id, {}).get("L1", 0), l2_count=levels.get(t.id, {}).get("L2", 0))
            for t in teams
        ]

    async def _clear_other_service_desks(self, keep: uuid.UUID | None) -> None:
        for t in await self.repos.users.list_teams():
            if t.is_service_desk and t.id != keep:
                t.is_service_desk = False
        await self.session.flush()

    async def create_team(self, data: TeamWrite) -> TeamView:
        policies.ensure_admin(self.principal)
        if await self.repos.users.get_team_by_name(data.name):
            raise Conflict("A team with that name exists.", code="team_exists")
        if data.is_service_desk:
            await self._clear_other_service_desks(None)
        team = await self.repos.users.add_team(Team(name=data.name.strip(), description=data.description, is_service_desk=data.is_service_desk))
        await self.audit.record("admin.team_created", actor=self.principal, entity_type="team", entity_id=team.id, new_value={"name": team.name})
        await self.commit()
        return next(v for v in await self.teams() if v.id == team.id)

    async def update_team(self, team_id: uuid.UUID, data: TeamWrite) -> TeamView:
        policies.ensure_admin(self.principal)
        team = await self.repos.users.get_team(team_id)
        if team is None:
            raise NotFound("Team not found.")
        existing = await self.repos.users.get_team_by_name(data.name)
        if existing and existing.id != team.id:
            raise Conflict("A team with that name exists.", code="team_exists")
        if data.is_service_desk:
            await self._clear_other_service_desks(team.id)
        old = {"name": team.name, "description": team.description, "is_service_desk": team.is_service_desk}
        team.name, team.description, team.is_service_desk = data.name.strip(), data.description, data.is_service_desk
        await self.audit.record("admin.team_updated", actor=self.principal, entity_type="team", entity_id=team.id, old_value=old, new_value=data.model_dump())
        await self.commit()
        return next(v for v in await self.teams() if v.id == team.id)

    # ── audit log ────────────────────────────────────────────────────────
    async def audit_log(self, *, entity_type: str | None, actor_type: str | None, action: str | None, before: datetime | None, limit: int) -> list[AuditEventView]:
        policies.ensure_admin(self.principal)
        events = await self.repos.audit.search(entity_type=entity_type, actor_type=actor_type, action_prefix=action, before=before, limit=limit)
        people = await self.repos.users.get_many([e.actor_id for e in events])
        ticket_ids = {e.ticket_id for e in events if e.ticket_id}
        numbers: dict[uuid.UUID, tuple[str, str]] = {}
        for tid in ticket_ids:
            t = await self.repos.tickets.get(tid)
            if t:
                numbers[tid] = (t.ticket_number, t.source)
        out = []
        for e in events:
            actor = people.get(e.actor_id) if e.actor_id else None
            label = actor.name if actor else (AI_LABEL if e.actor_type == ActorType.AI.value else SYSTEM_LABEL)
            number, source = numbers.get(e.ticket_id, (None, "assistant")) if e.ticket_id else (None, "assistant")
            described = _describe(e.action, e.old_value, e.new_value, e.metadata_ or {}, internal=True, source=source)
            summary = described[0] if described else e.action.replace("_", " ").replace(".", " · ")
            out.append(
                AuditEventView(
                    id=e.id, created_at=e.created_at, actor_type=e.actor_type, actor_label=label, actor_role=e.actor_role,
                    action=e.action, summary=summary, entity_type=e.entity_type, entity_id=e.entity_id, ticket_id=e.ticket_id,
                    ticket_number=number, old_value=e.old_value, new_value=e.new_value, metadata={k: v for k, v in (e.metadata_ or {}).items() if k not in ("trace_id",)},
                )
            )
        return out

    # ── notifications ────────────────────────────────────────────────────
    async def notifications(self) -> NotificationsResponse:
        me = await self.repos.users.get(self.principal.profile_id)
        since = me.notifications_seen_at if me else None
        events = await self.repos.audit.notifications_for(self.principal.profile_id, since=None, limit=25)
        tickets = {}
        for tid in {e.ticket_id for e in events if e.ticket_id}:
            t = await self.repos.tickets.get(tid)
            if t:
                tickets[tid] = t
        internal = self.principal.is_staff
        items = []
        for e in events:
            t = tickets.get(e.ticket_id)
            if t is None:
                continue
            if e.action == "comment.added" and (e.new_value or {}).get("visibility") == "internal" and not internal:
                continue
            described = _describe(e.action, e.old_value, e.new_value, e.metadata_ or {}, internal=internal and t.requester_id != self.principal.profile_id, source=t.source)
            if described is None:
                continue
            items.append(NotificationView(id=e.id, at=e.created_at, ticket_id=t.id, ticket_number=t.ticket_number, ticket_title=t.title, summary=described[0], unread=since is None or e.created_at > since))
        return NotificationsResponse(items=items, unread=sum(1 for i in items if i.unread))

    async def mark_notifications_seen(self) -> None:
        me = await self.repos.users.get(self.principal.profile_id)
        if me:
            me.notifications_seen_at = utcnow()
            await self.commit()

    # ── global search (⌘K) ───────────────────────────────────────────────
    async def search(self, query: str) -> SearchResults:
        from app.services.knowledge_service import KnowledgeService

        tickets, _ = await self.repos.tickets.list(self.principal, TicketFilters(query=query, limit=8, sort="updated"))
        config = await self.repos.settings.ai_configuration()
        presenter = TicketPresenter(self.repos, SlaService(self.repos.settings), self.principal, ai_threshold=float(config.confidence_threshold))
        articles = await KnowledgeService(self.repos, self.container, self.principal).list_articles(query=query, category=None, status=None)
        return SearchResults(tickets=await presenter.summaries(tickets), articles=articles[:6])
