"""The new tool schema and bounded result flow through the real node executor."""

import json
from dataclasses import replace

import httpx

from plutolab_api.core.crypto import decrypt
from plutolab_api.services import agent_tools
from plutolab_api.services.agent_execution import execute_node
from plutolab_api.services.agent_github import GitHubSearchOutput
from tests.test_agent_execution import completion, provider, running
from tests.test_agent_execution import owners as owners
from tests.test_agent_execution import review_db as review_db
from tests.test_agents import local_only as local_only
from tests.test_review_domain import review_engine as review_engine


async def test_github_tool_result_reaches_model_with_provenance(review_db, owners, monkeypatch):
    run = await running(review_db, owners[0], tools=("search_github",))

    async def github(db, user_id, arguments):
        assert user_id == owners[0].id
        assert arguments.month == "2026-08"
        return GitHubSearchOutput(
            month="2026-08",
            observed_at="2026-09-25T00:00:00Z",
            source="https://github.com/search?q=fixture",
            incomplete_results=False,
            items=[],
        )

    monkeypatch.setattr(
        agent_tools,
        "REGISTRY",
        {
            **agent_tools.REGISTRY,
            "search_github": replace(agent_tools.REGISTRY["search_github"], executor=github),
        },
    )
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            assert body["tools"][0]["function"]["name"] == "search_github"
            assert "month" in body["tools"][0]["function"]["parameters"]["properties"]
            return httpx.Response(
                200,
                json=completion(
                    None,
                    tool={
                        "name": "search_github",
                        "arguments": '{"month":"2026-08"}',
                    },
                ),
            )
        result = json.loads(body["messages"][-1]["content"])
        assert result["month"] == "2026-08"
        assert result["source"] == "https://github.com/search?q=fixture"
        assert "not historical" in result["metric"]
        return httpx.Response(200, json=completion("# 调研结果\n无符合条件的仓库。"))

    node = await execute_node(review_db, owners[0].id, run.id, "a", provider(handler))
    assert node.state == "succeeded" and len(calls) == 2
    assert "# 调研结果" in decrypt(node.output_ciphertext)
