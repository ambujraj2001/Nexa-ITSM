from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import OPEN_STATUSES
from app.models import Profile, Team, Ticket


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── profiles ─────────────────────────────────────────────────────────
    async def get(self, profile_id: uuid.UUID) -> Profile | None:
        return await self.session.get(Profile, profile_id)

    async def get_by_auth_user(self, auth_user_id: uuid.UUID) -> Profile | None:
        return (await self.session.execute(select(Profile).where(Profile.auth_user_id == auth_user_id))).scalar_one_or_none()

    async def get_by_email(self, email: str) -> Profile | None:
        stmt = select(Profile).where(func.lower(Profile.email) == email.strip().lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_many(self, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, Profile]:
        wanted = {i for i in ids if i is not None}
        if not wanted:
            return {}
        rows = (await self.session.execute(select(Profile).where(Profile.id.in_(wanted)))).scalars().all()
        return {p.id: p for p in rows}

    async def list(
        self,
        *,
        role: str | None = None,
        team_id: uuid.UUID | None = None,
        query: str | None = None,
        include_inactive: bool = False,
        limit: int = 200,
    ) -> Sequence[Profile]:
        stmt = select(Profile).order_by(Profile.name).limit(limit)
        if role:
            stmt = stmt.where(Profile.role == role)
        if team_id:
            stmt = stmt.where(Profile.team_id == team_id)
        if not include_inactive:
            stmt = stmt.where(Profile.is_active.is_(True))
        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(or_(Profile.name.ilike(like), Profile.email.ilike(like)))
        return (await self.session.execute(stmt)).scalars().all()

    async def add(self, profile: Profile) -> Profile:
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def assignable_engineers(self, team_id: uuid.UUID, level: str | None = None) -> list[tuple[Profile, int]]:
        """Active engineers in a team with their open-ticket load, least loaded first."""
        load = (
            select(Ticket.assigned_to, func.count().label("open_count"))
            .where(Ticket.status.in_([s.value for s in OPEN_STATUSES]), Ticket.assigned_to.is_not(None))
            .group_by(Ticket.assigned_to)
            .subquery()
        )
        stmt = (
            select(Profile, func.coalesce(load.c.open_count, 0))
            .outerjoin(load, load.c.assigned_to == Profile.id)
            .where(
                Profile.team_id == team_id,
                Profile.is_active.is_(True),
                Profile.role.in_(["engineer", "admin"]),
                Profile.engineer_level.is_not(None),
            )
            .order_by(func.coalesce(load.c.open_count, 0), Profile.name)
        )
        if level:
            stmt = stmt.where(Profile.engineer_level == level)
        return [(p, int(c)) for p, c in (await self.session.execute(stmt)).all()]

    async def staff_counts_by_team(self) -> dict[uuid.UUID, dict[str, int]]:
        stmt = (
            select(Profile.team_id, Profile.engineer_level, func.count())
            .where(Profile.is_active.is_(True), Profile.team_id.is_not(None), Profile.engineer_level.is_not(None))
            .group_by(Profile.team_id, Profile.engineer_level)
        )
        out: dict[uuid.UUID, dict[str, int]] = {}
        for team_id, level, count in (await self.session.execute(stmt)).all():
            out.setdefault(team_id, {})[level] = int(count)
        return out

    # ── teams ────────────────────────────────────────────────────────────
    async def get_team(self, team_id: uuid.UUID) -> Team | None:
        return await self.session.get(Team, team_id)

    async def get_team_by_name(self, name: str) -> Team | None:
        stmt = select(Team).where(func.lower(Team.name) == name.strip().lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_teams(self) -> Sequence[Team]:
        return (await self.session.execute(select(Team).order_by(Team.name))).scalars().all()

    async def teams_by_ids(self, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, Team]:
        wanted = {i for i in ids if i is not None}
        if not wanted:
            return {}
        rows = (await self.session.execute(select(Team).where(Team.id.in_(wanted)))).scalars().all()
        return {t.id: t for t in rows}

    async def service_desk(self) -> Team | None:
        stmt = select(Team).where(Team.is_service_desk.is_(True))
        team = (await self.session.execute(stmt)).scalar_one_or_none()
        if team is None:
            team = (await self.session.execute(select(Team).order_by(Team.created_at).limit(1))).scalar_one_or_none()
        return team

    async def add_team(self, team: Team) -> Team:
        self.session.add(team)
        await self.session.flush()
        return team

    async def team_member_counts(self) -> dict[uuid.UUID, int]:
        stmt = (
            select(Profile.team_id, func.count())
            .where(and_(Profile.team_id.is_not(None), Profile.is_active.is_(True)))
            .group_by(Profile.team_id)
        )
        return {tid: int(n) for tid, n in (await self.session.execute(stmt)).all()}
