"""Telemetria fora de RLS (exceção aprovada em 2026-11-22): acesso só por funções com
contexto obrigatório, role de ingestão só com INSERT, idempotência e dia no fuso do tenant.

Este teste roda no CI e bloqueia merge.
"""

from datetime import UTC, date, datetime, timedelta

import asyncpg
import pytest

from tests.db.conftest import World, scoped

pytestmark = pytest.mark.integration

INSERT = (
    "INSERT INTO telemetry_internal.telemetry_raw "
    "(tenant_id, asset_id, source, ts_utc, speed_kmh, ignition, odometer_km) "
    "VALUES ($1, $2, 'wialon', $3, $4, true, $5) ON CONFLICT DO NOTHING"
)

HOURLY_FROM = datetime(2026, 3, 9, tzinfo=UTC)
HOURLY_TO = datetime(2026, 3, 13, tzinfo=UTC)


@pytest.fixture(scope="session")
async def telemetry(world: World, migrated_db: str) -> World:
    """Duas amostras por ativo, gravadas pela role de ingestão."""
    from tests.db.conftest import _connect

    async with _connect("INGEST_DATABASE_URL", migrated_db) as conn:
        for tenant, asset in world.asset.items():
            for i in range(2):
                await conn.execute(
                    INSERT, tenant, asset, world.t0 + timedelta(minutes=i), 50.0 + i, 1000.0 + i
                )
    return world


class TestPrivilegios:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM telemetry_internal.telemetry_raw",
            "SELECT * FROM telemetry_internal.telemetry_hourly",
        ],
    )
    async def test_app_nao_acessa_telemetria_direto(
        self, app: asyncpg.Connection, telemetry: World, sql: str
    ) -> None:
        async with scoped(app, tenant=telemetry.tenant_a1):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.fetch(sql)

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM telemetry_internal.telemetry_raw",
            "SELECT * FROM telemetry_internal.telemetry_hourly",
            "UPDATE telemetry_internal.telemetry_raw SET speed_kmh = 0",
            "DELETE FROM telemetry_internal.telemetry_raw",
        ],
    )
    async def test_ingest_so_insere(self, ingest: asyncpg.Connection, sql: str) -> None:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await ingest.execute(sql)

    async def test_ingest_nao_le_cadastro_nem_funcoes_de_leitura(
        self, ingest: asyncpg.Connection, telemetry: World
    ) -> None:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await ingest.fetch("SELECT * FROM assets")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await ingest.fetch(
                "SELECT * FROM app.telemetry_raw_range($1, $2, $3)",
                telemetry.asset[telemetry.tenant_a1],
                HOURLY_FROM,
                HOURLY_TO,
            )

    async def test_ingest_nao_grava_ativo_com_tenant_errado(
        self, ingest: asyncpg.Connection, telemetry: World
    ) -> None:
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await ingest.execute(
                INSERT,
                telemetry.tenant_a1,
                telemetry.asset[telemetry.tenant_b1],
                telemetry.t0,
                10.0,
                1.0,
            )


class TestContextoObrigatorio:
    @pytest.mark.parametrize(
        "call",
        [
            "SELECT * FROM app.telemetry_raw_range($1, '2026-03-09', '2026-03-13')",
            "SELECT * FROM app.telemetry_hourly_range('2026-03-09', '2026-03-13', ARRAY[$1::uuid])",
            "SELECT * FROM app.telemetry_daily('2026-03-09', '2026-03-13', ARRAY[$1::uuid])",
        ],
    )
    async def test_sem_contexto_da_erro_em_vez_de_vazio(
        self, app: asyncpg.Connection, telemetry: World, call: str
    ) -> None:
        tr = app.transaction()
        await tr.start()
        try:
            with pytest.raises(asyncpg.InsufficientPrivilegeError, match="contexto de tenant"):
                await app.fetch(call, telemetry.asset[telemetry.tenant_a1])
        finally:
            await tr.rollback()

    async def test_revendedor_com_tenant_de_outro_da_erro(
        self, app: asyncpg.Connection, telemetry: World
    ) -> None:
        async with scoped(app, reseller=telemetry.reseller_x, tenant=telemetry.tenant_b1):
            with pytest.raises(asyncpg.InsufficientPrivilegeError, match="fora do escopo"):
                await app.fetch(
                    "SELECT * FROM app.telemetry_hourly_range($1, $2)", HOURLY_FROM, HOURLY_TO
                )


