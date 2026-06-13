"""Integration tests for /api/v1/dashboard/summary (adapts to login state)."""

from httpx import AsyncClient

SUMMARY = "/api/v1/dashboard/summary"
REGISTER = "/api/v1/auth/register"

_REQUIRED_FIELDS = {
    "is_authenticated",
    "notes_count",
    "tasks_count",
    "rag_docs_count",
    "agents_count",
    "images_count",
    "tokens_this_month",
    "tokens_limit",
    "recent_activities",
}


class TestUnauthenticated:
    async def test_returns_200_with_demo_data(self, client: AsyncClient) -> None:
        resp = await client.get(SUMMARY)
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_authenticated"] is False
        # demo 数字非零, 让访客预览不空荡
        assert body["notes_count"] > 0
        assert body["images_count"] > 0
        assert body["tokens_this_month"] > 0

    async def test_demo_has_recent_activities(self, client: AsyncClient) -> None:
        resp = await client.get(SUMMARY)
        body = resp.json()
        assert len(body["recent_activities"]) >= 3
        first = body["recent_activities"][0]
        assert first.keys() >= {"kind", "title", "timestamp"}

    async def test_invalid_token_treated_as_anonymous(self, client: AsyncClient) -> None:
        # 用伪造 token 不应 401, 应 fallback 到匿名 (demo)
        resp = await client.get(SUMMARY, headers={"Authorization": "Bearer not.a.real.jwt"})
        assert resp.status_code == 200
        assert resp.json()["is_authenticated"] is False


class TestAuthenticated:
    async def test_returns_real_zero_counts(self, client: AsyncClient) -> None:
        reg = await client.post(
            REGISTER, json={"email": "dashboarder@example.com", "password": "supersecret"}
        )
        token = reg.json()["access_token"]

        resp = await client.get(SUMMARY, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_authenticated"] is True
        # Phase 3/4/7 还没做, 所有真实计数应该是 0
        assert body["notes_count"] == 0
        assert body["tasks_count"] == 0
        assert body["rag_docs_count"] == 0
        assert body["tokens_this_month"] == 0
        assert body["recent_activities"] == []


class TestSchema:
    async def test_response_has_all_required_fields(self, client: AsyncClient) -> None:
        resp = await client.get(SUMMARY)
        assert resp.json().keys() >= _REQUIRED_FIELDS
