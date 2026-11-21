"""Aplicação FastAPI.

Atrás do proxy reverso a API fica em `/api` (mesmo host do front, por revendedor). As rotas
de infraestrutura respondem tanto na raiz (healthcheck do container) quanto em `/api`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.db.session import get_engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.service_name)
    app = FastAPI(
        title="Plataforma de telemetria",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.app_env == "prod" else "/api/docs",
        openapi_url=None if settings.app_env == "prod" else "/api/openapi.json",
        redoc_url=None,
    )
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "X-Ingest-Token"],
        )
    app.include_router(health_router)
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