class TestIsolamentoNasFuncoes:
    async def test_tenant_le_so_o_proprio(self, app: asyncpg.Connection, telemetry: World) -> None:
        a1 = telemetry.tenant_a1
        async with scoped(app, tenant=a1):
            proprio = await app.fetch(
                "SELECT * FROM app.telemetry_raw_range($1, $2, $3)",
                telemetry.asset[a1],
                HOURLY_FROM,
                HOURLY_TO,
            )
            assert len(proprio) == 2
            alheio = await app.fetch(
                "SELECT * FROM app.telemetry_raw_range($1, $2, $3)",
                telemetry.asset[telemetry.tenant_b1],
                HOURLY_FROM,
                HOURLY_TO,
            )
            assert alheio == []
            hourly = await app.fetch(
                "SELECT DISTINCT tenant_id FROM app.telemetry_hourly_range($1, $2)",
                HOURLY_FROM,
                HOURLY_TO,
            )
            assert {r["tenant_id"] for r in hourly} == {a1}
            daily = await app.fetch(
                "SELECT DISTINCT tenant_id FROM app.telemetry_daily($1, $2)",
                date(2026, 3, 9),
                date(2026, 3, 12),
            )
            assert {r["tenant_id"] for r in daily} == {a1}

    async def test_revendedor_le_so_os_seus_clientes(
        self, app: asyncpg.Connection, telemetry: World
    ) -> None:
        async with scoped(app, reseller=telemetry.reseller_x):
            rows = await app.fetch(
                "SELECT DISTINCT tenant_id FROM app.telemetry_hourly_range($1, $2)",
                HOURLY_FROM,
                HOURLY_TO,
            )
            assert {r["tenant_id"] for r in rows} == {telemetry.tenant_a1, telemetry.tenant_a2}
            alheio = await app.fetch(
                "SELECT * FROM app.telemetry_raw_range($1, $2, $3)",
                telemetry.asset[telemetry.tenant_b1],
                HOURLY_FROM,
                HOURLY_TO,
            )
            assert alheio == []


class TestIdempotencia:
    async def test_duplicado_e_ignorado(
        self, ingest: asyncpg.Connection, owner: asyncpg.Connection, telemetry: World
    ) -> None:
        t, a = telemetry.tenant_a2, telemetry.asset[telemetry.tenant_a2]
        ts = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
        assert await ingest.execute(INSERT, t, a, ts, 40.0, 10.0) == "INSERT 0 1"
        assert await ingest.execute(INSERT, t, a, ts, 99.0, 99.0) == "INSERT 0 0"
        row = await owner.fetchrow(
            "SELECT count(*) AS n, max(speed_kmh) AS v FROM telemetry_internal.telemetry_raw "
            "WHERE asset_id = $1 AND ts_utc = $2",
            a,
            ts,
        )
        assert row is not None
        assert (row["n"], row["v"]) == (1, 40.0)

    async def test_duplicado_em_chunk_comprimido_e_ignorado(
        self, ingest: asyncpg.Connection, owner: asyncpg.Connection, telemetry: World
    ) -> None:
        t, a = telemetry.tenant_b1, telemetry.asset[telemetry.tenant_b1]
        ts = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)  # dado antigo, chega atrasado
        assert await ingest.execute(INSERT, t, a, ts, 30.0, 5.0) == "INSERT 0 1"
        await owner.execute(
            "SELECT compress_chunk(c, if_not_compressed => true) "
            "FROM show_chunks('telemetry_internal.telemetry_raw', older_than => $1::timestamptz) c",
            ts + timedelta(days=1),
        )
        compressed = await owner.fetchval(
            "SELECT count(*) FROM timescaledb_information.chunks "
            "WHERE hypertable_name = 'telemetry_raw' AND is_compressed"
        )
        assert compressed >= 1
        assert await ingest.execute(INSERT, t, a, ts, 77.0, 77.0) == "INSERT 0 0"
        n = await owner.fetchval(
            "SELECT count(*) FROM telemetry_internal.telemetry_raw WHERE asset_id = $1 "
            "AND ts_utc = $2",
            a,
            ts,
        )
        assert n == 1


class TestDiaNoFusoDoTenant:
    """Evento às 23h30 locais cai no dia local, não no dia UTC (1.6)."""

    @pytest.mark.parametrize(
        ("tenant_key", "ts_utc"),
        [
            ("a1", datetime(2026, 4, 11, 2, 30, tzinfo=UTC)),  # 23h30 em São Paulo (UTC-3)
            ("a2", datetime(2026, 4, 11, 3, 30, tzinfo=UTC)),  # 23h30 em Manaus (UTC-4)
        ],
    )
    async def test_23h30_local(
        self,
        ingest: asyncpg.Connection,
        owner: asyncpg.Connection,
        app: asyncpg.Connection,
        telemetry: World,
        tenant_key: str,
        ts_utc: datetime,
    ) -> None:
        tenant = {"a1": telemetry.tenant_a1, "a2": telemetry.tenant_a2}[tenant_key]
        asset = telemetry.asset[tenant]
        await ingest.execute(INSERT, tenant, asset, ts_utc, 20.0, 1.0)
        await owner.execute(
            "CALL refresh_continuous_aggregate("
            "'telemetry_internal.telemetry_hourly', $1::timestamptz, $2::timestamptz)",
            datetime(2026, 4, 10, tzinfo=UTC),
            datetime(2026, 4, 12, tzinfo=UTC),
        )
        async with scoped(app, tenant=tenant):
            rows = await app.fetch(
                "SELECT day, samples FROM app.telemetry_daily($1, $2, ARRAY[$3::uuid])",
                date(2026, 4, 9),
                date(2026, 4, 12),
                asset,
            )
        assert [(r["day"], r["samples"]) for r in rows] == [(date(2026, 4, 10), 1)]
