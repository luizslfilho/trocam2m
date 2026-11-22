"""Trechos de DDL reutilizados pelas migrations (RLS, grants e índices padrão).

Toda tabela de negócio com `tenant_id` recebe a mesma política: só enxerga e só escreve
linhas dos tenants visíveis no contexto da transação (`app.visible_tenant_ids()`).
"""

APP_ROLE = "telemetria_app"
INGEST_ROLE = "telemetria_ingest"

VISIBLE_TENANTS = "(SELECT app.visible_tenant_ids())::uuid[]"


def split_sql(script: str) -> list[str]:
    """Divide um script em comandos por `;`, respeitando corpos `$$ ... $$` e comentários `--`.

    O asyncpg usa prepared statements e não aceita vários comandos numa chamada só.
    """
    statements: list[str] = []
    current: list[str] = []
    in_dollar = False
    for line in script.splitlines():
        stripped = line.strip()
        if not in_dollar and (not stripped or stripped.startswith("--")):
            continue
        current.append(line)
        if line.count("$$") % 2 == 1:
            in_dollar = not in_dollar
        if not in_dollar and stripped.endswith(";"):
            statements.append("\n".join(current).rstrip().rstrip(";"))
            current = []
    if current and "\n".join(current).strip():
        statements.append("\n".join(current).strip().rstrip(";"))
    return statements


def execute_script(script: str) -> None:
    from alembic import op

    for stmt in split_sql(script):
        op.execute(stmt)


def tenant_rls(table: str, *, grants: str = "SELECT, INSERT, UPDATE, DELETE") -> list[str]:
    """RLS por tenant, índice em `tenant_id` e grants para a role da aplicação."""
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING (tenant_id = ANY ({VISIBLE_TENANTS})) "
        f"WITH CHECK (tenant_id = ANY ({VISIBLE_TENANTS}))",
        f"CREATE INDEX ix_{table}_tenant_id ON {table} (tenant_id)",
        f"GRANT {grants} ON {table} TO {APP_ROLE}",
    ]


def tenant_or_reseller_rls(
    table: str, *, grants: str = "SELECT, INSERT, UPDATE, DELETE"
) -> list[str]:
    """RLS para tabelas cujas linhas podem ser do revendedor (`tenant_id` nulo)."""
    rule = (
        f"(tenant_id = ANY ({VISIBLE_TENANTS})) "
        "OR (tenant_id IS NULL AND reseller_id = app.current_reseller_id())"
    )
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"CREATE POLICY tenant_or_reseller_isolation ON {table} USING ({rule}) WITH CHECK ({rule})",
        f"CREATE INDEX ix_{table}_tenant_id ON {table} (tenant_id)",
        f"CREATE INDEX ix_{table}_reseller_id ON {table} (reseller_id)",
        f"GRANT {grants} ON {table} TO {APP_ROLE}",
    ]
