"""Telemetria: hypertable, compressão, aggregate horário e funções de leitura com contexto.

Exceção documentada (decisoes.md, 2026-11-22): o TimescaleDB não permite RLS em hypertable
com compressão nem com continuous aggregate. Por isso `telemetry_raw` e `telemetry_hourly`
ficam no schema `telemetry_internal`, SEM RLS e SEM nenhum GRANT para `telemetria_app`:
- a aplicação só lê pelas funções `app.telemetry_*`, que exigem contexto de tenant e
  levantam erro quando ele não está definido;
- o worker de ingestão (`telemetria_ingest`) só tem INSERT na hypertable;
- a FK (tenant_id, asset_id) → assets impede gravar ativo de um tenant com o tenant de outro.

Revision ID: 0004_telemetria
Revises: 0003_operacao
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

from app.db.ddl import APP_ROLE, INGEST_ROLE, execute_script

revision: str = "0004_telemetria"
down_revision: str | Sequence[str] | None = "0003_operacao"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = f"""
CREATE SCHEMA telemetry_internal;
REVOKE ALL ON SCHEMA telemetry_internal FROM PUBLIC;
GRANT USAGE ON SCHEMA telemetry_internal TO {INGEST_ROLE};

CREATE TABLE telemetry_internal.telemetry_raw (
    tenant_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    source data_source NOT NULL,
    ts_utc timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    lat double precision,
    lon double precision,
    speed_kmh real,
    heading_deg real,
    altitude_m real,
    satellites smallint,
    ignition boolean,
    rpm real,
    engine_load_pct real,
    torque_pct real,
    pto_active boolean,
    gear_neutral boolean,
    seatbelt_fastened boolean,
    fuel_level_pct real,
    fuel_level_l real,
    fuel_used_total_l double precision,
    odometer_km double precision,
    engine_hours double precision,
    battery_v real,
    ext_power_v real,
    rfid text,
    vin text,
    event_code text,
    dtc jsonb,
    extra jsonb,
    quality_flags text[] NOT NULL DEFAULT '{{}}',
    CONSTRAINT uq_telemetry_raw_key UNIQUE (tenant_id, asset_id, source, ts_utc),
    CONSTRAINT ck_telemetry_raw_flags CHECK (
        quality_flags <@ ARRAY['sentinel_removed', 'out_of_range', 'spike', 'gap_before']),
    CONSTRAINT fk_telemetry_raw_asset FOREIGN KEY (tenant_id, asset_id)
        REFERENCES public.assets (tenant_id, id) ON DELETE RESTRICT
);
SELECT create_hypertable(
    'telemetry_internal.telemetry_raw', by_range('ts_utc', INTERVAL '1 day'));
ALTER TABLE telemetry_internal.telemetry_raw SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, asset_id',
    timescaledb.compress_orderby = 'ts_utc DESC');
SELECT add_compression_policy('telemetry_internal.telemetry_raw', INTERVAL '7 days');
GRANT INSERT ON telemetry_internal.telemetry_raw TO {INGEST_ROLE};

-- Horário em UTC. O diário no fuso do tenant é montado a partir dele (app.telemetry_daily).
CREATE MATERIALIZED VIEW telemetry_internal.telemetry_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    tenant_id,
    asset_id,
    time_bucket(INTERVAL '1 hour', ts_utc) AS bucket,
    count(*) AS samples,
    min(ts_utc) AS first_ts,
    max(ts_utc) AS last_ts,
    min(odometer_km) AS odometer_min,
    max(odometer_km) AS odometer_max,
    min(engine_hours) AS engine_hours_min,
    max(engine_hours) AS engine_hours_max,
    min(fuel_used_total_l) AS fuel_used_min,
    max(fuel_used_total_l) AS fuel_used_max,
    max(speed_kmh) AS speed_max,
    sum(speed_kmh) AS speed_sum,
    count(speed_kmh) AS speed_count,
    count(*) FILTER (WHERE ignition) AS ignition_samples,
    count(*) FILTER (WHERE cardinality(quality_flags) > 0) AS flagged_samples
FROM telemetry_internal.telemetry_raw
GROUP BY tenant_id, asset_id, bucket
WITH NO DATA;

-- Refresh cobrindo 8 dias para trás: dado atrasado de até 7 dias reprocessa o agregado (1.6).
SELECT add_continuous_aggregate_policy('telemetry_internal.telemetry_hourly',
    start_offset => INTERVAL '8 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes');
"""

FUNCTIONS = f"""
CREATE FUNCTION app.telemetry_raw_range(
    p_asset_id uuid, p_from timestamptz, p_to timestamptz)
RETURNS SETOF telemetry_internal.telemetry_raw
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
DECLARE
    ids uuid[] := app.require_visible_tenant_ids();
