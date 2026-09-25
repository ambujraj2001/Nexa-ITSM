"""In-process background jobs (AI investigation, indexing, summaries).

Jobs run as asyncio tasks after the request that scheduled them returns, so
long-running agent work never blocks an HTTP response. Each job opens its own
database session. Crash safety: investigations left pending/running by a dead
worker are recovered on startup (see InvestigationService.recover_stale).
Tests switch to `inline=True` so jobs complete before assertions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.context import request_id_var
from app.core.logging import get_logger

log = get_logger(__name__)


class BackgroundJobs:
    def __init__(self, *, inline: bool = False) -> None:
        self.inline = inline
        self._tasks: set[asyncio.Task[Any]] = set()

    async def spawn(self, name: str, factory: Callable[[], Awaitable[Any]]) -> None:
        if self.inline:
            await self._run(name, factory)
            return
        task = asyncio.create_task(self._run(name, factory), name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, name: str, factory: Callable[[], Awaitable[Any]]) -> None:
        token = request_id_var.set(request_id_var.get())
        try:
            await factory()
        except Exception:
            log.exception("job.failed", job=name)
        finally:
            request_id_var.reset(token)

    @property
    def pending(self) -> int:
        return len(self._tasks)

    async def drain(self, timeout: float = 30.0) -> None:
        if self._tasks:
            await asyncio.wait(set(self._tasks), timeout=timeout)

    async def shutdown(self, timeout: float = 10.0) -> None:
        await self.drain(timeout)
        for task in list(self._tasks):
            task.cancel()
