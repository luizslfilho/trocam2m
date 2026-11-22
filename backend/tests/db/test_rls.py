"""Isolamento entre tenants e entre revendedores nas tabelas relacionais (Seção 4).

Este teste roda no CI e bloqueia merge.
"""

import uuid

import asyncpg
import pytest

from tests.db.conftest import World, scoped

pytestmark = pytest.mark.integration

# Catálogos globais aprovados como exceção (decisoes.md, 2026-11-22).
GLOBAL_CATALOGS = {"param_mapping", "dtc_dictionary", "alembic_version"}


class TestEstrutura:
    async def test_roles_da_aplicacao_sem_bypassrls_nem_superuser(
        self, owner: asyncpg.Connection
    ) -> None:
        rows = await owner.fetch(
            "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles "
            "WHERE rolname IN ('telemetria_app', 'telemetria_ingest')"
        )
        assert {r["rolname"] for r in rows} == {"telemetria_app", "telemetria_ingest"}
        assert all(not r["rolsuper"] and not r["rolbypassrls"] for r in rows)

    async def test_rls_ativa_em_toda_tabela_relacional(self, owner: asyncpg.Connection) -> None:
        rows = await owner.fetch(
            "SELECT c.relname, c.relrowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r'"
        )
        sem_rls = {r["relname"] for r in rows if not r["relrowsecurity"]} - GLOBAL_CATALOGS
        assert sem_rls == set()

    async def test_toda_politica_usa_o_contexto(self, owner: asyncpg.Connection) -> None:
        rows = await owner.fetch(
            "SELECT tablename, policyname, qual, with_check FROM pg_policies "
            "WHERE schemaname = 'public'"
        )
        com_politica = {r["tablename"] for r in rows}
        tabelas = await owner.fetch(
            "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity"
        )
        assert {t["relname"] for t in tabelas} <= com_politica
        for r in rows:
            expr = f"{r['qual'] or ''} {r['with_check'] or ''}"
            assert "visible_tenant_ids" in expr or "reseller_id" in expr, r["policyname"]

    async def test_tenant_id_not_null_e_indexado(self, owner: asyncpg.Connection) -> None:
        rows = await owner.fetch(
            """
            SELECT c.table_name, c.is_nullable,
                   EXISTS (
                       SELECT 1 FROM pg_index i
                       JOIN pg_class t ON t.oid = i.indrelid
                       JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = i.indkey[0]
                       WHERE t.relname = c.table_name AND a.attname = 'tenant_id'
                   ) AS indexed
            FROM information_schema.columns c
            WHERE c.table_schema = 'public' AND c.column_name = 'tenant_id'
            """
        )
        nullable_ok = {"users", "platform_credentials", "audit_log"}  # exceções aprovadas
        for r in rows:
            assert r["indexed"], f"{r['table_name']}.tenant_id sem índice"
            if r["table_name"] not in nullable_ok:
                assert r["is_nullable"] == "NO", f"{r['table_name']}.tenant_id aceita nulo"


