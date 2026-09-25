"""Apply supabase/migrations/*.sql to the database in SUPABASE_DB_URL.

Records applied versions in supabase_migrations.schema_migrations — the same
table the Supabase CLI uses — so this script and `supabase db push` agree on
what has run. Each migration runs in its own transaction.

    uv run python -m scripts.migrate            # apply pending migrations
    uv run python -m scripts.migrate --status   # list applied / pending
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

import asyncpg

from app.config import BACKEND_DIR, get_settings

MIGRATIONS_DIR = BACKEND_DIR / "supabase" / "migrations"
_NAME = re.compile(r"^(\d{14})_(.+)\.sql$")


def plain_dsn(url: str) -> str:
    """asyncpg wants a libpq-style DSN without SQLAlchemy driver or pooler hints."""
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://")
    if "?" in url:
        base, query = url.split("?", 1)
        kept = [p for p in query.split("&") if p and not p.startswith(("pgbouncer=", "prepared_statement_cache_size="))]
        url = base + ("?" + "&".join(kept) if kept else "")
    return url


def discover() -> list[tuple[str, str, Path]]:
    found = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = _NAME.match(path.name)
        if match:
            found.append((match.group(1), match.group(2), path))
    return found


async def run(status_only: bool) -> int:
    settings = get_settings()
    if not settings.database_configured:
        print("SUPABASE_DB_URL is not set. Add it to the repository .env first.", file=sys.stderr)
        return 2
    conn = await asyncpg.connect(plain_dsn(settings.supabase_db_url.get_secret_value()), statement_cache_size=0, timeout=20)
    try:
        await conn.execute(
            "create schema if not exists supabase_migrations;"
            "create table if not exists supabase_migrations.schema_migrations (version text primary key, statements text[], name text)"
        )
        applied = {r["version"] for r in await conn.fetch("select version from supabase_migrations.schema_migrations")}
        migrations = discover()
        pending = [m for m in migrations if m[0] not in applied]
        for version, name, _ in migrations:
            print(f"  {'applied ' if version in applied else 'pending '} {version}  {name}")
        if status_only or not pending:
            print("Nothing to apply." if not pending else f"{len(pending)} pending.")
            return 0
        for version, name, path in pending:
            sql = path.read_text(encoding="utf-8")
            print(f"→ applying {version}_{name} …", flush=True)
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "insert into supabase_migrations.schema_migrations (version, statements, name) values ($1, $2, $3)",
                    version,
                    [sql],
                    name,
                )
        print(f"Applied {len(pending)} migration(s).")
        return 0
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--status", action="store_true", help="show applied and pending migrations without applying")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.status)))


if __name__ == "__main__":
    main()
