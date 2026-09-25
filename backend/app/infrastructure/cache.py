"""Rate limiting, job locks and small JSON caches built on the key-value store."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.core.errors import RateLimited
from app.core.logging import get_logger
from app.infrastructure.redis import KeyValueStore

log = get_logger(__name__)

NAMESPACE = "nexa"


def key(*parts: object) -> str:
    return ":".join([NAMESPACE, *(str(p) for p in parts)])


class RateLimiter:
    """Fixed-window limiter. Fails open if Redis is unavailable (logged)."""

    def __init__(self, store: KeyValueStore) -> None:
        self._store = store

    async def hit(self, scope: str, subject: str, *, limit: int, window_seconds: int = 60) -> None:
        window = int(time.time() // window_seconds)
        count = await self._store.incr_window(key("rl", scope, subject, window), window_seconds + 5)
        if count is None:
            log.warning("rate_limit.store_unavailable", scope=scope)
            return
        if count > limit:
            retry_after = window_seconds - int(time.time() % window_seconds)
            raise RateLimited(
                "You're sending requests faster than Nexa can handle. Please wait a moment.",
                retry_after=max(1, retry_after),
            )


class JobLock:
    """Best-effort distributed lock (SET NX EX) so a job runs once across workers."""

    def __init__(self, store: KeyValueStore) -> None:
        self._store = store

    @asynccontextmanager
    async def hold(self, name: str, *, ttl_seconds: int) -> AsyncIterator[bool]:
        token = uuid.uuid4().hex
        lock_key = key("lock", name)
        acquired = await self._store.set(lock_key, token, ttl_seconds=ttl_seconds, only_if_absent=True)
        try:
            yield acquired
        finally:
            if acquired and await self._store.get(lock_key) == token:
                await self._store.delete(lock_key)


class JsonCache:
    def __init__(self, store: KeyValueStore) -> None:
        self._store = store

    async def get(self, cache_key: str) -> Any | None:
        raw = await self._store.get(cache_key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    async def set(self, cache_key: str, value: Any, *, ttl_seconds: int) -> None:
        await self._store.set(cache_key, json.dumps(value, default=str), ttl_seconds=ttl_seconds)

    async def invalidate(self, *cache_keys: str) -> None:
        await self._store.delete(*cache_keys)
