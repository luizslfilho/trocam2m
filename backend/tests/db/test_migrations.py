"""Migrations sobem do zero, descem até a base sem erro e sobem de novo."""

import asyncpg
import pytest

from tests.db.conftest import alembic, asyncpg_dsn, create_empty_database

pytestmark = pytest.mark.integration

DB = "telemetria_migrations_test"


async def _public_tables(dsn: str) -> set[str]:
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname IN ('public', 'telemetry_internal')"
        )
    finally:
        await conn.close()
    return {r["tablename"] for r in rows}


async def test_migrations_sobem_descem_e_sobem() -> None:
    await create_empty_database(DB)
    dsn = asyncpg_dsn("MIGRATION_DATABASE_URL", DB)

    up = alembic(DB, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    tables = await _public_tables(dsn)
    assert {"tenants", "users", "audit_log", "telemetry_raw", "ingest_tokens"} <= tables

    down = alembic(DB, "downgrade", "base")
    assert down.returncode == 0, down.stderr
    assert await _public_tables(dsn) <= {"alembic_version"}

    again = alembic(DB, "upgrade", "head")
    assert again.returncode == 0, again.stderr
