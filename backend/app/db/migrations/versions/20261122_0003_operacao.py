"""Operação: viagens, DTC, manutenção, combustível, configuração, pontuação, relatórios, auditoria.

Revision ID: 0003_operacao
Revises: 0002_cadastro
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

from app.db.ddl import APP_ROLE, execute_script, tenant_or_reseller_rls, tenant_rls

revision: str = "0003_operacao"
down_revision: str | Sequence[str] | None = "0002_cadastro"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPES = """
CREATE TYPE maintenance_kind AS ENUM ('preventive', 'corrective');
-- suggested (vinda de DTC crítico) só conta como parada depois que o gestor confirma (1.5).
CREATE TYPE maintenance_status AS ENUM ('suggested', 'open', 'closed', 'dismissed');
CREATE TYPE fuel_tx_source AS ENUM ('card', 'erp', 'manual');
CREATE TYPE config_scope AS ENUM ('tenant', 'group', 'model', 'asset');
CREATE TYPE occurrence_status AS ENUM (
    'valid', 'contested', 'accepted_contest', 'rejected_contest', 'void_quality');
CREATE TYPE contest_decision AS ENUM ('accepted', 'rejected');
CREATE TYPE report_frequency AS ENUM ('daily', 'weekly', 'monthly');
CREATE TYPE report_format AS ENUM ('pdf', 'xlsx');
"""

TABLES = """
CREATE TABLE trips (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    asset_id uuid NOT NULL,
    driver_id uuid,
    started_at timestamptz NOT NULL,
    ended_at timestamptz NOT NULL,
    distance_km double precision,
    duration_s integer,
    stopped_s integer,
    max_speed_kmh real,
    liters double precision,
    liters_estimated boolean NOT NULL DEFAULT false,
    origin jsonb,
    destination jsonb,
    quality data_quality NOT NULL,
    quality_reason text,
    computed_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ended_at >= started_at),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id),
    FOREIGN KEY (tenant_id, driver_id) REFERENCES drivers (tenant_id, id)
);
CREATE INDEX ix_trips_asset ON trips (tenant_id, asset_id, started_at);
CREATE INDEX ix_trips_driver ON trips (tenant_id, driver_id, started_at);

-- Sem FK para dtc_dictionary: código desconhecido também abre alerta.
CREATE TABLE dtc_alerts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    asset_id uuid NOT NULL,
    spn integer NOT NULL,
    fmi smallint NOT NULL,
    severity dtc_severity,
    opened_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    closed_at timestamptz,
    UNIQUE (tenant_id, id),
    CHECK (closed_at IS NULL OR closed_at >= opened_at),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id)
);
CREATE INDEX ix_dtc_alerts_open ON dtc_alerts (tenant_id, asset_id) WHERE closed_at IS NULL;
CREATE UNIQUE INDEX uq_dtc_alerts_one_open
    ON dtc_alerts (tenant_id, asset_id, spn, fmi) WHERE closed_at IS NULL;

CREATE TABLE maintenance_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    asset_id uuid NOT NULL,
    kind maintenance_kind NOT NULL,
    status maintenance_status NOT NULL,
    reason text NOT NULL,
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    dtc_alert_id uuid,
    created_by uuid REFERENCES users (id),
    confirmed_by uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ended_at IS NULL OR ended_at >= started_at),
    CHECK (status <> 'closed' OR ended_at IS NOT NULL),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id),
    FOREIGN KEY (tenant_id, dtc_alert_id) REFERENCES dtc_alerts (tenant_id, id)
);
CREATE INDEX ix_maintenance_events_asset ON maintenance_events (tenant_id, asset_id, started_at);
CREATE INDEX ix_maintenance_events_status ON maintenance_events (tenant_id, status)
    WHERE status IN ('suggested', 'open');

