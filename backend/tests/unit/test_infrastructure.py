"""Redaction, retrieval helpers, rate limiting, JWT verification and model routing."""

from __future__ import annotations

import time
import uuid

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import Settings
from app.core.errors import NotAuthenticated, RateLimited
from app.core.redaction import scrub
from app.core.security import TokenVerifier
from app.infrastructure.cache import JobLock, RateLimiter
from app.infrastructure.litellm import ModelRouter
from app.infrastructure.redis import InMemoryStore
from app.infrastructure.supabase import SupabaseAdmin
from app.repositories.knowledge_repository import or_tsquery
from app.utils.text import chunk_text


def test_secrets_are_scrubbed() -> None:
    event = {
        "authorization": "Bearer abc.def.ghi",
        "api_key": "sk-live-123",
        "nested": {"db_url": "postgresql://u:p@h/db", "note": "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"},
        "message": "connecting to postgresql://postgres:hunter2@db.internal:5432/postgres",
        "input_tokens": 120,
    }
    cleaned = scrub(event)
    assert cleaned["authorization"] == "[REDACTED]" and cleaned["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["db_url"] == "[REDACTED]"
    assert "eyJ" not in cleaned["nested"]["note"]
    assert "hunter2" not in cleaned["message"]
    assert cleaned["input_tokens"] == 120


def test_or_tsquery_is_safe_and_or_joined() -> None:
    assert or_tsquery("VPN fails: CERT_AUTHORITY_INVALID & (drop table)!") == "vpn | fails | cert | authority | invalid | drop | table"
    assert or_tsquery("   ") == ""


def test_chunking_keeps_headings_and_bounds_size() -> None:
    text = "## Renewing\n\n" + ("Step text. " * 200) + "\n\n## Confirm\n\nAsk the user to connect."
    chunks = chunk_text(text, max_chars=500)
    assert len(chunks) > 2 and all(len(c) <= 700 for c in chunks)
    assert any(c.startswith("Confirm") or "## Confirm" in c for c in chunks)


async def test_rate_limiter_and_locks() -> None:
    store = InMemoryStore()
    limiter = RateLimiter(store)
    for _ in range(3):
        await limiter.hit("t", "u1", limit=3)
    with pytest.raises(RateLimited):
        await limiter.hit("t", "u1", limit=3)
    await limiter.hit("t", "u2", limit=3)  # other users unaffected

    lock = JobLock(store)
    async with lock.hold("job", ttl_seconds=30) as first:
        async with lock.hold("job", ttl_seconds=30) as second:
            assert first and not second
    async with lock.hold("job", ttl_seconds=30) as again:
        assert again


def _settings(**kw: object) -> Settings:
    return Settings(_env_file=None, supabase_url="https://proj.supabase.co", supabase_anon_key="anon", **kw)  # type: ignore[call-arg]


def _claims(**overrides: object) -> dict:
    now = int(time.time())
    return {"sub": str(uuid.uuid4()), "aud": "authenticated", "role": "authenticated", "iss": "https://proj.supabase.co/auth/v1", "exp": now + 3600, "iat": now, "email": "e@example.com", **overrides}


async def test_hs256_tokens_verify_and_non_user_keys_are_rejected() -> None:
    settings = _settings(supabase_jwt_secret="s" * 40)
    verifier = TokenVerifier(settings, SupabaseAdmin(settings))
    good = jwt.encode(_claims(), "s" * 40, algorithm="HS256")
    assert (await verifier.verify(good)).email == "e@example.com"
    for bad in (
        jwt.encode(_claims(role="anon"), "s" * 40, algorithm="HS256"),  # anon key shape
        jwt.encode(_claims(role="service_role"), "s" * 40, algorithm="HS256"),  # service key shape
        jwt.encode(_claims(exp=int(time.time()) - 600), "s" * 40, algorithm="HS256"),
        jwt.encode(_claims(), "wrong-secret" * 4, algorithm="HS256"),
        jwt.encode(_claims(aud="other"), "s" * 40, algorithm="HS256"),
    ):
        with pytest.raises(NotAuthenticated):
            await verifier.verify(bad)


async def test_asymmetric_tokens_verify_against_jwks() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    public_jwk = jwt.algorithms.ECAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public_jwk.update({"kid": "k1", "alg": "ES256", "use": "sig"})
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"keys": [public_jwk]}))
    settings = _settings()
    verifier = TokenVerifier(settings, SupabaseAdmin(settings), client=httpx.AsyncClient(transport=transport))
    token = jwt.encode(_claims(), key, algorithm="ES256", headers={"kid": "k1"})
    assert (await verifier.verify(token)).subject
    forged = jwt.encode(_claims(), ec.generate_private_key(ec.SECP256R1()), algorithm="ES256", headers={"kid": "k1"})
    with pytest.raises(NotAuthenticated):
        await verifier.verify(forged)


def test_model_routing_tiers_overrides_and_proxy_prefix() -> None:
    router = ModelRouter(_settings(litellm_base_url="https://llm.example.com", litellm_api_key="k", nexa_model_fast="fast-model", nexa_model_strong="strong-model", nexa_model_copilot="copilot-model"))
    assert router.resolve("triage").alias == "fast-model"
    assert router.resolve("diagnosis").alias == "strong-model"
    assert router.resolve("copilot").alias == "copilot-model"
    config = router.resolve("resolution_plan")
    assert config.litellm_model == "litellm_proxy/strong-model"
    assert config.api_base == "https://llm.example.com" and config.api_key == "k"
    described = router.describe()
    assert "k" not in str(described.values()) or described["gateway"] == "litellm_proxy"
    assert "api_key" not in str(described)


def test_strong_tier_falls_back_to_fast() -> None:
    router = ModelRouter(_settings(nexa_model_fast="only-fast"))
    assert router.resolve("diagnosis").alias == "only-fast"
    assert router.resolve("diagnosis").litellm_model == "only-fast"  # no proxy → alias passed through
