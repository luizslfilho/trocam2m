import httpx
import pytest

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("path", ["/ready", "/api/ready"])
async def test_ready_com_banco_e_redis_no_ar(client: httpx.AsyncClient, path: str) -> None:
    resp = await client.get(path)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


async def test_ready_503_quando_redis_fora(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.settings import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    monkeypatch.setenv("READY_TIMEOUT_SECONDS", "0.5")
    resp = await client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] != "ok"


async def test_ready_503_quando_banco_fora(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.settings import get_settings
    from app.db.session import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://ninguem:x@127.0.0.1:1/nada")
    monkeypatch.setenv("READY_TIMEOUT_SECONDS", "0.5")
    resp = await client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["checks"]["database"] != "ok"
    await get_engine().dispose()
    get_engine.cache_clear()