CREATE TABLE maintenance_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    model_id uuid,
    asset_id uuid,
    item text NOT NULL,
    interval_engine_hours double precision CHECK (interval_engine_hours > 0),
    interval_km double precision CHECK (interval_km > 0),
    interval_days integer CHECK (interval_days > 0),
    warn_before_engine_hours double precision CHECK (warn_before_engine_hours >= 0),
    warn_before_km double precision CHECK (warn_before_km >= 0),
    warn_before_days integer CHECK (warn_before_days >= 0),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    CHECK (num_nonnulls(model_id, asset_id) = 1),
    CHECK (num_nonnulls(interval_engine_hours, interval_km, interval_days) >= 1),
    FOREIGN KEY (tenant_id, model_id) REFERENCES asset_models (tenant_id, id),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id)
);

CREATE TABLE maintenance_executions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    plan_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    executed_at timestamptz NOT NULL,
    engine_hours_reading double precision,
    odometer_km_reading double precision,
    notes text,
    created_by uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, plan_id) REFERENCES maintenance_plans (tenant_id, id),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id)
);
CREATE INDEX ix_maintenance_executions_plan
    ON maintenance_executions (tenant_id, plan_id, asset_id, executed_at);

-- Preço com data de vigência: o passado não muda quando o preço muda.
CREATE TABLE fuel_prices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    fuel_type text NOT NULL DEFAULT 'diesel',
    price_per_l numeric(10, 4) NOT NULL CHECK (price_per_l > 0),
    valid_from date NOT NULL,
    created_by uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, fuel_type, valid_from)
);

CREATE TABLE fuel_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    asset_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL,
    liters double precision NOT NULL CHECK (liters > 0),
    total_price numeric(12, 2),
    source fuel_tx_source NOT NULL,
    external_ref text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source, external_ref),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id)
);
CREATE INDEX ix_fuel_transactions_asset ON fuel_transactions (tenant_id, asset_id, occurred_at);

-- Herança: padrão do sistema → tenant → grupo → modelo → ativo (etapa 6).
CREATE TABLE config_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    scope config_scope NOT NULL,
    scope_id uuid,
    key text NOT NULL,
    value jsonb NOT NULL,
    valid_from timestamptz NOT NULL DEFAULT now(),
    updated_by uuid REFERENCES users (id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((scope = 'tenant') = (scope_id IS NULL))
);
CREATE UNIQUE INDEX uq_config_settings_key
    ON config_settings (tenant_id, scope, scope_id, key, valid_from) NULLS NOT DISTINCT;

CREATE TABLE config_versions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    scope config_scope NOT NULL,
    scope_id uuid,
    key text NOT NULL,
    old_value jsonb,
    new_value jsonb,
    valid_from timestamptz NOT NULL,
    changed_by uuid REFERENCES users (id),
    changed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_config_versions_key ON config_versions (tenant_id, key, changed_at);

-- Pesos versionados: sem sobreposição de vigência por tipo de ocorrência (5.1).
CREATE TABLE scoring_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    occurrence_type text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    weight numeric(6, 2) NOT NULL CHECK (weight >= 0),
    params jsonb NOT NULL DEFAULT '{}',
    version integer NOT NULL,
    valid_from timestamptz NOT NULL,
    valid_to timestamptz,
    created_by uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, occurrence_type, version),
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    EXCLUDE USING gist (
        tenant_id WITH =, occurrence_type WITH =, tstzrange(valid_from, valid_to) WITH &&)
);

CREATE TABLE scoring_cycles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    starts_on date NOT NULL,
    ends_on date NOT NULL,
    closed_at timestamptz,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, starts_on),
    CHECK (ends_on > starts_on)
);

