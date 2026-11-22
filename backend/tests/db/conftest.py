"""Banco de teste real: cria um banco limpo, aplica as migrations e semeia um mundo fictício.

Três conexões, uma por role: `owner` (dona do schema, só para preparar o cenário),
`app` (API, sujeita a RLS) e `ingest` (worker, só INSERT na telemetria).
Todo nome, placa e identificador aqui é fictício.
"""

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEST_DB = os.environ.get("TEST_DATABASE_NAME", "telemetria_test")


def _url(env: str) -> str:
    value = os.environ.get(env)
    if not value:
        pytest.skip(f"{env} não definida; testes de banco precisam do TimescaleDB")
    return value


def sqlalchemy_url(env: str, database: str) -> str:
    return make_url(_url(env)).set(database=database).render_as_string(hide_password=False)


def asyncpg_dsn(env: str, database: str) -> str:
    url = make_url(_url(env)).set(drivername="postgresql", database=database)
    return url.render_as_string(hide_password=False)


async def create_empty_database(name: str) -> None:
    """Banco novo com TimescaleDB e os mesmos grants de base do init do container."""
    maintenance = make_url(_url("MIGRATION_DATABASE_URL")).database or "postgres"
    admin = await asyncpg.connect(asyncpg_dsn("MIGRATION_DATABASE_URL", maintenance))
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()
    conn = await asyncpg.connect(asyncpg_dsn("MIGRATION_DATABASE_URL", name))
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
        await conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        await conn.execute("GRANT USAGE ON SCHEMA public TO telemetria_app, telemetria_ingest")
        await conn.execute(
            f'GRANT CONNECT ON DATABASE "{name}" TO telemetria_app, telemetria_ingest'
        )
    finally:
        await conn.close()


def alembic(database: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "MIGRATION_DATABASE_URL": sqlalchemy_url("MIGRATION_DATABASE_URL", database),
    }
    return subprocess.run(  # noqa: S603 - comando fixo, sem entrada externa
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@dataclass(frozen=True)
class World:
    reseller_x: uuid.UUID
    reseller_y: uuid.UUID
    tenant_a1: uuid.UUID  # revendedor X, America/Sao_Paulo
    tenant_a2: uuid.UUID  # revendedor X, America/Manaus
    tenant_b1: uuid.UUID  # revendedor Y, America/Sao_Paulo
    asset: dict[uuid.UUID, uuid.UUID]  # tenant -> ativo
    driver: dict[uuid.UUID, uuid.UUID]  # tenant -> motorista
    credential_x: uuid.UUID  # credencial compartilhada do revendedor X
    t0: datetime


@pytest.fixture(scope="session")
async def migrated_db() -> str:
    await create_empty_database(TEST_DB)
    result = alembic(TEST_DB, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    return TEST_DB


@asynccontextmanager
async def _connect(env: str, database: str) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(asyncpg_dsn(env, database))
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def owner(migrated_db: str) -> AsyncIterator[asyncpg.Connection]:
    async with _connect("MIGRATION_DATABASE_URL", migrated_db) as conn:
        yield conn


@pytest.fixture
async def app(migrated_db: str) -> AsyncIterator[asyncpg.Connection]:
    async with _connect("DATABASE_URL", migrated_db) as conn:
        yield conn


@pytest.fixture
async def ingest(migrated_db: str) -> AsyncIterator[asyncpg.Connection]:
    async with _connect("INGEST_DATABASE_URL", migrated_db) as conn:
        yield conn


@asynccontextmanager
async def scoped(
    conn: asyncpg.Connection,
    *,
    tenant: uuid.UUID | None = None,
    reseller: uuid.UUID | None = None,
) -> AsyncIterator[asyncpg.Connection]:
    """Transação com contexto (SET LOCAL), sempre desfeita no fim."""
    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute(
            "SELECT set_config('app.tenant_id', $1, true), set_config('app.reseller_id', $2, true)",
            str(tenant) if tenant else "",
            str(reseller) if reseller else "",
        )
        yield conn
    finally:
        await tr.rollback()


@pytest.fixture(scope="session")
async def world(migrated_db: str) -> World:
    t0 = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
    async with _connect("MIGRATION_DATABASE_URL", migrated_db) as conn:
        rx = await conn.fetchval(
            "INSERT INTO resellers (name, slug, hosts) "
            "VALUES ('Revenda X', 'x', '{x.example.test}') RETURNING id"
        )
        ry = await conn.fetchval(
            "INSERT INTO resellers (name, slug, hosts) "
            "VALUES ('Revenda Y', 'y', '{y.example.test}') RETURNING id"
        )
        tenants = {}
        for key, reseller, tz in (
            ("a1", rx, "America/Sao_Paulo"),
            ("a2", rx, "America/Manaus"),
            ("b1", ry, "America/Sao_Paulo"),
        ):
            tenants[key] = await conn.fetchval(
                "INSERT INTO tenants (reseller_id, name, timezone) "
                "VALUES ($1, $2, $3) RETURNING id",
                reseller,
                f"Cliente {key.upper()}",
                tz,
            )
        assets, drivers = {}, {}
        for key, tid in tenants.items():
            assets[tid] = await conn.fetchval(
                "INSERT INTO assets (tenant_id, category, label, plate, source, external_id) "
                "VALUES ($1, 'truck', $2, $3, 'wialon', $4) RETURNING id",
                tid,
                f"Caminhão {key}",
                f"TST{key.upper()}01",
                f"unit-{key}",
            )
            drivers[tid] = await conn.fetchval(
                "INSERT INTO drivers (tenant_id, name, rfid_code) VALUES ($1, $2, $3) RETURNING id",
                tid,
                f"Motorista Fictício {key}",
                f"RFID-{key}",
            )
            await conn.execute(
                "INSERT INTO users (reseller_id, tenant_id, email, role) "
                "VALUES ($1, $2, $3, 'fleet_manager')",
                rx if key != "b1" else ry,
                tid,
                f"gestor-{key}@example.test",
            )
        for reseller, slug in ((rx, "x"), (ry, "y")):
            await conn.execute(
                "INSERT INTO users (reseller_id, email, role) VALUES ($1, $2, 'reseller_admin')",
                reseller,
                f"admin-{slug}@example.test",
            )
        cred = await conn.fetchval(
            "INSERT INTO platform_credentials "
            "(reseller_id, platform, label, encrypted_secret, key_id) "
            "VALUES ($1, 'wialon', 'Wialon da revenda X', '\\x00'::bytea, 'dev-key') RETURNING id",
            rx,
        )
        await conn.execute(
            "INSERT INTO platform_unit_map "
            "(reseller_id, tenant_id, credential_id, external_unit_id, asset_id) "
            "VALUES ($1, $2, $3, 'unit-a1', $4)",
            rx,
            tenants["a1"],
            cred,
            assets[tenants["a1"]],
        )
        for tid in tenants.values():
            await conn.execute(
                "INSERT INTO audit_log (reseller_id, tenant_id, action, entity) "
                "SELECT reseller_id, id, 'seed', 'tenant' FROM tenants WHERE id = $1",
                tid,
            )
    return World(
        reseller_x=rx,
        reseller_y=ry,
        tenant_a1=tenants["a1"],
        tenant_a2=tenants["a2"],
        tenant_b1=tenants["b1"],
        asset=assets,
        driver=drivers,
        credential_x=cred,
        t0=t0,
    )
