"""Extensões, schema `app` e funções de contexto de tenant/revendedor.

Revision ID: 0001_contexto
Revises:
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

from app.db.ddl import APP_ROLE, INGEST_ROLE

revision: str = "0001_contexto"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("CREATE SCHEMA app")
    op.execute("REVOKE ALL ON SCHEMA app FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA app TO {APP_ROLE}, {INGEST_ROLE}")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA app REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC")
    # Contexto vem SEMPRE do token, aplicado por SET LOCAL (set_config(..., true)).
    for name in ("tenant", "reseller"):
        op.execute(f"""
            CREATE FUNCTION app.current_{name}_id() RETURNS uuid
            LANGUAGE sql STABLE PARALLEL SAFE
            AS $$ SELECT nullif(current_setting('app.{name}_id', true), '')::uuid $$
        """)
        op.execute(
            f"GRANT EXECUTE ON FUNCTION app.current_{name}_id() TO {APP_ROLE}, {INGEST_ROLE}"
        )


def downgrade() -> None:
    op.execute("DROP SCHEMA app CASCADE")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
    op.execute("DROP EXTENSION IF EXISTS citext")