class TestTenantContraTenant:
    async def test_le_so_o_proprio_tenant(self, app: asyncpg.Connection, world: World) -> None:
        async with scoped(app, tenant=world.tenant_a1):
            for table in ("assets", "drivers", "users", "platform_unit_map", "audit_log"):
                rows = await app.fetch(f"SELECT tenant_id FROM {table}")
                tenants = {r["tenant_id"] for r in rows}
                assert tenants == {world.tenant_a1}, table
            ids = {r["id"] for r in await app.fetch("SELECT id FROM tenants")}
            assert ids == {world.tenant_a1}

    async def test_id_alheio_nao_aparece(self, app: asyncpg.Connection, world: World) -> None:
        alheio = world.asset[world.tenant_b1]
        async with scoped(app, tenant=world.tenant_a1):
            assert await app.fetchval("SELECT count(*) FROM assets WHERE id = $1", alheio) == 0
            status = await app.execute("UPDATE assets SET label = 'x' WHERE id = $1", alheio)
            assert status == "UPDATE 0"
            status = await app.execute("DELETE FROM drivers WHERE tenant_id = $1", world.tenant_b1)
            assert status == "DELETE 0"

    async def test_nao_escreve_em_outro_tenant(self, app: asyncpg.Connection, world: World) -> None:
        async with scoped(app, tenant=world.tenant_a1):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(
                    "INSERT INTO drivers (tenant_id, name) VALUES ($1, 'Intruso')", world.tenant_b1
                )

    async def test_nao_move_linha_para_outro_tenant(
        self, app: asyncpg.Connection, world: World
    ) -> None:
        async with scoped(app, tenant=world.tenant_a1):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(
                    "UPDATE drivers SET tenant_id = $1 WHERE tenant_id = $2",
                    world.tenant_b1,
                    world.tenant_a1,
                )

    async def test_sem_contexto_nao_ve_nada(self, app: asyncpg.Connection, world: World) -> None:
        tr = app.transaction()
        await tr.start()
        try:
            for table in ("tenants", "assets", "drivers", "users", "resellers"):
                assert await app.fetchval(f"SELECT count(*) FROM {table}") == 0, table
        finally:
            await tr.rollback()

    async def test_tenant_inexistente_nao_ve_nada(self, app: asyncpg.Connection) -> None:
        async with scoped(app, tenant=uuid.uuid4()):
            assert await app.fetchval("SELECT count(*) FROM assets") == 0


class TestRevendedorContraRevendedor:
    async def test_revendedor_ve_so_os_seus_clientes(
        self, app: asyncpg.Connection, world: World
    ) -> None:
        async with scoped(app, reseller=world.reseller_x):
            ids = {r["id"] for r in await app.fetch("SELECT id FROM tenants")}
            assert ids == {world.tenant_a1, world.tenant_a2}
            assets = {r["tenant_id"] for r in await app.fetch("SELECT tenant_id FROM assets")}
            assert assets == {world.tenant_a1, world.tenant_a2}
            resellers = {r["id"] for r in await app.fetch("SELECT id FROM resellers")}
            assert resellers == {world.reseller_x}

    async def test_revendedor_com_tenant_de_outro_nao_ve_nada(
        self, app: asyncpg.Connection, world: World
    ) -> None:
        async with scoped(app, reseller=world.reseller_x, tenant=world.tenant_b1):
            assert await app.fetchval("SELECT count(*) FROM tenants") == 0
            assert await app.fetchval("SELECT count(*) FROM assets") == 0

    async def test_revendedor_nao_cria_cliente_em_outro_revendedor(
        self, app: asyncpg.Connection, world: World
    ) -> None:
        async with scoped(app, reseller=world.reseller_x):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(
                    "INSERT INTO tenants (reseller_id, name) VALUES ($1, 'Cliente roubado')",
                    world.reseller_y,
                )

    async def test_usuarios_e_credenciais_do_revendedor(
        self, app: asyncpg.Connection, world: World
    ) -> None:
        async with scoped(app, reseller=world.reseller_x):
            admins = await app.fetch("SELECT email FROM users WHERE role = 'reseller_admin'")
            assert [r["email"] for r in admins] == ["admin-x@example.test"]
            creds = await app.fetch("SELECT id FROM platform_credentials")
            assert [r["id"] for r in creds] == [world.credential_x]
        async with scoped(app, reseller=world.reseller_y):
            assert await app.fetchval("SELECT count(*) FROM platform_credentials") == 0

    async def test_cliente_nao_ve_credencial_compartilhada_nem_admin_da_revenda(
        self, app: asyncpg.Connection, world: World
    ) -> None:
        async with scoped(app, tenant=world.tenant_a1):
            assert await app.fetchval("SELECT count(*) FROM platform_credentials") == 0
            assert (
                await app.fetchval("SELECT count(*) FROM users WHERE role = 'reseller_admin'") == 0
            )
            # mas enxerga a marca do próprio revendedor
            assert await app.fetchval("SELECT id FROM resellers") == world.reseller_x
