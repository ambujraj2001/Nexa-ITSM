"""Integration providers.

Each provider implements `check()` (is it configured and reachable?) and may
later implement `notify()` / `sync()`. Adding Slack, email or monitoring later
means registering a provider here — the `integrations` table and settings UI
already model enabled flags, non-secret config and a secret *reference*.

V1 ships Supabase Auth (identity) as a live integration. The others report
their real state honestly ("not configured") instead of pretending to connect.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings


@dataclass(frozen=True)
class IntegrationStatus:
    status: str  # not_configured | connected | error | disabled
    detail: str | None = None
    available: bool = True  # False → UI shows "available in a later release"


class IntegrationProvider(Protocol):
    provider: str

    async def check(self, *, enabled: bool, settings: Settings, secret_ref: str | None) -> IntegrationStatus: ...


class SupabaseAuthProvider:
    provider = "supabase_auth"

    async def check(self, *, enabled: bool, settings: Settings, secret_ref: str | None) -> IntegrationStatus:
        if not settings.supabase_auth_configured:
            return IntegrationStatus("not_configured", "Set SUPABASE_URL and SUPABASE_ANON_KEY.")
        return IntegrationStatus("connected", "Sign-in is handled by Supabase Auth.")


class PlannedProvider:
    """Catalogued integration whose connector isn't part of V1."""

    def __init__(self, provider: str) -> None:
        self.provider = provider

    async def check(self, *, enabled: bool, settings: Settings, secret_ref: str | None) -> IntegrationStatus:
        has_secret = bool(secret_ref and os.environ.get(secret_ref))
        detail = "Credential present; connector ships in a later release." if has_secret else f"Add {secret_ref} to the environment to configure." if secret_ref else None
        return IntegrationStatus("not_configured", detail, available=False)


REGISTRY: dict[str, IntegrationProvider] = {
    "supabase_auth": SupabaseAuthProvider(),
    "slack": PlannedProvider("slack"),
    "email": PlannedProvider("email"),
    "monitoring_webhook": PlannedProvider("monitoring_webhook"),
    "asset_management": PlannedProvider("asset_management"),
}


def provider_for(name: str) -> IntegrationProvider:
    return REGISTRY.get(name) or PlannedProvider(name)
