"""Unit tests for HybridRetriever service (Phase 4.3.a)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models.rag import RAGChunk, RAGDocument, RAGKnowledgeBase
from plutolab_api.models.user import User
from plutolab_api.schemas.rag import SearchResultItem
from plutolab_api.services.embedder import EmbeddingService, generate_mock_vector
from plutolab_api.services.retriever import HybridRetriever


@pytest.fixture
async def sample_kb_data(db_session: AsyncSession) -> dict[str, uuid.UUID]:
    """Seed test user, knowledge bases, documents, and chunks."""
    # 1. User
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"retriever-test-{uid.hex[:8]}@example.com",
        password_hash="fakehash",
        plan="free",
    )
    db_session.add(user)
    await db_session.flush()

    # 2. Knowledge Base A & B (for isolation test)
    kb_a = RAGKnowledgeBase(
        user_id=user.id,
        title="技术架构库 A",
        description="测试知识库 A",
    )
    kb_b = RAGKnowledgeBase(
        user_id=user.id,
        title="机密隔离库 B",
        description="测试知识库 B",
    )
    db_session.add_all([kb_a, kb_b])
    await db_session.flush()

    # 3. Documents
    doc_a = RAGDocument(
        kb_id=kb_a.id,
        user_id=user.id,
        filename="system_architecture.md",
        file_type="md",
        file_size=1024,
        status="ready",
    )
    doc_b = RAGDocument(
        kb_id=kb_b.id,
        user_id=user.id,
        filename="secret_doc.txt",
        file_type="txt",
        file_size=512,
        status="ready",
    )
    db_session.add_all([doc_a, doc_b])
    await db_session.flush()

    # 4. Chunks for KB A
    text_1 = "FastAPI is a high-performance modern web framework for Python."
    text_2 = "PostgreSQL pgvector extension enables efficient vector similarity search."
    text_3 = "Antigravity multi-agent systems coordinate complex agentic coding workflows."

    c1 = RAGChunk(
        document_id=doc_a.id,
        kb_id=kb_a.id,
        chunk_index=0,
        content=text_1,
        embedding=generate_mock_vector("FastAPI web framework Python"),
        token_count=10,
        metadata_={"page_number": 1, "topic": "backend"},
    )
    c2 = RAGChunk(
        document_id=doc_a.id,
        kb_id=kb_a.id,
        chunk_index=1,
        content=text_2,
        embedding=generate_mock_vector("PostgreSQL pgvector vector similarity"),
        token_count=10,
        metadata_={"page_number": 1, "topic": "database"},
    )
    c3 = RAGChunk(
        document_id=doc_a.id,
        kb_id=kb_a.id,
        chunk_index=2,
        content=text_3,
        embedding=generate_mock_vector("Antigravity multi-agent workflows"),
        token_count=10,
        metadata_={"page_number": 2, "topic": "ai"},
    )

    # Chunk for KB B (Isolated)
    c_b = RAGChunk(
        document_id=doc_b.id,
        kb_id=kb_b.id,
        chunk_index=0,
        content="This is private secret information belonging strictly to KB B.",
        embedding=generate_mock_vector("private secret information"),
        token_count=10,
        metadata_={"page_number": 1},
    )

    db_session.add_all([c1, c2, c3, c_b])
    await db_session.commit()

    return {
        "user_id": user.id,
        "kb_a_id": kb_a.id,
        "kb_b_id": kb_b.id,
        "doc_a_id": doc_a.id,
        "chunk_1_id": c1.id,
        "chunk_2_id": c2.id,
        "chunk_3_id": c3.id,
        "chunk_b_id": c_b.id,
    }


@pytest.mark.asyncio
async def test_hybrid_retriever_vector_mode(
    db_session: AsyncSession, sample_kb_data: dict[str, uuid.UUID]
) -> None:
    retriever = HybridRetriever()
    kb_id = sample_kb_data["kb_a_id"]

    results = await retriever.search(
        db=db_session,
        kb_id=kb_id,
        query="PostgreSQL pgvector vector similarity",
        top_k=3,
        mode="vector",
    )

    assert len(results) > 0
    top_hit = results[0]
    assert isinstance(top_hit, SearchResultItem)
    assert top_hit.retrieval_source == "vector"
    assert top_hit.chunk_id == sample_kb_data["chunk_2_id"]
    assert top_hit.filename == "system_architecture.md"
    assert top_hit.score > 0.0


@pytest.mark.asyncio
async def test_hybrid_retriever_fts_mode(
    db_session: AsyncSession, sample_kb_data: dict[str, uuid.UUID]
) -> None:
    retriever = HybridRetriever()
    kb_id = sample_kb_data["kb_a_id"]

    results = await retriever.search(
        db=db_session,
        kb_id=kb_id,
        query="FastAPI framework",
        top_k=3,
        mode="fts",
    )

    assert len(results) >= 1
    top_hit = results[0]
    assert top_hit.retrieval_source == "fts"
    assert top_hit.chunk_id == sample_kb_data["chunk_1_id"]
    assert "FastAPI" in top_hit.content


@pytest.mark.asyncio
async def test_hybrid_retriever_hybrid_mode_rrf(
    db_session: AsyncSession, sample_kb_data: dict[str, uuid.UUID]
) -> None:
    retriever = HybridRetriever()
    kb_id = sample_kb_data["kb_a_id"]

    # Query matches both FTS keyword 'pgvector' and semantic embedding
    results = await retriever.search(
        db=db_session,
        kb_id=kb_id,
        query="PostgreSQL pgvector vector similarity",
        top_k=2,
        mode="hybrid",
    )

    assert len(results) >= 1
    top_hit = results[0]
    # Chunk 2 matched both vector and FTS, so source should be 'hybrid'
    assert top_hit.retrieval_source == "hybrid"
    assert top_hit.chunk_id == sample_kb_data["chunk_2_id"]
    assert top_hit.score > 0.0


@pytest.mark.asyncio
async def test_hybrid_retriever_empty_and_no_match(
    db_session: AsyncSession, sample_kb_data: dict[str, uuid.UUID]
) -> None:
    retriever = HybridRetriever()
    kb_id = sample_kb_data["kb_a_id"]

    # 1. Empty string
    assert await retriever.search(db=db_session, kb_id=kb_id, query="") == []
    assert await retriever.search(db=db_session, kb_id=kb_id, query="   ") == []

    # 2. Query with no text match in FTS
    results = await retriever.search(
        db=db_session,
        kb_id=kb_id,
        query="xyznonsensetermthatneverexists",
        top_k=5,
        mode="fts",
    )
    assert results == []


@pytest.mark.asyncio
async def test_hybrid_retriever_kb_isolation(
    db_session: AsyncSession, sample_kb_data: dict[str, uuid.UUID]
) -> None:
    retriever = HybridRetriever()
    kb_a_id = sample_kb_data["kb_a_id"]
    kb_b_id = sample_kb_data["kb_b_id"]

    # Search query that exists strictly in KB B
    results_a = await retriever.search(
        db=db_session,
        kb_id=kb_a_id,
        query="private secret information",
        mode="fts",
    )
    # KB A must NOT leak KB B's chunks!
    assert len(results_a) == 0

    # Searching KB B finds it
    results_b = await retriever.search(
        db=db_session,
        kb_id=kb_b_id,
        query="private secret information",
        mode="fts",
    )
    assert len(results_b) == 1
    assert results_b[0].chunk_id == sample_kb_data["chunk_b_id"]
