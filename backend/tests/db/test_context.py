"""Helper `tenant_scope` (SQLAlchemy): aplica o contexto só dentro da transação."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.db.context import MissingTenantContextError, apply_tenant_context, tenant_scope
from tests.db.conftest import World, sqlalchemy_url

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(sqlalchemy_url("DATABASE_URL", migrated_db), pool_size=1)
    yield eng
    await eng.dispose()


async def test_contexto_vale_so_na_transacao(engine: AsyncEngine, world: World) -> None:
    async with AsyncSession(engine) as session:
        async with tenant_scope(session, tenant_id=world.tenant_a1):
            ids = (await session.execute(text("SELECT id FROM tenants"))).scalars().all()
            assert ids == [world.tenant_a1]
        # mesma conexão do pool, transação nova: contexto já não existe
        async with session.begin():
            n = (await session.execute(text("SELECT count(*) FROM tenants"))).scalar_one()
            assert n == 0


async def test_revendedor(engine: AsyncEngine, world: World) -> None:
    async with AsyncSession(engine) as session, tenant_scope(session, reseller_id=world.reseller_x):
        ids = set((await session.execute(text("SELECT id FROM tenants"))).scalars())
        assert ids == {world.tenant_a1, world.tenant_a2}


async def test_sem_tenant_nem_revendedor_e_erro(engine: AsyncEngine) -> None:
    async with AsyncSession(engine) as session, session.begin():
        with pytest.raises(MissingTenantContextError):
            await apply_tenant_context(session)
