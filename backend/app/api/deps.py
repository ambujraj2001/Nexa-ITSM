"""FastAPI dependencies: container, DB session, authenticated principal, services.

The principal is always derived server-side: verified Supabase JWT → profile row.
Role, team and ownership are never read from client input.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Container
from app.core.context import user_id_var
from app.core.errors import NotAuthenticated, PermissionDenied
from app.core.logging import get_logger
from app.core.security import VerifiedToken
from app.domain import policies
from app.domain.enums import Role, SupportLevel
from app.domain.policies import Principal
from app.infrastructure.cache import key as cache_key
from app.models import Profile
from app.services.base import Repos

log = get_logger(__name__)
_bearer = HTTPBearer(auto_error=False, description="Supabase access token")
_PROFILE_CACHE_TTL = 60


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    async with container.db.session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_repos(session: SessionDep) -> Repos:
    return Repos.for_session(session)


ReposDep = Annotated[Repos, Depends(get_repos)]


def _principal_from(profile: Profile) -> Principal:
    return Principal(
        profile_id=profile.id,
        auth_user_id=profile.auth_user_id,
        role=Role(profile.role),
        name=profile.name,
        email=profile.email,
        engineer_level=SupportLevel(profile.engineer_level) if profile.engineer_level else None,
        team_id=profile.team_id,
    )


def _principal_to_cache(p: Principal) -> dict[str, str | None]:
    return {
        "profile_id": str(p.profile_id), "auth_user_id": str(p.auth_user_id) if p.auth_user_id else None, "role": p.role.value,
        "name": p.name, "email": p.email, "engineer_level": p.engineer_level.value if p.engineer_level else None,
        "team_id": str(p.team_id) if p.team_id else None,
    }


def _principal_from_cache(data: dict) -> Principal:
    return Principal(
        profile_id=uuid.UUID(data["profile_id"]),
        auth_user_id=uuid.UUID(data["auth_user_id"]) if data.get("auth_user_id") else None,
        role=Role(data["role"]),
        name=data["name"],
        email=data["email"],
        engineer_level=SupportLevel(data["engineer_level"]) if data.get("engineer_level") else None,
        team_id=uuid.UUID(data["team_id"]) if data.get("team_id") else None,
    )


async def _load_or_provision(repos: Repos, auth_user_id: uuid.UUID, email: str | None, full_name: str | None) -> Profile:
    profile = await repos.users.get_by_auth_user(auth_user_id)
    if profile is not None:
        return profile
    # The auth trigger normally creates the profile; this covers users created
    # before the migration ran. New profiles are always employees.
    if email:
        existing = await repos.users.get_by_email(email)
        if existing is not None:
            if existing.auth_user_id is None:
                existing.auth_user_id = auth_user_id
                await repos.session.commit()
                return existing
            log.warning("auth.profile_email_conflict")
            raise PermissionDenied("Your account isn't set up correctly. Contact your IT admin.", code="profile_conflict")
    profile = await repos.users.add(
        Profile(auth_user_id=auth_user_id, email=(email or f"{auth_user_id}@unknown").lower(), name=full_name or (email or "New user").split("@")[0], role=Role.EMPLOYEE.value)
    )
    await repos.session.commit()
    return profile


async def get_verified_token(
    container: ContainerDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> VerifiedToken:
    """Authenticate before anything touches the database (401 beats 503)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise NotAuthenticated("Sign in to continue.")
    return await container.verifier.verify(credentials.credentials)


async def get_principal(
    verified: Annotated[VerifiedToken, Depends(get_verified_token)],
    container: ContainerDep,
    repos: ReposDep,
) -> Principal:
    ck = cache_key("profile", verified.subject)
    cached = await container.cache.get(ck)
    principal: Principal | None = None
    if isinstance(cached, dict):
        try:
            principal = _principal_from_cache(cached)
        except (KeyError, ValueError):
            principal = None
    if principal is None:
        profile = await _load_or_provision(repos, verified.subject, verified.email, verified.full_name)
        if not profile.is_active:
            raise PermissionDenied("Your account has been deactivated.", code="account_inactive")
        principal = _principal_from(profile)
        await container.cache.set(ck, _principal_to_cache(principal), ttl_seconds=_PROFILE_CACHE_TTL)
    user_id_var.set(str(principal.profile_id))
    trace.get_current_span().set_attribute("enduser.id", str(principal.profile_id))
    trace.get_current_span().set_attribute("enduser.role", principal.role.value)
    return principal


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_staff(principal: PrincipalDep) -> Principal:
    policies.ensure_staff(principal)
    return principal


def require_admin(principal: PrincipalDep) -> Principal:
    policies.ensure_admin(principal)
    return principal


StaffDep = Annotated[Principal, Depends(require_staff)]
AdminDep = Annotated[Principal, Depends(require_admin)]


def home_path(principal: Principal) -> str:
    if principal.is_admin:
        return "/settings/ai"
    if principal.is_engineer:
        return "/dispatch"
    return "/assistant"
