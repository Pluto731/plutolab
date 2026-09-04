"""Unit tests for RAG SQLAlchemy models (Phase 4.1.a)."""

import uuid

from pgvector.sqlalchemy import Vector

from plutolab_api.models import (
    RAGChunk,
    RAGConversation,
    RAGDocument,
    RAGKnowledgeBase,
    RAGMessage,
)


def test_rag_knowledge_base_attributes() -> None:
    uid = uuid.uuid4()
    kb = RAGKnowledgeBase(
        user_id=uid,
        title="深度学习论文库",
        description="收集前沿大模型架构论文",
        icon="brain",
    )
    assert kb.title == "深度学习论文库"
    assert kb.description == "收集前沿大模型架构论文"
    assert kb.icon == "brain"
    assert kb.user_id == uid
    assert "深度学习论文库" in repr(kb)


def test_rag_document_attributes() -> None:
    uid = uuid.uuid4()
    kb_id = uuid.uuid4()
    doc = RAGDocument(
        kb_id=kb_id,
        user_id=uid,
        filename="attention_is_all_you_need.pdf",
        file_type="pdf",
        file_size=102400,
        status="pending",
        source_type="upload",
    )
    assert doc.filename == "attention_is_all_you_need.pdf"
    assert doc.file_type == "pdf"
    assert doc.file_size == 102400
    assert doc.status == "pending"
    assert doc.source_type == "upload"
    assert doc.source_note_id is None
    assert "attention_is_all_you_need.pdf" in repr(doc)


def test_rag_chunk_vector_and_metadata() -> None:
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    fake_embedding = [0.01] * 1536

    chunk = RAGChunk(
        document_id=doc_id,
        kb_id=kb_id,
        chunk_index=0,
        content="Transformer architecture uses multi-head attention.",
        embedding=fake_embedding,
        token_count=42,
        metadata_={"page": 1, "source": "attention.pdf"},
    )
    assert chunk.document_id == doc_id
    assert chunk.chunk_index == 0
    assert len(chunk.embedding) == 1536
    assert chunk.metadata_["page"] == 1
    assert "doc=" in repr(chunk)

    # Check table column mapping
    col = RAGChunk.__table__.c.embedding
    assert isinstance(col.type, Vector)
    assert col.type.dim == 1536

    # Verify column name "metadata" vs python attribute metadata_
    assert RAGChunk.__table__.c.metadata is not None


def test_rag_conversation_and_message() -> None:
    kb_id = uuid.uuid4()
    user_id = uuid.uuid4()
    conv = RAGConversation(kb_id=kb_id, user_id=user_id, title="探讨 Transformer 注意力机制")
    assert conv.title == "探讨 Transformer 注意力机制"
    assert conv.kb_id == kb_id
    assert "探讨 Transformer 注意力机制" in repr(conv)

    conv_id = uuid.uuid4()
    msg = RAGMessage(
        conversation_id=conv_id,
        role="assistant",
        content="Self-attention allows the model to relate different positions...",
        citations=[{"ref_index": 1, "doc_title": "attention.pdf", "page": 3}],
    )
    assert msg.role == "assistant"
    assert len(msg.citations) == 1
    assert msg.citations[0]["ref_index"] == 1
    assert "assistant" in repr(msg)
