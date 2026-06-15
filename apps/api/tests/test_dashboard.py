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
    "today_words",
    "writing_streak",
    "recent_activities",
    "recent_tasks",
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


NOTES = "/api/v1/notes"
TASKS = "/api/v1/tasks"


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
        # 新用户没数据, 所有真实计数应该是 0
        assert body["notes_count"] == 0
        assert body["tasks_count"] == 0
        assert body["rag_docs_count"] == 0
        assert body["tokens_this_month"] == 0
        assert body["today_words"] == 0
        assert body["writing_streak"] == 0
        assert body["recent_activities"] == []
        assert body["recent_tasks"] == []

    async def test_notes_count_reflects_real_notes(self, client: AsyncClient) -> None:
        reg = await client.post(
            REGISTER, json={"email": "notes-count@example.com", "password": "supersecret"}
        )
        h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        for i in range(3):
            await client.post(NOTES, headers=h, json={"title": f"笔记 {i}", "content": "abc"})
        body = (await client.get(SUMMARY, headers=h)).json()
        assert body["notes_count"] == 3

    async def test_recent_activities_returns_recent_notes(
        self, client: AsyncClient
    ) -> None:
        reg = await client.post(
            REGISTER, json={"email": "recent@example.com", "password": "supersecret"}
        )
        h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        created = await client.post(NOTES, headers=h, json={"title": "唯一", "content": "x"})
        note_id = created.json()["id"]
        body = (await client.get(SUMMARY, headers=h)).json()
        assert len(body["recent_activities"]) == 1
        act = body["recent_activities"][0]
        assert act["kind"] == "note"
        assert act["title"] == "唯一"
        assert act["id"] == note_id

    async def test_today_words_sums_content_length(self, client: AsyncClient) -> None:
        reg = await client.post(
            REGISTER, json={"email": "wordcount@example.com", "password": "supersecret"}
        )
        h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        await client.post(NOTES, headers=h, json={"title": "A", "content": "hello"})  # 5
        await client.post(NOTES, headers=h, json={"title": "B", "content": "world!"})  # 6
        body = (await client.get(SUMMARY, headers=h)).json()
        assert body["today_words"] == 11

    async def test_writing_streak_today_is_one(self, client: AsyncClient) -> None:
        reg = await client.post(
            REGISTER, json={"email": "streak@example.com", "password": "supersecret"}
        )
        h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        await client.post(NOTES, headers=h, json={"title": "今天"})
        body = (await client.get(SUMMARY, headers=h)).json()
        assert body["writing_streak"] == 1

    async def test_tasks_count_only_undone(self, client: AsyncClient) -> None:
        reg = await client.post(
            REGISTER, json={"email": "dash-tasks@example.com", "password": "supersecret"}
        )
        h = {"Authorization": f"Bearer {reg.json()['access_token']}"}
        # 创建 3 个任务, 标 1 个 done
        for title in ["A", "B", "C"]:
            await client.post(TASKS, headers=h, json={"title": title})
        # mark C as done
        all_tasks = (await client.get(TASKS, headers=h)).json()
        c_task = next(t for t in all_tasks if t["title"] == "C")
        await client.patch(f"{TASKS}/{c_task['id']}", headers=h, json={"done": True})

        summary = (await client.get(SUMMARY, headers=h)).json()
        # tasks_count 只计未完成
        assert summary["tasks_count"] == 2
        # recent_tasks 只含未完成
        recent_titles = {t["title"] for t in summary["recent_tasks"]}
        assert recent_titles == {"A", "B"}

    async def test_recent_activities_isolated_per_user(
        self, client: AsyncClient
    ) -> None:
        a = await client.post(
            REGISTER, json={"email": "iso-a@example.com", "password": "supersecret"}
        )
        b = await client.post(
            REGISTER, json={"email": "iso-b@example.com", "password": "supersecret"}
        )
        ha = {"Authorization": f"Bearer {a.json()['access_token']}"}
        hb = {"Authorization": f"Bearer {b.json()['access_token']}"}
        await client.post(NOTES, headers=ha, json={"title": "alice"})
        body_b = (await client.get(SUMMARY, headers=hb)).json()
        # b 看不见 a 的笔记
        assert body_b["notes_count"] == 0
        assert body_b["recent_activities"] == []


class TestSchema:
    async def test_response_has_all_required_fields(self, client: AsyncClient) -> None:
        resp = await client.get(SUMMARY)
        assert resp.json().keys() >= _REQUIRED_FIELDS