CREATE TABLE driver_occurrences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    driver_id uuid,
    asset_id uuid NOT NULL,
    cycle_id uuid,
    adjusts_cycle_id uuid,
    occurrence_type text NOT NULL,
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    location jsonb,
    measured_value double precision,
    limit_value double precision,
    description text NOT NULL,
    weight_applied numeric(6, 2) NOT NULL DEFAULT 0,
    rule_id uuid,
    quality data_quality NOT NULL,
    status occurrence_status NOT NULL DEFAULT 'valid',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    CHECK (status <> 'void_quality' OR weight_applied = 0),
    FOREIGN KEY (tenant_id, driver_id) REFERENCES drivers (tenant_id, id),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id),
    FOREIGN KEY (tenant_id, cycle_id) REFERENCES scoring_cycles (tenant_id, id),
    FOREIGN KEY (tenant_id, adjusts_cycle_id) REFERENCES scoring_cycles (tenant_id, id),
    FOREIGN KEY (tenant_id, rule_id) REFERENCES scoring_rules (tenant_id, id)
);
CREATE INDEX ix_driver_occurrences_driver ON driver_occurrences (tenant_id, driver_id, started_at);
CREATE INDEX ix_driver_occurrences_cycle ON driver_occurrences (tenant_id, cycle_id);

CREATE TABLE occurrence_contests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    occurrence_id uuid NOT NULL,
    opened_by uuid NOT NULL REFERENCES users (id),
    opened_at timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL,
    decision contest_decision,
    decided_by uuid REFERENCES users (id),
    decided_at timestamptz,
    justification text,
    CHECK ((decision IS NULL) = (decided_at IS NULL)),
    CHECK (decision IS NULL OR justification IS NOT NULL),
    FOREIGN KEY (tenant_id, occurrence_id) REFERENCES driver_occurrences (tenant_id, id)
);
CREATE INDEX ix_occurrence_contests_pending ON occurrence_contests (tenant_id)
    WHERE decision IS NULL;

CREATE TABLE report_schedules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    report_type text NOT NULL,
    filters jsonb NOT NULL DEFAULT '{}',
    frequency report_frequency NOT NULL,
    format report_format NOT NULL,
    recipients text[] NOT NULL CHECK (cardinality(recipients) > 0),
    next_run_at timestamptz NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_by uuid REFERENCES users (id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_report_schedules_due ON report_schedules (next_run_at) WHERE active;

-- Auditoria append-only: a aplicação só insere e lê.
CREATE TABLE audit_log (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reseller_id uuid NOT NULL REFERENCES resellers (id),
    tenant_id uuid,
    actor_user_id uuid REFERENCES users (id),
    action text NOT NULL,
    entity text NOT NULL,
    entity_id text,
    before jsonb,
    after jsonb,
    at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (reseller_id, tenant_id) REFERENCES tenants (reseller_id, id)
);
CREATE INDEX ix_audit_log_tenant_at ON audit_log (tenant_id, at);
CREATE INDEX ix_audit_log_reseller_at ON audit_log (reseller_id, at);
"""

TENANT_TABLES = (
    "trips",
    "dtc_alerts",
    "maintenance_events",
    "maintenance_plans",
    "maintenance_executions",
    "fuel_prices",
    "fuel_transactions",
    "config_settings",
    "config_versions",
    "scoring_rules",
    "scoring_cycles",
    "driver_occurrences",
    "occurrence_contests",
    "report_schedules",
)

DROP_ORDER = (
    "audit_log",
    "report_schedules",
    "occurrence_contests",
    "driver_occurrences",
    "scoring_cycles",
    "scoring_rules",
    "config_versions",
    "config_settings",
    "fuel_transactions",
    "fuel_prices",
    "maintenance_executions",
    "maintenance_plans",
    "maintenance_events",
    "dtc_alerts",
    "trips",
)


def upgrade() -> None:
    execute_script(TYPES)
    execute_script(TABLES)
    for table in TENANT_TABLES:
        for stmt in tenant_rls(table):
            op.execute(stmt)
    for stmt in tenant_or_reseller_rls("audit_log", grants="SELECT, INSERT"):
        if not stmt.startswith("CREATE INDEX"):  # índices próprios acima
            op.execute(stmt)
    op.execute(f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")


def downgrade() -> None:
    op.execute("DROP TABLE " + ", ".join(DROP_ORDER))
    op.execute(
        "DROP TYPE report_format, report_frequency, contest_decision, occurrence_status, "
        "config_scope, fuel_tx_source, maintenance_status, maintenance_kind"
    )
