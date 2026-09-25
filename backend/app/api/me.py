"""Current user, global search, notifications and health."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import ContainerDep, PrincipalDep, ReposDep, home_path
from app.core.logging import get_logger
from app.schemas.common import OkResponse
from app.schemas.misc import MeView, NotificationsResponse, ProfileUpdate, SearchResults
from app.services.admin_service import AdminService
from app.services.audit_service import AuditService
from app.services.presenters import team_ref

log = get_logger(__name__)
router = APIRouter(tags=["me"])


async def _me(repos: ReposDep, principal: PrincipalDep) -> MeView:
    profile = await repos.users.get(principal.profile_id)
    team = await repos.users.get_team(profile.team_id) if profile and profile.team_id else None
    return MeView(
        id=principal.profile_id, name=profile.name if profile else principal.name, email=principal.email, role=principal.role.value,
        engineer_level=principal.engineer_level.value if principal.engineer_level else None, team=team_ref(team),
        job_title=profile.job_title if profile else None, department=profile.department if profile else None,
        location=profile.location if profile else None, avatar_url=profile.avatar_url if profile else None, home_path=home_path(principal),
    )


@router.get("/api/me", response_model=MeView)
async def me(principal: PrincipalDep, repos: ReposDep) -> MeView:
    return await _me(repos, principal)


@router.patch("/api/me", response_model=MeView)
async def update_me(body: ProfileUpdate, principal: PrincipalDep, repos: ReposDep, container: ContainerDep) -> MeView:
    profile = await repos.users.get(principal.profile_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if profile and changes:
        old = {k: getattr(profile, k) for k in changes}
        for k, v in changes.items():
            setattr(profile, k, v.strip())
        await AuditService(repos.audit).record("profile.updated", actor=principal, entity_type="profile", entity_id=profile.id, old_value=old, new_value=changes)
        await repos.session.commit()
        if profile.auth_user_id:
            from app.infrastructure.cache import key as cache_key

            await container.store.delete(cache_key("profile", profile.auth_user_id))
    return await _me(repos, principal)


@router.get("/api/search", response_model=SearchResults)
async def search(q: Annotated[str, Query(min_length=2, max_length=200)], principal: PrincipalDep, repos: ReposDep, container: ContainerDep) -> SearchResults:
    return await AdminService(repos, container, principal).search(q)


@router.get("/api/notifications", response_model=NotificationsResponse)
async def notifications(principal: PrincipalDep, repos: ReposDep, container: ContainerDep) -> NotificationsResponse:
    return await AdminService(repos, container, principal).notifications()


@router.post("/api/notifications/seen", response_model=OkResponse)
async def notifications_seen(principal: PrincipalDep, repos: ReposDep, container: ContainerDep) -> OkResponse:
    await AdminService(repos, container, principal).mark_notifications_seen()
    return OkResponse()


@router.get("/health")
async def health(container: ContainerDep) -> dict:
    """Liveness plus non-secret configuration flags (used by the sign-in page)."""
    s = container.settings
    return {
        "status": "ok",
        "version": s.app_version,
        "environment": s.app_env,
        "configured": {
            "database": s.database_configured,
            "auth": s.supabase_auth_configured,
            "ai": container.ai_available,
            "embeddings": s.embeddings_configured,
            "redis": container.store.backend_name,
            "telemetry": s.axiom_configured,
        },
    }


@router.get("/health/ready")
async def ready(container: ContainerDep) -> dict:
    checks: dict[str, str] = {}
    try:
        async with container.db.session() as session:
            await session.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {type(exc).__name__}"
    checks["redis"] = "ok" if await container.store.ping() else "unavailable"
    ok = checks["database"] == "ok"
    return {"status": "ok" if ok else "degraded", "checks": checks}
