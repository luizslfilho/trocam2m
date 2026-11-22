"""Regras de integridade aprovadas em 2026-11-22: papéis × tenant, mapeamento de unidades,
auditoria append-only, catálogos globais e seed do dicionário de DTC."""

import asyncpg
import pytest

from tests.db.conftest import World, scoped

pytestmark = pytest.mark.integration


class TestUsuarios:
    @pytest.mark.parametrize(
        ("role", "with_tenant"),
        [("reseller_admin", True), ("admin", False), ("fleet_manager", False), ("driver", False)],
    )
    async def test_papel_x_tenant(
        self, owner: asyncpg.Connection, world: World, role: str, with_tenant: bool
    ) -> None:
        with pytest.raises(asyncpg.CheckViolationError):
            await owner.execute(
                "INSERT INTO users (reseller_id, tenant_id, email, role) "
                "VALUES ($1, $2, $3, $4::user_role)",
                world.reseller_x,
                world.tenant_a1 if with_tenant else None,
                f"invalido-{role}@example.test",
                role,
            )

    async def test_driver_so_com_motorista_do_proprio_tenant(
        self, owner: asyncpg.Connection, world: World
    ) -> None:
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await owner.execute(
                "INSERT INTO users (reseller_id, tenant_id, email, role, driver_id) "
                "VALUES ($1, $2, 'mot@example.test', 'driver', $3)",
                world.reseller_x,
                world.tenant_a1,
                world.driver[world.tenant_b1],
            )

    async def test_tenant_precisa_ser_do_revendedor_do_usuario(
        self, owner: asyncpg.Connection, world: World
    ) -> None:
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await owner.execute(
                "INSERT INTO users (reseller_id, tenant_id, email, role) "
                "VALUES ($1, $2, 'cruzado@example.test', 'viewer')",
                world.reseller_y,
                world.tenant_a1,
            )


class TestMapeamentoDeUnidades:
    async def test_unidade_so_para_cliente_do_mesmo_revendedor(
        self, owner: asyncpg.Connection, world: World
    ) -> None:
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await owner.execute(
                "INSERT INTO platform_unit_map (reseller_id, tenant_id, credential_id, "
                "external_unit_id) VALUES ($1, $2, $3, 'unit-b1')",
                world.reseller_x,
                world.tenant_b1,
                world.credential_x,
            )

    async def test_unidade_nao_aponta_para_ativo_de_outro_tenant(
        self, owner: asyncpg.Connection, world: World
    ) -> None:
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await owner.execute(
                "INSERT INTO platform_unit_map (reseller_id, tenant_id, credential_id, "
                "external_unit_id, asset_id) VALUES ($1, $2, $3, 'unit-a2', $4)",
                world.reseller_x,
                world.tenant_a2,
                world.credential_x,
                world.asset[world.tenant_a1],
            )

    async def test_unidade_mapeada_uma_vez_por_credencial(
        self, owner: asyncpg.Connection, world: World
    ) -> None:
        with pytest.raises(asyncpg.UniqueViolationError):
            await owner.execute(
                "INSERT INTO platform_unit_map (reseller_id, tenant_id, credential_id, "
                "external_unit_id) VALUES ($1, $2, $3, 'unit-a1')",
                world.reseller_x,
                world.tenant_a2,
                world.credential_x,
            )


class TestAuditoria:
    @pytest.mark.parametrize(
        "sql", ["UPDATE audit_log SET action = 'apagado'", "DELETE FROM audit_log"]
    )
    async def test_audit_log_append_only(
        self, app: asyncpg.Connection, world: World, sql: str
    ) -> None:
        async with scoped(app, tenant=world.tenant_a1):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(sql)

    async def test_app_insere_auditoria_do_proprio_tenant(
        self, app: asyncpg.Connection, world: World
    ) -> None:
        async with scoped(app, tenant=world.tenant_a1):
            await app.execute(
                "INSERT INTO audit_log (reseller_id, tenant_id, action, entity) "
                "VALUES ($1, $2, 'teste', 'x')",
                world.reseller_x,
                world.tenant_a1,
            )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(
                    "INSERT INTO audit_log (reseller_id, tenant_id, action, entity) "
                    "VALUES ($1, $2, 'teste', 'x')",
                    world.reseller_y,
                    world.tenant_b1,
                )


class TestCatalogos:
    async def test_app_le_mas_nao_escreve_catalogos(
        self, app: asyncpg.Connection, world: World
    ) -> None:
        async with scoped(app, tenant=world.tenant_a1):
            assert await app.fetchval("SELECT count(*) FROM dtc_dictionary") > 0
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute(
                    "INSERT INTO dtc_dictionary (spn, fmi, description_pt, severity, "
                    "suggested_action) VALUES (1, 1, 'x', 'info', 'x')"
                )
        async with scoped(app, tenant=world.tenant_a1):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.execute("DELETE FROM param_mapping")

    async def test_seed_dtc_pequeno_e_marcado_para_revisao(self, owner: asyncpg.Connection) -> None:
        rows = await owner.fetch("SELECT review_status, severity::text FROM dtc_dictionary")
        assert 0 < len(rows) <= 10
        assert {r["review_status"] for r in rows} == {"a_revisar_por_especialista"}
