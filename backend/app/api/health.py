"""`/health` (processo vivo) e `/ready` (banco e Redis respondendo)."""

import asyncio

from fastapi import APIRouter, Response, status

from app.core.logging import get_logger
from app.core.readiness import check_database, check_redis
from app.core.settings import get_settings
from app.db.session import get_engine

router = APIRouter(tags=["infra"])
log = get_logger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    settings = get_settings()
    timeout = settings.ready_timeout_seconds
    db, cache = await asyncio.gather(
        check_database(get_engine(), timeout),
        check_redis(settings.redis_url.get_secret_value(), timeout),
    )
    checks = {"database": db.detail, "redis": cache.detail}
    if db.ok and cache.ok:
        return {"status": "ready", "checks": checks}
    log.warning("ready_failed", **checks)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not_ready", "checks": checks}
