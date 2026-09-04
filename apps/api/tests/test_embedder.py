"""Unit tests for vector EmbeddingService (Phase 4.2.c)."""

import math
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.crypto import encrypt
from plutolab_api.models.user import User
from plutolab_api.models.user_api_key import UserApiKey
from plutolab_api.services.embedder import (
    EMBEDDING_DIM,
    EmbeddingError,
    EmbeddingService,
    generate_mock_vector,
)


def test_generate_mock_vector() -> None:
    v1 = generate_mock_vector("人工智能知识库")
    v2 = generate_mock_vector("人工智能知识库")
    v3 = generate_mock_vector("不同文本的向量对比")

    # 1. Dimension check
    assert len(v1) == EMBEDDING_DIM
    assert len(v3) == EMBEDDING_DIM

    # 2. Determinism check
    assert v1 == v2
    assert v1 != v3

    # 3. L2 Unit Norm check: sqrt(sum(x^2)) == 1.0
    norm = math.sqrt(sum(x * x for x in v1))
    assert norm == pytest.approx(1.0, abs=1e-3)


@pytest.mark.asyncio
async def test_embed_texts_mock_fallback() -> None:
    service = EmbeddingService()

    # Empty list
    assert await service.embed_texts([]) == []

    # Fallback to mock when api_key is None
    results = await service.embed_texts(["段落一", "段落二"])
    assert len(results) == 2
    assert len(results[0]) == EMBEDDING_DIM
    assert len(results[1]) == EMBEDDING_DIM

    # Fallback disabled without API key raises error
    with pytest.raises(EmbeddingError, match="OpenAI API key is required"):
        await service.embed_texts(["测试"], api_key=None, mock_fallback=False)


@pytest.mark.asyncio
async def test_embed_query_mock_fallback() -> None:
    service = EmbeddingService()
    query_vec = await service.embed_query("如何使用 RAG 提高检索准确率？")
    assert len(query_vec) == EMBEDDING_DIM
    norm = math.sqrt(sum(x * x for x in query_vec))
    assert norm == pytest.approx(1.0, abs=1e-3)


@pytest.mark.asyncio
async def test_embed_texts_with_mock_http_client() -> None:
    # Simulate OpenAI /v1/embeddings response
    fake_vector = [0.05] * EMBEDDING_DIM

    def mock_transport(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer sk-test-key-123"
        return httpx.Response(
            status_code=200,
            json={
                "data": [
                    {"embedding": fake_vector, "index": 0},
                    {"embedding": fake_vector, "index": 1},
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
    service = EmbeddingService(http_client=client)

    results = await service.embed_texts(["text1", "text2"], api_key="sk-test-key-123")
    assert len(results) == 2
    assert results[0] == fake_vector
    assert results[1] == fake_vector


@pytest.mark.asyncio
async def test_embed_texts_http_error_handling() -> None:
    # 1. 401 Unauthorized
    def transport_401(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=401, text="Unauthorized")

    client_401 = httpx.AsyncClient(transport=httpx.MockTransport(transport_401))
    service_401 = EmbeddingService(http_client=client_401)
    with pytest.raises(EmbeddingError, match="Invalid OpenAI API key"):
        await service_401.embed_texts(["test"], api_key="bad-key")

    # 2. 429 Rate Limit
    def transport_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=429, text="Rate limit exceeded")

    client_429 = httpx.AsyncClient(transport=httpx.MockTransport(transport_429))
    service_429 = EmbeddingService(http_client=client_429)
    with pytest.raises(EmbeddingError, match="rate limit or quota exceeded"):
        await service_429.embed_texts(["test"], api_key="quota-key")


@pytest.mark.asyncio
async def test_get_user_openai_key_decryption(
    db_session: AsyncSession,
) -> None:
    # Create test user
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"embedder-test-{uid.hex[:8]}@example.com",
        password_hash="fakehash",
        plan="free",
    )
    db_session.add(user)
    await db_session.flush()

    # Store encrypted OpenAI API Key using Phase 2.5 CryptoService
    plaintext_key = "sk-proj-super-secret-openai-key-9999"
    ciphertext = encrypt(plaintext_key)

    api_key_record = UserApiKey(
        user_id=user.id,
        provider="openai",
        key_ciphertext=ciphertext,
        key_preview="9999",
        label="我的主账号 Key",
    )
    db_session.add(api_key_record)
    await db_session.commit()

    # Query and decrypt using EmbeddingService
    service = EmbeddingService()
    decrypted_key = await service.get_user_openai_key(db_session, user.id)
    assert decrypted_key == plaintext_key

    # Query for non-existent user returns None
    other_key = await service.get_user_openai_key(db_session, uuid.uuid4())
    assert other_key is None
