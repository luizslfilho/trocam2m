#!/bin/bash
# Roda uma vez, na criação do volume. Roles da aplicação NUNCA têm SUPERUSER nem BYPASSRLS
# (Seção 4). Tabelas, grants e RLS vêm das migrations (Alembic).
#
#   telemetria_owner   dona do schema; só migrations (POSTGRES_USER da imagem)
#   telemetria_app     API e serviços; sujeita a RLS; telemetria só por funções
#   telemetria_ingest  worker de ingestão; só INSERT na telemetria
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_password="$APP_DB_PASSWORD" -v ingest_password="$INGEST_DB_PASSWORD" <<'SQL'
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE ROLE telemetria_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
  PASSWORD :'app_password';
CREATE ROLE telemetria_ingest LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
  PASSWORD :'ingest_password';
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO telemetria_app, telemetria_ingest;
SELECT format('GRANT CONNECT ON DATABASE %I TO telemetria_app, telemetria_ingest',
              current_database()) \gexec
SQL
