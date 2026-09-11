"""Regression coverage for stored keys and terminal RAG stream outcomes."""

import json
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.crypto import encrypt
from plutolab_api.models.rag import RAGConversation, RAGKnowledgeBase, RAGMessage
from plutolab_api.models.user import User
from plutolab_api.models.user_api_key import UserApiKey
from plutolab_api.schemas.rag import CitationItem
from plutolab_api.services.chat import RAGChatService
from plutolab_api.services.embedder import EmbeddingService


@pytest.mark.parametrize("provider_status", [200, 401])
async def test_chat_with_stored_provider_key(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, provider_status: int
) -> None:
    """Exercise real key storage/decryption and chat persistence with an HTTP stub."""
    user = User(email=f"key-{uuid4()}@example.com", password_hash="fixture")
    db_session.add(user)
    await db_session.flush()
    kb = RAGKnowledgeBase(user_id=user.id, title="Fixture")
    db_session.add(kb)
    await db_session.flush()
    conv = RAGConversation(kb_id=kb.id, user_id=user.id, title="New Chat")
    db_session.add_all(
        [
            conv,
            UserApiKey(
                user_id=user.id,
                provider="openai",
                key_ciphertext=encrypt("fixture-key"),
                key_preview="fixture",
            ),
        ]
    )
    await db_session.commit()
    conv_id, user_id = conv.id, user.id
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer fixture-key"
        return httpx.Response(
            provider_status,
            text=(
                'data: {"choices":[{"delta":{"content":"Stored key works"}}]}\n\ndata: [DONE]\n\n'
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        service = RAGChatService(http_client=client)
        monkeypatch.setattr(
            service, "_retrieve_with_reflection", AsyncMock(return_value=([], None))
        )
        events = [
            event async for event in service.stream_chat(db_session, conv, user_id, "Question")
        ]
    assert len(requests) == 1
    messages = list(
        await db_session.scalars(select(RAGMessage).where(RAGMessage.conversation_id == conv_id))
    )
    if provider_status == 200:
        assert events[-1] == "data: [DONE]\n\n"
        assert len(messages) == 1
        assert messages[0].content == "Stored key works"
    else:
        assert all("[DONE]" not in event for event in events)
        assert json.loads(events[-1][6:])["error"]["code"] == "generation_failed"
        assert messages == []


@pytest.mark.parametrize("ciphertext", [None, b"", b"invalid", "not-bytes"])
async def test_malformed_stored_key_is_explicit_failure(ciphertext: object) -> None:
    db = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.first.return_value = UserApiKey(key_ciphertext=ciphertext)
    db.execute = AsyncMock(return_value=result)
    with pytest.raises(ValueError, match="Stored provider API key") as error:
        await RAGChatService().get_user_llm_key(db, uuid4(), "openai")
    assert error.value.__cause__ is not None


async def test_no_stored_key_returns_none() -> None:
    db = MagicMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=result)
    assert await RAGChatService().get_user_llm_key(db, uuid4(), "openai") is None


@pytest.mark.parametrize("phase", ["preparation", "generation", "persistence"])
async def test_stream_failure_never_acknowledges_success(
    phase: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = MagicMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    embedder = MagicMock(spec=EmbeddingService)
    embedder.get_user_openai_key = AsyncMock(return_value=None)
    service = RAGChatService(embedder=embedder)
    monkeypatch.setattr(service, "_get_chat_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_retrieve_with_reflection", AsyncMock(return_value=([], None)))
    monkeypatch.setattr(service, "get_user_llm_key", AsyncMock(return_value=None))

    async def tokens(query: str, citations: list[CitationItem]) -> AsyncIterator[str]:
        yield "Partial answer"
        if phase == "generation":
            raise RuntimeError("private-provider-details")

    monkeypatch.setattr(service, "_stream_mock_response", tokens)
    if phase == "preparation":
        embedder.get_user_openai_key.side_effect = RuntimeError("private-provider-details")
    if phase == "persistence":
        db.commit.side_effect = RuntimeError("private-provider-details")
    conv = RAGConversation(id=uuid4(), kb_id=uuid4(), user_id=uuid4(), title="New Chat")
    events = [event async for event in service.stream_chat(db, conv, conv.user_id, "Question")]
    assert "[DONE]" not in "".join(events)
    assert "private-provider-details" not in "".join(events)
    failure = json.loads(events[-1][6:])
    assert failure["error"]["code"] == f"{phase}_failed"
    assert failure["delta"] == ""
    db.rollback.assert_awaited_once()
    if phase != "persistence":
        db.commit.assert_not_awaited()


async def test_truncated_provider_stream_is_rejected() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"part"}}]}\n\n'
            )
        )
    ) as client:
        service = RAGChatService(http_client=client)
        with pytest.raises(ValueError, match="before completion"):
            _ = [
                token
                async for token in service._stream_openai_compatible(
                    "https://fixture.invalid", "fixture", "fixture", []
                )
            ]


async def test_document_ingestion_failure_exposes_error_msg(client: httpx.AsyncClient) -> None:
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"document-{uuid4()}@example.com",
            "password": "fixture-password-123",
        },
    )
    assert registration.status_code == 201
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    kb = await client.post(
        "/api/v1/rag/knowledge-bases", headers=headers, json={"title": "Fixture"}
    )
    assert kb.status_code == 201
    base = f"/api/v1/rag/knowledge-bases/{kb.json()['id']}/documents"
    upload = await client.post(
        f"{base}/upload", headers=headers, files=[("files", ("empty.txt", b"", "text/plain"))]
    )
    assert upload.status_code == 202
    documents = await client.get(base, headers=headers)
    assert documents.status_code == 200
    document = documents.json()[0]
    assert document["status"] == "failed"
    assert document["error_msg"]
    assert "error_message" not in document
