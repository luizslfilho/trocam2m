"""Checagens de prontidão: banco e Redis respondendo."""

import asyncio
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    detail: str


async def check_database(engine: AsyncEngine, timeout_s: float) -> CheckResult:
    try:
        async with asyncio.timeout(timeout_s):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception as exc:  # o motivo vai para o log, não para a resposta
        return CheckResult(ok=False, detail=type(exc).__name__)
    return CheckResult(ok=True, detail="ok")


async def check_redis(redis_url: str, timeout_s: float) -> CheckResult:
    client: Redis = Redis.from_url(
        redis_url, socket_connect_timeout=timeout_s, socket_timeout=timeout_s
    )
    try:
        async with asyncio.timeout(timeout_s):
            await client.ping()
    except Exception as exc:
        return CheckResult(ok=False, detail=type(exc).__name__)
    finally:
        await client.aclose()
    return CheckResult(ok=True, detail="ok")
