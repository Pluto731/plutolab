"""Unit tests for RAG Pydantic v2 schemas (Phase 4.1.c)."""

from datetime import datetime, timezone
import uuid

import pytest
from pydantic import ValidationError

from plutolab_api.models.rag import RAGChunk
from plutolab_api.schemas.rag import (
    ChatQueryRewrite,
    ChatStreamChunk,
    ChunkPublic,
    CitationItem,
    ConversationCreate,
    ConversationPublic,
    ConversationSummary,
    ConversationUpdate,
    DocumentImportNoteRequest,
    DocumentPublic,
    KnowledgeBaseCreate,
    KnowledgeBasePublic,
    KnowledgeBaseSummary,
    KnowledgeBaseUpdate,
    MessageCreate,
    MessagePublic,
    SearchResultItem,
)


def test_citation_item_validation() -> None:
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    item = CitationItem(
        document_id=doc_id,
        chunk_id=chunk_id,
        filename="system_design.md",
        chunk_index=2,
        content="Antigravity architecture uses multi-agent coordination.",
        similarity=0.92,
        metadata={"page": 5, "char_offset": 320},
    )

    assert item.document_id == doc_id
    assert item.chunk_id == chunk_id
    assert item.similarity == 0.92
    assert item.metadata["page"] == 5

    # Invalid similarity (< 0.0 or > 1.0)
    with pytest.raises(ValidationError):
        CitationItem(
            document_id=doc_id,
            chunk_id=chunk_id,
            filename="test.md",
            chunk_index=0,
            content="abc",
            similarity=1.5,
        )

    with pytest.raises(ValidationError):
        CitationItem(
            document_id=doc_id,
            chunk_id=chunk_id,
            filename="test.md",
            chunk_index=0,
            content="abc",
            similarity=-0.1,
        )


def test_search_result_item() -> None:
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    result = SearchResultItem(
        chunk_id=chunk_id,
        document_id=doc_id,
        filename="deepseek.pdf",
        chunk_index=0,
        content="DeepSeek R1 reasoning trace.",
        score=0.88,
        retrieval_source="vector",
    )
    assert result.retrieval_source == "vector"
    assert result.score == 0.88


def test_knowledge_base_schemas() -> None:
    # 1. Create
    kb_in = KnowledgeBaseCreate(
        title="AI 论文与架构",
        description="前沿论文集合",
        icon="sparkles",
    )
    assert kb_in.title == "AI 论文与架构"

    # Empty title should fail min_length=1
    with pytest.raises(ValidationError):
        KnowledgeBaseCreate(title="")

    # 2. Update
    kb_up = KnowledgeBaseUpdate(title="新标题")
    assert kb_up.title == "新标题"
    assert kb_up.description is None

    # 3. Public & Summary
    kb_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    kb_pub = KnowledgeBasePublic(
        id=kb_id,
        user_id=user_id,
        title="AI 论文",
        description="测试描述",
        icon="book",
        doc_count=12,
        char_count=54000,
        created_at=now,
        updated_at=now,
    )
    assert kb_pub.doc_count == 12
    assert kb_pub.char_count == 54000

    kb_sum = KnowledgeBaseSummary(
        id=kb_id,
        title="AI 论文",
        description="测试描述",
        icon="book",
        doc_count=12,
        char_count=54000,
        created_at=now,
        updated_at=now,
    )
    assert kb_sum.id == kb_id


def test_document_schemas() -> None:
    # 1. Import notes validation
    note_ids = [uuid.uuid4(), uuid.uuid4()]
    import_req = DocumentImportNoteRequest(note_ids=note_ids)
    assert len(import_req.note_ids) == 2

    # Empty note_ids list should fail
    with pytest.raises(ValidationError):
        DocumentImportNoteRequest(note_ids=[])

    # 2. DocumentPublic
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    doc_pub = DocumentPublic(
        id=doc_id,
        kb_id=kb_id,
        filename="spec.docx",
        file_type="docx",
        file_size=20480,
        status="ready",
        char_count=1500,
        chunk_count=3,
        source_type="upload",
        created_at=now,
        updated_at=now,
    )
    assert doc_pub.status == "ready"
    assert doc_pub.chunk_count == 3
    assert doc_pub.error_msg is None

    # Invalid status should fail
    with pytest.raises(ValidationError):
        DocumentPublic(
            id=doc_id,
            kb_id=kb_id,
            filename="spec.docx",
            file_type="docx",
            file_size=20480,
            status="unknown_status",  # type: ignore[arg-type]
            char_count=1500,
            chunk_count=3,
            source_type="upload",
            created_at=now,
            updated_at=now,
        )


