"""Transient state: Upstash Redis (REST) with an in-process fallback.

Redis is never a source of truth in Nexa. It holds rate-limit counters, job
locks, engineer copilot sessions and short-lived caches. Every operation has a
timeout; failures are logged and degrade gracefully (reads miss, rate limits
fail open, locks fall back to database guards) instead of breaking requests.
"""

from __future__ import annotations

import asyncio
import fnmatch
import time
from typing import Protocol

from app.config import Settings
from app.core.logging import get_logger
from app.infrastructure.telemetry import span

log = get_logger(__name__)

_TIMEOUT_SECONDS = 2.0


class KeyValueStore(Protocol):
    backend_name: str

    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None, only_if_absent: bool = False) -> bool: ...
    async def delete(self, *keys: str) -> None: ...
    async def incr_window(self, key: str, ttl_seconds: int) -> int | None: ...
    async def push_capped(self, key: str, value: str, *, max_len: int, ttl_seconds: int) -> None: ...
    async def list_range(self, key: str, start: int = 0, stop: int = -1) -> list[str]: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class UpstashStore:
    backend_name = "upstash"

    def __init__(self, url: str, token: str) -> None:
        from upstash_redis.asyncio import Redis

        # allow_telemetry=False: the SDK must not phone home with usage metadata.
        self._client = Redis(url=url, token=token, allow_telemetry=False, rest_retries=1, rest_retry_interval=0.2)

    async def _run(self, op: str, coro):  # type: ignore[no-untyped-def]
        with span("redis.command", **{"db.system": "redis", "db.operation": op}):
            return await asyncio.wait_for(coro, timeout=_TIMEOUT_SECONDS)

    async def get(self, key: str) -> str | None:
        try:
            value = await self._run("GET", self._client.get(key))
            return None if value is None else str(value)
        except Exception as exc:  # noqa: BLE001 — degrade, never fail the request
            log.warning("redis.get_failed", error=type(exc).__name__)
            return None

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None, only_if_absent: bool = False) -> bool:
        try:
            result = await self._run("SET", self._client.set(key, value, ex=ttl_seconds, nx=only_if_absent or None))
            return result is not None and result is not False
        except Exception as exc:  # noqa: BLE001
            log.warning("redis.set_failed", error=type(exc).__name__)
            return False

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            await self._run("DEL", self._client.delete(*keys))
        except Exception as exc:  # noqa: BLE001
            log.warning("redis.delete_failed", error=type(exc).__name__)

    async def incr_window(self, key: str, ttl_seconds: int) -> int | None:
        try:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl_seconds)  # key is per-window, so re-arming the TTL is harmless
            results = await self._run("INCR+EXPIRE", pipe.exec())
            return int(results[0])
        except Exception as exc:  # noqa: BLE001
            log.warning("redis.incr_failed", error=type(exc).__name__)
            return None

    async def push_capped(self, key: str, value: str, *, max_len: int, ttl_seconds: int) -> None:
        try:
            pipe = self._client.pipeline()
            pipe.lpush(key, value)
            pipe.ltrim(key, 0, max_len - 1)
            pipe.expire(key, ttl_seconds)
            await self._run("LPUSH+LTRIM", pipe.exec())
        except Exception as exc:  # noqa: BLE001
            log.warning("redis.push_failed", error=type(exc).__name__)

    async def list_range(self, key: str, start: int = 0, stop: int = -1) -> list[str]:
        try:
            values = await self._run("LRANGE", self._client.lrange(key, start, stop))
            return [str(v) for v in values or []]
        except Exception as exc:  # noqa: BLE001
            log.warning("redis.lrange_failed", error=type(exc).__name__)
            return []

    async def ping(self) -> bool:
        try:
            return bool(await self._run("PING", self._client.ping()))
        except Exception:  # noqa: BLE001
            return False

    async def close(self) -> None:
        await self._client.close()


class InMemoryStore:
    """Single-process stand-in for local development and tests."""

    backend_name = "memory"

    def __init__(self) -> None:
        self._values: dict[str, tuple[str | list[str], float | None]] = {}
        self._lock = asyncio.Lock()

    def _alive(self, key: str) -> bool:
        item = self._values.get(key)
        if item is None:
            return False
        expires = item[1]
        if expires is not None and expires <= time.monotonic():
            self._values.pop(key, None)
            return False
        return True

    async def get(self, key: str) -> str | None:
        async with self._lock:
            if not self._alive(key):
                return None
            value = self._values[key][0]
            return value if isinstance(value, str) else None

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None, only_if_absent: bool = False) -> bool:
        async with self._lock:
            if only_if_absent and self._alive(key):
                return False
            self._values[key] = (value, time.monotonic() + ttl_seconds if ttl_seconds else None)
            return True

    async def delete(self, *keys: str) -> None:
        async with self._lock:
            for key in keys:
                self._values.pop(key, None)

    async def incr_window(self, key: str, ttl_seconds: int) -> int | None:
        async with self._lock:
            if self._alive(key):
                raw, expires = self._values[key]
                count = int(raw) + 1 if isinstance(raw, str) else 1
            else:
                count, expires = 1, time.monotonic() + ttl_seconds
            self._values[key] = (str(count), expires)
            return count

    async def push_capped(self, key: str, value: str, *, max_len: int, ttl_seconds: int) -> None:
        async with self._lock:
            existing = self._values[key][0] if self._alive(key) else []
            items = [value, *(existing if isinstance(existing, list) else [])][:max_len]
            self._values[key] = (items, time.monotonic() + ttl_seconds)

    async def list_range(self, key: str, start: int = 0, stop: int = -1) -> list[str]:
        async with self._lock:
            if not self._alive(key):
                return []
            items = self._values[key][0]
            if not isinstance(items, list):
                return []
            end = None if stop == -1 else stop + 1
            return list(items[start:end])

    async def keys(self, pattern: str) -> list[str]:
        async with self._lock:
            return [k for k in list(self._values) if self._alive(k) and fnmatch.fnmatch(k, pattern)]

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._values.clear()


def create_store(settings: Settings) -> KeyValueStore:
    if settings.redis_configured:
        return UpstashStore(settings.upstash_redis_rest_url, settings.upstash_redis_rest_token.get_secret_value())
    if settings.is_production:
        log.warning("redis.not_configured_in_production", detail="Using in-process store; limits are per-instance.")
    return InMemoryStore()
