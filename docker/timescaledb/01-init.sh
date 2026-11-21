#!/bin/bash
# Roda uma vez, na criação do volume. A role da aplicação NUNCA tem SUPERUSER nem BYPASSRLS
# (Seção 4). Tabelas, grants e RLS vêm das migrations (etapa 2).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_password="$APP_DB_PASSWORD" <<'SQL'
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE ROLE telemetria_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE
  PASSWORD :'app_password';
GRANT CONNECT ON DATABASE telemetria TO telemetria_app;
GRANT USAGE ON SCHEMA public TO telemetria_app;
SQL