def test_chunk_public_with_orm_metadata_mapping() -> None:
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. Test with dict using "metadata"
    chunk_dict = {
        "id": chunk_id,
        "document_id": doc_id,
        "kb_id": kb_id,
        "chunk_index": 0,
        "content": "Sample content snippet",
        "token_count": 128,
        "metadata": {"section": "intro", "heading": "Overview"},
        "created_at": now,
    }
    chunk_p1 = ChunkPublic.model_validate(chunk_dict)
    assert chunk_p1.metadata["section"] == "intro"

    # 2. Test with dict using "metadata_" (simulating raw ORM dict or alias)
    chunk_dict_alias = {
        "id": chunk_id,
        "document_id": doc_id,
        "kb_id": kb_id,
        "chunk_index": 0,
        "content": "Sample content snippet",
        "token_count": 128,
        "metadata_": {"section": "appendix"},
        "created_at": now,
    }
    chunk_p2 = ChunkPublic.model_validate(chunk_dict_alias)
    assert chunk_p2.metadata["section"] == "appendix"

    # 3. Test with actual SQLAlchemy RAGChunk instance
    orm_chunk = RAGChunk(
        id=chunk_id,
        document_id=doc_id,
        kb_id=kb_id,
        chunk_index=1,
        content="ORM mapped content",
        embedding=[0.0] * 1536,
        token_count=256,
        metadata_={"page": 3, "tags": ["rag", "ai"]},
        created_at=now,
    )
    chunk_p3 = ChunkPublic.model_validate(orm_chunk)
    assert chunk_p3.chunk_index == 1
    assert chunk_p3.token_count == 256
    assert chunk_p3.metadata["page"] == 3
    assert chunk_p3.metadata["tags"] == ["rag", "ai"]


def test_conversation_and_message_schemas() -> None:
    conv_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # 1. ConversationCreate & Update
    c_create = ConversationCreate()
    assert c_create.title == "新对话"

    c_update = ConversationUpdate(title="关于 RAG 的深入探讨")
    assert c_update.title == "关于 RAG 的深入探讨"

    # 2. MessageCreate
    m_create = MessageCreate(content="请帮我总结这篇文章的核心论点", top_k=8, hybrid_search=True)
    assert m_create.top_k == 8
    assert m_create.hybrid_search is True

    # top_k bounds check
    with pytest.raises(ValidationError):
        MessageCreate(content="test", top_k=0)

    with pytest.raises(ValidationError):
        MessageCreate(content="test", top_k=25)

    # 3. MessagePublic with nested CitationItem
    citation = CitationItem(
        document_id=doc_id,
        chunk_id=chunk_id,
        filename="paper.pdf",
        chunk_index=4,
        content="The proposed method outperforms baselines by 15%.",
        similarity=0.95,
    )
    m_pub = MessagePublic(
        id=msg_id,
        conversation_id=conv_id,
        role="assistant",
        content="根据论文第 4 节，核心结论如下：[^1]",
        citations=[citation],
        created_at=now,
    )
    assert len(m_pub.citations) == 1
    assert m_pub.citations[0].filename == "paper.pdf"

    # 4. ConversationPublic with nested messages
    conv_pub = ConversationPublic(
        id=conv_id,
        kb_id=kb_id,
        title="论文讨论",
        messages=[m_pub],
        created_at=now,
        updated_at=now,
    )
    assert len(conv_pub.messages) == 1
    assert conv_pub.messages[0].role == "assistant"

    # 5. ConversationSummary
    conv_sum = ConversationSummary(
        id=conv_id,
        kb_id=kb_id,
        title="论文讨论",
        message_count=6,
        created_at=now,
        updated_at=now,
    )
    assert conv_sum.message_count == 6


def test_streaming_and_agentic_schemas() -> None:
    # 1. Stream chunk with delta
    chunk1 = ChatStreamChunk(delta="Hello ")
    assert chunk1.delta == "Hello "
    assert chunk1.citation is None

    # 2. Stream chunk with citation
    cit = CitationItem(
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        filename="manual.md",
        chunk_index=0,
        content="Installation guide",
        similarity=0.85,
    )
    chunk2 = ChatStreamChunk(citation=cit)
    assert chunk2.citation is not None
    assert chunk2.citation.filename == "manual.md"

    # 3. Stream chunk finish
    chunk3 = ChatStreamChunk(finish_reason="stop")
    assert chunk3.finish_reason == "stop"

    # 4. Query rewrite
    rewrite = ChatQueryRewrite(
        original_query="如何优化向量检索？",
        rewritten_query="pgvector HNSW 索引调优参数与混合检索 RRF 算法",
        sub_queries=["pgvector m 和 ef 参数设置", "RRF 算法融合公式"],
    )
    assert len(rewrite.sub_queries) == 2
    assert "pgvector" in rewrite.rewritten_query
