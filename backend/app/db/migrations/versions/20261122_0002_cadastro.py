"""Hierarquia de revenda, cadastro, credenciais de plataforma, ingestão e catálogos.

Revision ID: 0002_cadastro
Revises: 0001_contexto
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

from app.db.ddl import (
    APP_ROLE,
    INGEST_ROLE,
    execute_script,
    tenant_or_reseller_rls,
    tenant_rls,
)

revision: str = "0002_cadastro"
down_revision: str | Sequence[str] | None = "0001_contexto"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPES = """
CREATE TYPE asset_category AS ENUM ('truck', 'yellow_line');
CREATE TYPE data_source AS ENUM ('wialon', 'redgps');
CREATE TYPE user_role AS ENUM ('reseller_admin', 'admin', 'fleet_manager', 'viewer', 'driver');
CREATE TYPE assignment_source AS ENUM ('rfid', 'platform_assignment', 'fixed');
CREATE TYPE geofence_shape AS ENUM ('polygon', 'circle', 'line');
CREATE TYPE geofence_purpose AS ENUM ('yard', 'workshop', 'mine', 'urban', 'work_front', 'other');
CREATE TYPE dtc_severity AS ENUM ('critical', 'warning', 'info');
CREATE TYPE data_quality AS ENUM ('reliable', 'partial', 'unreliable');
"""

TABLES = """
CREATE TABLE resellers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    hosts text[] NOT NULL DEFAULT '{}',
    branding jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_resellers_hosts ON resellers USING gin (hosts);

CREATE TABLE tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reseller_id uuid NOT NULL REFERENCES resellers (id),
    name text NOT NULL,
    timezone text NOT NULL DEFAULT 'America/Sao_Paulo',
    currency char(3) NOT NULL DEFAULT 'BRL',
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (reseller_id, id)
);
CREATE INDEX ix_tenants_reseller_id ON tenants (reseller_id);

CREATE TABLE asset_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    parent_id uuid,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, parent_id) REFERENCES asset_groups (tenant_id, id)
);

CREATE TABLE asset_models (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    name text NOT NULL,
    manufacturer text,
    category asset_category NOT NULL,
    idle_max_rpm real,
    extra_eco_max_rpm real,
    eco_max_rpm real,
    rpm_abs_max real,
    work_load_threshold_pct real NOT NULL DEFAULT 20 CHECK (work_load_threshold_pct BETWEEN 0 AND 100),
    idle_lph real CHECK (idle_lph >= 0),
    std_kmpl real CHECK (std_kmpl > 0),
    std_lph real CHECK (std_lph > 0),
    tank_capacity_l real CHECK (tank_capacity_l > 0),
    electrical_system_v smallint CHECK (electrical_system_v IN (12, 24)),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, name),
    CHECK (idle_max_rpm < extra_eco_max_rpm AND extra_eco_max_rpm < eco_max_rpm
           AND eco_max_rpm <= rpm_abs_max)
);

CREATE TABLE assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    group_id uuid,
    model_id uuid,
    category asset_category NOT NULL,
    label text NOT NULL,
    plate text,
    vin text,
    hardware_model text,
    source data_source NOT NULL,
    external_id text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, source, external_id),
    FOREIGN KEY (tenant_id, group_id) REFERENCES asset_groups (tenant_id, id),
    FOREIGN KEY (tenant_id, model_id) REFERENCES asset_models (tenant_id, id)
);
CREATE INDEX ix_assets_group ON assets (tenant_id, group_id);

CREATE TABLE drivers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    name text NOT NULL,
    document text,
    rfid_code text,
    external_id text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, rfid_code)
);

CREATE TABLE driver_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    asset_id uuid NOT NULL,
    driver_id uuid NOT NULL,
    source assignment_source NOT NULL,
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ended_at IS NULL OR ended_at > started_at),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id),
    FOREIGN KEY (tenant_id, driver_id) REFERENCES drivers (tenant_id, id)
);
CREATE INDEX ix_driver_assignments_asset ON driver_assignments (tenant_id, asset_id, started_at);
CREATE INDEX ix_driver_assignments_driver ON driver_assignments (tenant_id, driver_id, started_at);

-- reseller_admin: tenant_id nulo; todos os outros papéis (inclusive driver): tenant_id preenchido.
CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reseller_id uuid NOT NULL REFERENCES resellers (id),
    tenant_id uuid,
    email citext NOT NULL UNIQUE,
    password_hash text,
    role user_role NOT NULL,
    driver_id uuid,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_users_role_scope CHECK ((role = 'reseller_admin') = (tenant_id IS NULL)),
    CONSTRAINT ck_users_driver_link CHECK (driver_id IS NULL OR role = 'driver'),
    FOREIGN KEY (reseller_id, tenant_id) REFERENCES tenants (reseller_id, id),
    FOREIGN KEY (tenant_id, driver_id) REFERENCES drivers (tenant_id, id)
);

