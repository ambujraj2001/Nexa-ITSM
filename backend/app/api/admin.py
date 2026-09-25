"""Administration: users, teams and the audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminDep, ContainerDep, ReposDep, StaffDep
from app.schemas.misc import AuditEventView, TeamView, TeamWrite, UserInvite, UserUpdate, UserView
from app.services.admin_service import AdminService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserView])
async def list_users(
    principal: AdminDep, repos: ReposDep, container: ContainerDep,
    role: str | None = None, team_id: uuid.UUID | None = None, q: Annotated[str | None, Query(max_length=120)] = None,
) -> list[UserView]:
    return await AdminService(repos, container, principal).users(role=role, team_id=team_id, query=q)


@router.patch("/users/{user_id}", response_model=UserView)
async def update_user(user_id: uuid.UUID, body: UserUpdate, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> UserView:
    return await AdminService(repos, container, principal).update_user(user_id, body)


@router.post("/users/invite", response_model=UserView, status_code=status.HTTP_201_CREATED)
async def invite_user(body: UserInvite, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> UserView:
    return await AdminService(repos, container, principal).invite(body)


@router.get("/teams", response_model=list[TeamView])
async def list_teams(principal: StaffDep, repos: ReposDep, container: ContainerDep) -> list[TeamView]:
    return await AdminService(repos, container, principal).teams()


@router.post("/teams", response_model=TeamView, status_code=status.HTTP_201_CREATED)
async def create_team(body: TeamWrite, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> TeamView:
    return await AdminService(repos, container, principal).create_team(body)


@router.put("/teams/{team_id}", response_model=TeamView)
async def update_team(team_id: uuid.UUID, body: TeamWrite, principal: AdminDep, repos: ReposDep, container: ContainerDep) -> TeamView:
    return await AdminService(repos, container, principal).update_team(team_id, body)


@router.get("/audit", response_model=list[AuditEventView])
async def audit_log(
    principal: AdminDep, repos: ReposDep, container: ContainerDep,
    entity_type: str | None = None, actor_type: Annotated[str | None, Query(pattern="^(user|ai|system)$")] = None,
    action: str | None = None, before: datetime | None = None, limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AuditEventView]:
    return await AdminService(repos, container, principal).audit_log(entity_type=entity_type, actor_type=actor_type, action=action, before=before, limit=limit)
