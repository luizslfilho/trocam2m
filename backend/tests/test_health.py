import httpx
import pytest


@pytest.mark.parametrize("path", ["/health", "/api/health"])
async def test_health_responde_ok(client: httpx.AsyncClient, path: str) -> None:
    resp = await client.get(path)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
