"""Fixtures comuns. Integração usa TimescaleDB e Redis reais (DATABASE_URL, REDIS_URL)."""

from collections.abc import AsyncIterator

import httpx
import pytest

from app.core.settings import get_settings
from app.db.session import get_engine
from app.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    get_settings.cache_clear()
    get_engine.cache_clear()
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await get_engine().dispose()
    get_engine.cache_clear()
    get_settings.cache_clear()
