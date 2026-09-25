"""Supabase access-token verification.

Supports both Supabase signing schemes:
  • asymmetric signing keys (ES256/RS256) — verified locally against the
    project's JWKS, which is cached and refreshed on unknown key ids;
  • legacy HS256 — verified with SUPABASE_JWT_SECRET, or, if that isn't
    configured, by asking Supabase Auth (`/auth/v1/user`), cached briefly.

Only end-user session tokens are accepted: `aud` and `role` must be
"authenticated" and `sub` must be present. That rejects the anon and
service-role keys even though they are JWTs signed by the same project.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

from app.config import Settings
from app.core.errors import NotAuthenticated, ServiceUnavailable
from app.core.logging import get_logger
from app.infrastructure.supabase import SupabaseAdmin

log = get_logger(__name__)

_ASYMMETRIC = {"RS256", "ES256", "EdDSA"}
_JWKS_TTL_SECONDS = 600
_INTROSPECTION_TTL_SECONDS = 60
_LEEWAY_SECONDS = 30


@dataclass(frozen=True)
class VerifiedToken:
    subject: uuid.UUID
    email: str | None
    full_name: str | None
    expires_at: int | None


class TokenVerifier:
    def __init__(self, settings: Settings, admin: SupabaseAdmin, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._admin = admin
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0))
        self._jwks: dict[str, jwt.PyJWK] = {}
        self._jwks_fetched_at = 0.0
        self._jwks_lock = asyncio.Lock()
        self._introspection_cache: dict[str, tuple[VerifiedToken, float]] = {}

    @property
    def issuer(self) -> str:
        return f"{self._settings.supabase_url}/auth/v1"

    async def verify(self, token: str) -> VerifiedToken:
        if not token:
            raise NotAuthenticated("Missing access token.")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise NotAuthenticated("Malformed access token.") from exc

        alg = header.get("alg")
        if alg in _ASYMMETRIC:
            key = await self._signing_key(header.get("kid"))
            claims = self._decode(token, key.key, alg)
        elif alg == "HS256":
            secret = self._settings.supabase_jwt_secret.get_secret_value()
            if secret:
                claims = self._decode(token, secret, "HS256")
            else:
                return await self._introspect(token)
        else:
            raise NotAuthenticated("Unsupported token algorithm.")
        return self._to_verified(claims)

    def _decode(self, token: str, key: Any, alg: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[alg],
                audience="authenticated",
                issuer=self.issuer if self._settings.supabase_url else None,
                leeway=_LEEWAY_SECONDS,
                options={"require": ["exp", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise NotAuthenticated("Your session has expired. Please sign in again.", code="token_expired") from exc
        except jwt.PyJWTError as exc:
            raise NotAuthenticated("Invalid access token.") from exc
        if claims.get("role") != "authenticated":
            raise NotAuthenticated("Invalid access token.")
        return claims

    @staticmethod
    def _to_verified(claims: dict[str, Any]) -> VerifiedToken:
        try:
            subject = uuid.UUID(str(claims["sub"]))
        except (KeyError, ValueError) as exc:
            raise NotAuthenticated("Invalid access token.") from exc
        meta = claims.get("user_metadata") or {}
        return VerifiedToken(
            subject=subject,
            email=(claims.get("email") or None),
            full_name=meta.get("full_name") or meta.get("name"),
            expires_at=claims.get("exp"),
        )

    async def _signing_key(self, kid: str | None) -> jwt.PyJWK:
        if not kid:
            raise NotAuthenticated("Invalid access token.")
        fresh = time.monotonic() - self._jwks_fetched_at < _JWKS_TTL_SECONDS
        if kid in self._jwks and fresh:
            return self._jwks[kid]
        async with self._jwks_lock:
            if kid not in self._jwks or time.monotonic() - self._jwks_fetched_at >= _JWKS_TTL_SECONDS:
                await self._refresh_jwks()
        if kid not in self._jwks:
            raise NotAuthenticated("Invalid access token.")
        return self._jwks[kid]

    async def _refresh_jwks(self) -> None:
        if not self._settings.supabase_url:
            raise ServiceUnavailable("SUPABASE_URL is not configured.")
        try:
            response = await self._client.get(f"{self.issuer}/.well-known/jwks.json")
            response.raise_for_status()
            keys = response.json().get("keys", [])
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("auth.jwks_fetch_failed", error=type(exc).__name__)
            if self._jwks:
                return  # keep serving cached keys
            raise ServiceUnavailable("Could not reach Supabase Auth to verify your session.") from exc
        parsed: dict[str, jwt.PyJWK] = {}
        for jwk in keys:
            try:
                parsed[jwk["kid"]] = jwt.PyJWK(jwk)
            except (KeyError, jwt.PyJWTError):
                continue
        self._jwks = parsed
        self._jwks_fetched_at = time.monotonic()

    async def _introspect(self, token: str) -> VerifiedToken:
        digest = hashlib.sha256(token.encode()).hexdigest()
        cached = self._introspection_cache.get(digest)
        if cached and cached[1] > time.monotonic():
            return cached[0]
        user = await self._admin.get_user_for_token(token)
        if user is None:
            raise NotAuthenticated("Invalid or expired session.")
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
        except jwt.PyJWTError:
            unverified = {}
        verified = VerifiedToken(
            subject=uuid.UUID(user.id),
            email=user.email,
            full_name=user.user_metadata.get("full_name") or user.user_metadata.get("name"),
            expires_at=unverified.get("exp"),
        )
        if len(self._introspection_cache) > 5000:
            self._introspection_cache.clear()
        self._introspection_cache[digest] = (verified, time.monotonic() + _INTROSPECTION_TTL_SECONDS)
        return verified

    async def close(self) -> None:
        await self._client.aclose()
