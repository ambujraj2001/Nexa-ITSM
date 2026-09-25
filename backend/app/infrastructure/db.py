"""Supabase Postgres access via SQLAlchemy (async, asyncpg).

The API connects with the database connection string (backend-only secret).
That role owns the tables and bypasses RLS, so authorization is enforced in
`app.domain.policies`; RLS remains the guard for any direct client access.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.core.errors import ServiceUnavailable


class SessionProvider(Protocol):
    """Hands out sessions. Background jobs use this so tests can inject their own."""

    def session(self) -> AsyncIterator[AsyncSession]: ...


class Database:
    def __init__(self, settings: Settings) -> None:
        if not settings.database_configured:
            raise ServiceUnavailable("SUPABASE_DB_URL is not configured.")
        connect_args: dict[str, object] = {"timeout": 15, "command_timeout": 60}
        engine_kwargs: dict[str, object] = {}
        url = make_url(settings.async_database_url)
        query = dict(url.query)
        query.pop("pgbouncer", None)  # libpq/PgBouncer hint that asyncpg rejects
        if (sslmode := query.pop("sslmode", None)) is not None:
            # asyncpg takes libpq's mode names via `ssl`; None would mean its default ("prefer").
            if sslmode in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
                connect_args["ssl"] = sslmode
        if settings.uses_transaction_pooler:
            # Supavisor transaction mode: no server-side prepared statement reuse.
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_name_func"] = lambda: f"__nexa_{uuid.uuid4().hex}__"
            query["prepared_statement_cache_size"] = "0"
            engine_kwargs["pool_pre_ping"] = False
        else:
            engine_kwargs["pool_pre_ping"] = True
        self.engine: AsyncEngine = create_async_engine(
            url.set(query=query),
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
            connect_args=connect_args,
            **engine_kwargs,
        )
        self._sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._sessionmaker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        await self.engine.dispose()
