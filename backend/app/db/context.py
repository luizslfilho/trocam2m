"""Contexto de tenant e revendedor por transação (Seção 4).

Os valores vêm SEMPRE do token do usuário (etapa 3), nunca do corpo da requisição.
`set_config(..., true)` equivale a `SET LOCAL`: vale só até o fim da transação atual,
então uma conexão devolvida ao pool nunca carrega o contexto de outro usuário.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

_SET = text(
    "SELECT set_config('app.tenant_id', :tenant, true), "
    "set_config('app.reseller_id', :reseller, true)"
)


class MissingTenantContextError(ValueError):
    """Nenhum tenant nem revendedor informado: não há escopo seguro para a transação."""


async def apply_tenant_context(
    conn: AsyncConnection | AsyncSession,
    *,
    tenant_id: UUID | None = None,
    reseller_id: UUID | None = None,
) -> None:
    if tenant_id is None and reseller_id is None:
        raise MissingTenantContextError("informe tenant_id e/ou reseller_id")
    await conn.execute(
        _SET,
        {
            "tenant": str(tenant_id) if tenant_id else "",
            "reseller": str(reseller_id) if reseller_id else "",
        },
    )


@asynccontextmanager
async def tenant_scope(
    session: AsyncSession,
    *,
    tenant_id: UUID | None = None,
    reseller_id: UUID | None = None,
) -> AsyncIterator[AsyncSession]:
    """Abre uma transação com o contexto aplicado; commit no fim, rollback em erro."""
    async with session.begin():
        await apply_tenant_context(session, tenant_id=tenant_id, reseller_id=reseller_id)
        yield session
