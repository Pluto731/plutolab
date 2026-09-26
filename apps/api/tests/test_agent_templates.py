"""Built-in templates import into independent owner-private Agent/Workflow copies."""

from tests.test_agents import agent_client as agent_client
from tests.test_agents import auth as auth
from tests.test_agents import local_only as local_only
from tests.test_review_domain import owners as owners
from tests.test_review_domain import review_db as review_db
from tests.test_review_domain import review_engine as review_engine


async def test_template_list_import_duplicate_and_tenant_isolation(agent_client, owners):
    headers = auth(owners[0])
    catalog = await agent_client.get("/api/v1/workflows/templates", headers=headers)
    assert catalog.status_code == 200
    assert [item["slug"] for item in catalog.json()["items"]] == [
        "research-and-review",
        "github-monthly-research",
    ]
    path = "/api/v1/workflows/templates/research-and-review/versions/1/import"
    first = await agent_client.post(path, json={}, headers=headers)
    second = await agent_client.post(path, json={}, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    first_agent_ids = {node["agent_id"] for node in first.json()["graph"]["nodes"]}
    second_agent_ids = {node["agent_id"] for node in second.json()["graph"]["nodes"]}
    assert first_agent_ids.isdisjoint(second_agent_ids)
    assert (
        await agent_client.get(f"/api/v1/workflows/{first.json()['id']}", headers=auth(owners[1]))
    ).status_code == 404
    assert (
        await agent_client.post(
            "/api/v1/workflows/templates/research-and-review/versions/2/import",
            json={},
            headers=headers,
        )
    ).status_code == 404


async def test_template_import_rejects_missing_required_tool(agent_client, owners, monkeypatch):
    from plutolab_api.services import workflow_templates

    monkeypatch.setattr(workflow_templates, "REGISTRY", {})
    response = await agent_client.post(
        "/api/v1/workflows/templates/research-and-review/versions/1/import",
        json={},
        headers=auth(owners[0]),
    )
    assert response.status_code == 422


async def test_github_template_import_preserves_explicit_tool_permissions(agent_client, owners):
    headers = auth(owners[0])
    response = await agent_client.post(
        "/api/v1/workflows/templates/github-monthly-research/versions/1/import",
        json={},
        headers=headers,
    )
    assert response.status_code == 201
    nodes = {node["id"]: node for node in response.json()["graph"]["nodes"]}
    for name, expected in [("research", ["search_github"]), ("review", [])]:
        path = f"/api/v1/agents/{nodes[name]['agent_id']}"
        agent = await agent_client.get(path, headers=headers)
        assert agent.status_code == 200
        assert agent.json()["tools"] == expected
        assert (await agent_client.get(path, headers=auth(owners[1]))).status_code == 404