BEGIN
    IF p_from IS NULL OR p_to IS NULL OR p_to <= p_from THEN
        RAISE EXCEPTION 'intervalo inválido' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    RETURN QUERY
        SELECT r.* FROM telemetry_internal.telemetry_raw r
        WHERE r.tenant_id = ANY (ids)
          AND r.asset_id = p_asset_id
          AND r.ts_utc >= p_from AND r.ts_utc < p_to
        ORDER BY r.ts_utc;
END
$$;

CREATE FUNCTION app.telemetry_hourly_range(
    p_from timestamptz, p_to timestamptz, p_asset_ids uuid[] DEFAULT NULL)
RETURNS SETOF telemetry_internal.telemetry_hourly
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
DECLARE
    ids uuid[] := app.require_visible_tenant_ids();
BEGIN
    IF p_from IS NULL OR p_to IS NULL OR p_to <= p_from THEN
        RAISE EXCEPTION 'intervalo inválido' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    RETURN QUERY
        SELECT h.* FROM telemetry_internal.telemetry_hourly h
        WHERE h.tenant_id = ANY (ids)
          AND (p_asset_ids IS NULL OR h.asset_id = ANY (p_asset_ids))
          AND h.bucket >= p_from AND h.bucket < p_to
        ORDER BY h.tenant_id, h.asset_id, h.bucket;
END
$$;

-- Diário no fuso de cada tenant, somando as horas UTC. Premissa: fuso de hora cheia
-- (todo o Brasil). Fuso com meia hora exige revisão (decisoes.md, 2026-11-22).
CREATE FUNCTION app.telemetry_daily(
    p_from date, p_to date, p_asset_ids uuid[] DEFAULT NULL)
RETURNS TABLE (
    tenant_id uuid,
    asset_id uuid,
    day date,
    samples bigint,
    first_ts timestamptz,
    last_ts timestamptz,
    odometer_min double precision,
    odometer_max double precision,
    engine_hours_min double precision,
    engine_hours_max double precision,
    fuel_used_min double precision,
    fuel_used_max double precision,
    speed_max real,
    speed_avg double precision,
    ignition_samples bigint,
    flagged_samples bigint)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
#variable_conflict use_column
DECLARE
    ids uuid[] := app.require_visible_tenant_ids();
BEGIN
    IF p_from IS NULL OR p_to IS NULL OR p_to < p_from THEN
        RAISE EXCEPTION 'intervalo inválido' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    RETURN QUERY
        SELECT h.tenant_id, h.asset_id,
               (h.bucket AT TIME ZONE t.timezone)::date AS day,
               sum(h.samples)::bigint, min(h.first_ts), max(h.last_ts),
               min(h.odometer_min), max(h.odometer_max),
               min(h.engine_hours_min), max(h.engine_hours_max),
               min(h.fuel_used_min), max(h.fuel_used_max),
               max(h.speed_max),
               sum(h.speed_sum) / nullif(sum(h.speed_count), 0),
               sum(h.ignition_samples)::bigint, sum(h.flagged_samples)::bigint
        FROM telemetry_internal.telemetry_hourly h
        JOIN public.tenants t ON t.id = h.tenant_id
        WHERE h.tenant_id = ANY (ids)
          AND (p_asset_ids IS NULL OR h.asset_id = ANY (p_asset_ids))
          -- pré-filtro largo em UTC; o filtro exato é pelo dia local abaixo
          AND h.bucket >= (p_from - 1)::timestamptz
          AND h.bucket < (p_to + 2)::timestamptz
          AND (h.bucket AT TIME ZONE t.timezone)::date BETWEEN p_from AND p_to
        GROUP BY h.tenant_id, h.asset_id, 3
        ORDER BY h.tenant_id, h.asset_id, 3;
END
$$;

GRANT EXECUTE ON FUNCTION app.telemetry_raw_range(uuid, timestamptz, timestamptz) TO {APP_ROLE};
GRANT EXECUTE ON FUNCTION app.telemetry_hourly_range(timestamptz, timestamptz, uuid[])
    TO {APP_ROLE};
GRANT EXECUTE ON FUNCTION app.telemetry_daily(date, date, uuid[]) TO {APP_ROLE};
"""


def upgrade() -> None:
    execute_script(SCHEMA)
    execute_script(FUNCTIONS)


def downgrade() -> None:
    op.execute("DROP FUNCTION app.telemetry_daily(date, date, uuid[])")
    op.execute("DROP FUNCTION app.telemetry_hourly_range(timestamptz, timestamptz, uuid[])")
    op.execute("DROP FUNCTION app.telemetry_raw_range(uuid, timestamptz, timestamptz)")
    op.execute("DROP MATERIALIZED VIEW telemetry_internal.telemetry_hourly")
    op.execute("DROP TABLE telemetry_internal.telemetry_raw")
    op.execute("DROP SCHEMA telemetry_internal CASCADE")
