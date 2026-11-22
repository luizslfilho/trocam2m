"""Configuração da aplicação (Pydantic Settings). Valores vêm do ambiente ou de `.env`."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    service_name: str = "api"

    # Role da aplicação: sem SUPERUSER e sem BYPASSRLS (Seção 4).
    database_url: SecretStr
    # Role dona do schema, usada só pelo Alembic.
    migration_database_url: SecretStr | None = None
    # Role do worker de ingestão: só INSERT na telemetria.
    ingest_database_url: SecretStr | None = None
    redis_url: SecretStr

    ready_timeout_seconds: float = Field(default=2.0, gt=0)
    # Front e API ficam no mesmo host (proxy reverso); CORS só para origens explícitas.
    cors_allowed_origins: list[str] = Field(default_factory=list)

    heartbeat_file: str = "/tmp/heartbeat"  # noqa: S108 - arquivo local do container
    heartbeat_interval_seconds: float = Field(default=10.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
