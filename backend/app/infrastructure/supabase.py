"""Server-side Supabase access: Auth admin API and Storage.

Uses the service-role key, so this module is backend-only by construction —
nothing here is reachable from the browser. Calls go through httpx and are
traced by the OpenTelemetry httpx instrumentation (headers are never recorded).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.core.errors import AppError, ServiceUnavailable
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None
    user_metadata: dict[str, Any]


class SupabaseError(AppError):
    status_code = 502
    code = "supabase_error"


class SupabaseAdmin:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0))

    # ── plumbing ─────────────────────────────────────────────────────────
    def _require_admin(self) -> str:
        if not self._settings.supabase_admin_configured:
            raise ServiceUnavailable("Supabase service credentials are not configured.")
        return self._settings.supabase_service_role_key.get_secret_value()

    def _admin_headers(self) -> dict[str, str]:
        key = self._require_admin()
        return {"apikey": key, "Authorization": f"Bearer {key}"}

    def _url(self, path: str) -> str:
        return f"{self._settings.supabase_url}{path}"

    @staticmethod
    def _raise_for(response: httpx.Response, action: str) -> None:
        if response.is_success:
            return
        try:
            body = response.json()
            detail = body.get("msg") or body.get("message") or body.get("error_description") or body.get("error")
        except ValueError:
            detail = None
        log.warning("supabase.request_failed", action=action, status=response.status_code)
        raise SupabaseError(f"Supabase {action} failed ({response.status_code}){': ' + str(detail) if detail else ''}.")

    async def close(self) -> None:
        await self._client.aclose()

    # ── Auth: token introspection (fallback for HS256 without secret) ─────
    async def get_user_for_token(self, access_token: str) -> AuthUser | None:
        response = await self._client.get(
            self._url("/auth/v1/user"),
            headers={"apikey": self._settings.supabase_anon_key, "Authorization": f"Bearer {access_token}"},
        )
        if response.status_code in (401, 403):
            return None
        self._raise_for(response, "token validation")
        data = response.json()
        return AuthUser(id=data["id"], email=data.get("email"), user_metadata=data.get("user_metadata") or {})

    async def auth_settings(self) -> dict[str, Any]:
        response = await self._client.get(self._url("/auth/v1/settings"), headers={"apikey": self._settings.supabase_anon_key})
        self._raise_for(response, "auth settings")
        return response.json()

    # ── Auth: admin ──────────────────────────────────────────────────────
    async def create_user(self, *, email: str, password: str, full_name: str, email_confirm: bool = True) -> AuthUser:
        response = await self._client.post(
            self._url("/auth/v1/admin/users"),
            headers=self._admin_headers(),
            json={"email": email, "password": password, "email_confirm": email_confirm, "user_metadata": {"full_name": full_name}},
        )
        self._raise_for(response, "user creation")
        data = response.json()
        return AuthUser(id=data["id"], email=data.get("email"), user_metadata=data.get("user_metadata") or {})

    async def find_user_by_email(self, email: str) -> AuthUser | None:
        target = email.lower()
        page = 1
        while True:
            response = await self._client.get(
                self._url("/auth/v1/admin/users"), headers=self._admin_headers(), params={"page": page, "per_page": 200}
            )
            self._raise_for(response, "user lookup")
            users = response.json().get("users", [])
            for user in users:
                if (user.get("email") or "").lower() == target:
                    return AuthUser(id=user["id"], email=user.get("email"), user_metadata=user.get("user_metadata") or {})
            if len(users) < 200:
                return None
            page += 1

    async def update_user_password(self, user_id: str, password: str) -> None:
        response = await self._client.put(
            self._url(f"/auth/v1/admin/users/{user_id}"), headers=self._admin_headers(), json={"password": password}
        )
        self._raise_for(response, "user update")

    async def invite_user(self, *, email: str, full_name: str, redirect_to: str | None = None) -> AuthUser:
        payload: dict[str, Any] = {"email": email, "data": {"full_name": full_name}}
        params = {"redirect_to": redirect_to} if redirect_to else None
        response = await self._client.post(self._url("/auth/v1/invite"), headers=self._admin_headers(), json=payload, params=params)
        self._raise_for(response, "invite")
        data = response.json()
        return AuthUser(id=data["id"], email=data.get("email"), user_metadata=data.get("user_metadata") or {})

    # ── Storage ──────────────────────────────────────────────────────────
    async def upload(self, bucket: str, path: str, content: bytes, content_type: str) -> None:
        response = await self._client.post(
            self._url(f"/storage/v1/object/{bucket}/{quote(path)}"),
            headers={**self._admin_headers(), "Content-Type": content_type, "x-upsert": "false"},
            content=content,
        )
        self._raise_for(response, "upload")

    async def signed_url(self, bucket: str, path: str, *, expires_in: int = 300) -> str:
        response = await self._client.post(
            self._url(f"/storage/v1/object/sign/{bucket}/{quote(path)}"),
            headers=self._admin_headers(),
            json={"expiresIn": expires_in},
        )
        self._raise_for(response, "signed URL")
        signed = response.json().get("signedURL") or response.json().get("signedUrl")
        return f"{self._settings.supabase_url}/storage/v1{signed}"

    async def remove(self, bucket: str, paths: list[str]) -> None:
        response = await self._client.request(
            "DELETE", self._url(f"/storage/v1/object/{bucket}"), headers=self._admin_headers(), json={"prefixes": paths}
        )
        self._raise_for(response, "delete")
