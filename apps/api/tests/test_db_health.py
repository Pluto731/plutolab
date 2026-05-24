"""Integration test: GET /api/v1/db/health hits the real Docker postgres."""

import pytest
from httpx import ASGITransport, AsyncClient

from plutolab_api.main import app


@pytest.mark.asyncio
async def test_db_health_returns_200() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/db/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["dialect"] == "postgresql"
    assert "PostgreSQL" in data["server_version"]
