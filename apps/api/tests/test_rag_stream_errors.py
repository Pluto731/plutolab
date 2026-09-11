"""Provider failures must not become mock success or expose provider exception details."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from plutolab_api.services.chat import RAGChatService


async def test_remote_stream_failure_is_explicit_and_sanitized(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_stream(self, **kwargs) -> AsyncIterator[str]:
        yield "Partial response"
        raise RuntimeError("private-provider-key-and-body")

    monkeypatch.setattr(RAGChatService, "get_user_llm_key", AsyncMock(return_value="test-key"))
    monkeypatch.setattr(RAGChatService, "_stream_openai_compatible", failing_stream)
    auth = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "stream-failure@example.com",
            "password": "test-password-12345",
        },
    )
    assert auth.status_code == 201
    headers = {"Authorization": f"Bearer {auth.json()['access_token']}"}
    kb = await client.post("/api/v1/rag/knowledge-bases", headers=headers, json={"title": "Errors"})
    conversation = await client.post(
        f"/api/v1/rag/knowledge-bases/{kb.json()['id']}/conversations", headers=headers, json={}
    )
    result = await client.post(
        f"/api/v1/rag/conversations/{conversation.json()['id']}/messages",
        headers=headers,
        json={"content": "Question", "stream": True},
    )
    assert result.status_code == 200
    assert '"finish_reason":"error"' in result.text
    assert "Partial response" in result.text
    assert "private-provider-key-and-body" not in result.text
    assert '"finish_reason":"stop"' not in result.text