-- Credencial pode ser do revendedor (tenant_id nulo) e compartilhada entre os clientes dele.
CREATE TABLE platform_credentials (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reseller_id uuid NOT NULL REFERENCES resellers (id),
    tenant_id uuid,
    platform data_source NOT NULL,
    label text NOT NULL,
    encrypted_secret bytea NOT NULL,
    key_id text NOT NULL,
    api_base_url text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (reseller_id, id),
    FOREIGN KEY (reseller_id, tenant_id) REFERENCES tenants (reseller_id, id)
);

-- Cada unidade da plataforma pertence a exatamente um cliente. Sem mapeamento, nada entra.
CREATE TABLE platform_unit_map (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reseller_id uuid NOT NULL,
    tenant_id uuid NOT NULL,
    credential_id uuid NOT NULL,
    external_unit_id text NOT NULL,
    asset_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (credential_id, external_unit_id),
    FOREIGN KEY (reseller_id, credential_id) REFERENCES platform_credentials (reseller_id, id),
    FOREIGN KEY (reseller_id, tenant_id) REFERENCES tenants (reseller_id, id),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id)
);

CREATE TABLE ingest_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    source data_source NOT NULL,
    token_hash bytea NOT NULL UNIQUE,
    label text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz
);

CREATE TABLE rejected_packets (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    source data_source NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL,
    payload jsonb NOT NULL
);
CREATE INDEX ix_rejected_packets_received ON rejected_packets (tenant_id, received_at);

-- Geometria em GeoJSON (sem PostGIS na imagem); ponto-em-polígono em Python (GeofenceMatcher).
CREATE TABLE geofences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants (id),
    name text NOT NULL,
    shape geofence_shape NOT NULL,
    purpose geofence_purpose NOT NULL DEFAULT 'other',
    geometry jsonb NOT NULL,
    radius_m double precision CHECK (radius_m > 0),
    width_m double precision CHECK (width_m > 0),
    bbox_min_lat double precision NOT NULL,
    bbox_min_lon double precision NOT NULL,
    bbox_max_lat double precision NOT NULL,
    bbox_max_lon double precision NOT NULL,
    allowed_idle boolean NOT NULL DEFAULT false,
    speed_limit_kmh real CHECK (speed_limit_kmh > 0),
    source data_source,
    external_id text,
    active boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((shape = 'circle') = (radius_m IS NOT NULL)),
    CHECK ((shape = 'line') = (width_m IS NOT NULL)),
    CHECK (bbox_min_lat <= bbox_max_lat AND bbox_min_lon <= bbox_max_lon)
);

-- Cópia persistente do último estado (o estado vivo fica no Redis Hash).
CREATE TABLE asset_live_state (
    tenant_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    last_ts_utc timestamptz NOT NULL,
    received_at timestamptz NOT NULL,
    state jsonb NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, asset_id),
    FOREIGN KEY (tenant_id, asset_id) REFERENCES assets (tenant_id, id)
);

-- Catálogos globais (sem tenant): leitura para a aplicação, escrita só por migration.
CREATE TABLE param_mapping (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source data_source NOT NULL,
    hardware_model text NOT NULL,
    canonical_field text NOT NULL,
    source_param text NOT NULL,
    scale double precision NOT NULL DEFAULT 1,
    "offset" double precision NOT NULL DEFAULT 0,
    needs_doc boolean NOT NULL DEFAULT true,
    notes text,
    UNIQUE (source, hardware_model, canonical_field)
);

CREATE TABLE dtc_dictionary (
    spn integer NOT NULL,
    fmi smallint NOT NULL CHECK (fmi BETWEEN 0 AND 31),
    description_pt text NOT NULL,
    severity dtc_severity NOT NULL,
    suggested_action text NOT NULL,
    review_status text NOT NULL DEFAULT 'a_revisar_por_especialista',
    PRIMARY KEY (spn, fmi)
);
"""

FUNCTIONS = f"""
-- Tenants visíveis no contexto. SECURITY DEFINER: lê tenants como dona do schema.
--   só tenant_id                → aquele tenant
--   reseller_id + tenant_id     → o tenant, só se for desse revendedor
--   só reseller_id              → todos os tenants do revendedor
--   nada                        → nenhum
CREATE FUNCTION app.visible_tenant_ids() RETURNS uuid[]
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
    SELECT CASE
        WHEN app.current_tenant_id() IS NOT NULL THEN ARRAY(
            SELECT t.id FROM public.tenants t
            WHERE t.id = app.current_tenant_id()
              AND (app.current_reseller_id() IS NULL OR t.reseller_id = app.current_reseller_id()))
        WHEN app.current_reseller_id() IS NOT NULL THEN ARRAY(
            SELECT t.id FROM public.tenants t WHERE t.reseller_id = app.current_reseller_id())
        ELSE '{{}}'::uuid[]
    END
