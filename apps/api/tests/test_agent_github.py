"""Public GitHub discovery: fixed origin, bounded data, permissions and provenance."""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from plutolab_api.services import agent_github, agent_tools


def payload(**changes):
    return {
        "incomplete_results": False,
        "items": [
            {
                "full_name": "example/research",
                "description": "public description",
                "stargazers_count": 42,
                "created_at": "2026-08-05T00:00:00Z",
                "html_url": "https://untrusted.invalid/ignored",
            }
        ],
        **changes,
    }


def transport(monkeypatch, handler):
    original = httpx.AsyncClient

    def client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return original(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(agent_github.httpx, "AsyncClient", client)


async def execute(arguments=None, enabled=("search_github",)):
    return await agent_tools.execute_tool(
        "search_github",
        arguments or {},
        db=None,
        user_id=uuid4(),
        enabled_tools=enabled,
    )


async def test_public_search_provenance_and_fixed_query(monkeypatch):
    def handler(request):
        assert request.url.host == "api.github.com"
        assert request.url.path == "/search/repositories"
        assert request.url.params["q"] == (
            'created:2026-08-01..2026-08-31 fork:false archived:false "AI" in:name,description'
        )
        assert request.url.params["sort"] == "stars"
        assert request.url.params["per_page"] == "5"
        assert "authorization" not in request.headers
        return httpx.Response(200, json=payload(incomplete_results=True))

    transport(monkeypatch, handler)
    result = await execute({"month": "2026-08", "keyword": "AI"})
    assert result.items[0].url == "https://github.com/example/research"
    assert result.items[0].stars == 42
    assert result.month == "2026-08" and result.observed_at
    assert result.incomplete_results is True
    assert "not historical" in result.metric
    assert result.source.startswith("https://github.com/search?")


async def test_previous_month_uses_server_clock_and_handles_year_boundary(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 2, tzinfo=UTC)

    monkeypatch.setattr(agent_github, "datetime", Clock)
    transport(monkeypatch, lambda request: httpx.Response(200, json=payload()))
    assert (await execute()).month == "2025-12"


@pytest.mark.parametrize(
    "arguments",
    [
        {"month": "0000-01"},
        {"month": "2026-13"},
        {"limit": True},
        {"limit": 11},
        {"url": "http://localhost"},
        {"keyword": "repo:private/secret"},
        {"user_id": "other"},
        {"keyword": "sk-abcdefghijklmnopqrstuv"},
    ],
)
async def test_invalid_arguments_never_fetch(monkeypatch, arguments):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid arguments must not reach HTTP")

    monkeypatch.setattr(agent_github.httpx, "AsyncClient", forbidden)
    with pytest.raises(agent_tools.ToolExecutionError, match=r"^invalid_arguments$"):
        await execute(arguments)


async def test_not_enabled_never_fetch():
    with pytest.raises(agent_tools.ToolExecutionError, match=r"^tool_not_allowed$"):
        await execute(enabled=("search_notes",))


@pytest.mark.parametrize(
    "mode", ["redirect", "rate_limit", "oversize", "malformed", "too_many", "unsafe"]
)
async def test_failures_are_bounded_and_redacted(monkeypatch, mode):
    calls = []

    def handler(request):
        calls.append(request)
        if mode == "redirect":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})
        if mode == "rate_limit":
            return httpx.Response(429, text="PRIVATE_RESPONSE")
        if mode == "oversize":
            return httpx.Response(200, content=b"x" * 262_145)
        if mode == "malformed":
            return httpx.Response(200, json=payload(items=[{"full_name": "../evil?q=x"}]))
        if mode == "too_many":
            return httpx.Response(200, json=payload(items=payload()["items"] * 11))
        data = payload()
        data["items"][0]["description"] = "api_key=PRIVATE_RESPONSE"
        return httpx.Response(200, json=data)

    transport(monkeypatch, handler)
    expected = "unsafe_output" if mode == "unsafe" else "tool_failed"
    with pytest.raises(agent_tools.ToolExecutionError, match=f"^{expected}$"):
        await execute()
    assert len(calls) == 1