$$;

CREATE FUNCTION app.visible_reseller_id() RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
    SELECT coalesce(
        app.current_reseller_id(),
        (SELECT t.reseller_id FROM public.tenants t WHERE t.id = app.current_tenant_id()))
$$;

-- Igual a visible_tenant_ids(), mas falha alto: sem contexto, ou com tenant fora do
-- revendedor, levanta erro em vez de devolver vazio. Usada nas funções de telemetria.
CREATE FUNCTION app.require_visible_tenant_ids() RETURNS uuid[]
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
DECLARE
    ids uuid[];
BEGIN
    IF app.current_tenant_id() IS NULL AND app.current_reseller_id() IS NULL THEN
        RAISE EXCEPTION 'contexto de tenant ausente: app.tenant_id/app.reseller_id não definidos'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    ids := app.visible_tenant_ids();
    IF app.current_tenant_id() IS NOT NULL AND cardinality(ids) = 0 THEN
        RAISE EXCEPTION 'tenant fora do escopo do contexto'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN ids;
END
$$;

GRANT EXECUTE ON FUNCTION app.visible_tenant_ids() TO {APP_ROLE}, {INGEST_ROLE};
GRANT EXECUTE ON FUNCTION app.visible_reseller_id() TO {APP_ROLE}, {INGEST_ROLE};
GRANT EXECUTE ON FUNCTION app.require_visible_tenant_ids() TO {APP_ROLE};
"""

TENANT_TABLES = (
    "asset_groups",
    "asset_models",
    "assets",
    "drivers",
    "driver_assignments",
    "platform_unit_map",
    "ingest_tokens",
    "rejected_packets",
    "geofences",
    "asset_live_state",
)

POLICIES = [
    # resellers: o próprio revendedor, ou o revendedor do tenant atual. Criação só pelo sistema.
    "ALTER TABLE resellers ENABLE ROW LEVEL SECURITY",
    "CREATE POLICY reseller_isolation ON resellers "
    "USING (id = app.visible_reseller_id()) WITH CHECK (id = app.visible_reseller_id())",
    f"GRANT SELECT, UPDATE ON resellers TO {APP_ROLE}",
    # tenants: enxerga os visíveis; reseller_admin cria clientes só no próprio revendedor.
    "ALTER TABLE tenants ENABLE ROW LEVEL SECURITY",
    "CREATE POLICY tenants_select ON tenants FOR SELECT "
    "USING (id = ANY ((SELECT app.visible_tenant_ids())::uuid[]))",
    "CREATE POLICY tenants_insert ON tenants FOR INSERT "
    "WITH CHECK (reseller_id = app.current_reseller_id())",
    "CREATE POLICY tenants_update ON tenants FOR UPDATE "
    "USING (id = ANY ((SELECT app.visible_tenant_ids())::uuid[])) "
    "WITH CHECK (reseller_id = app.visible_reseller_id())",
    f"GRANT SELECT, INSERT, UPDATE ON tenants TO {APP_ROLE}",
    *tenant_or_reseller_rls("users"),
    *tenant_or_reseller_rls("platform_credentials"),
    *[stmt for t in TENANT_TABLES for stmt in tenant_rls(t)],
    f"GRANT SELECT ON param_mapping, dtc_dictionary TO {APP_ROLE}",
]


def upgrade() -> None:
    execute_script(TYPES)
    execute_script(TABLES)
    execute_script(FUNCTIONS)
    for stmt in POLICIES:
        op.execute(stmt)


def downgrade() -> None:
    op.execute(
        "DROP TABLE dtc_dictionary, param_mapping, asset_live_state, geofences, rejected_packets, "
        "ingest_tokens, platform_unit_map, platform_credentials, users, driver_assignments, "
        "drivers, assets, asset_models, asset_groups, tenants, resellers"
    )
    op.execute("DROP FUNCTION app.require_visible_tenant_ids()")
    op.execute("DROP FUNCTION app.visible_reseller_id()")
    op.execute("DROP FUNCTION app.visible_tenant_ids()")
    op.execute(
        "DROP TYPE data_quality, dtc_severity, geofence_purpose, geofence_shape, "
        "assignment_source, user_role, data_source, asset_category"
    )
