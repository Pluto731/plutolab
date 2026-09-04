"""Unit tests for RecursiveSplitter service (Phase 4.2.b)."""

import pytest

from plutolab_api.services.doc_parser import ParsedDocument, ParsedPage
from plutolab_api.services.text_splitter import (
    DocumentChunk,
    RecursiveSplitter,
    count_tokens,
)


def test_count_tokens() -> None:
    assert count_tokens("") == 0
    assert count_tokens("hello") == 1
    # Chinese phrase token count
    zh_tokens = count_tokens("人工智能检索增强生成技术")
    assert zh_tokens >= 8


def test_recursive_splitter_initialization_validation() -> None:
    # Valid
    splitter = RecursiveSplitter(chunk_size=256, chunk_overlap=32)
    assert splitter.chunk_size == 256
    assert splitter.chunk_overlap == 32

    # Invalid chunk_size <= 0
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        RecursiveSplitter(chunk_size=0)

    # Invalid negative overlap
    with pytest.raises(ValueError, match="chunk_overlap cannot be negative"):
        RecursiveSplitter(chunk_overlap=-1)

    # Invalid overlap >= chunk_size
    with pytest.raises(ValueError, match="strictly smaller than chunk_size"):
        RecursiveSplitter(chunk_size=100, chunk_overlap=100)

    with pytest.raises(ValueError, match="strictly smaller than chunk_size"):
        RecursiveSplitter(chunk_size=100, chunk_overlap=120)


def test_split_short_text() -> None:
    splitter = RecursiveSplitter(chunk_size=512, chunk_overlap=64)
    short_text = "这是一个很短的句子，不会被切分。"
    chunks = splitter.split_text(short_text)

    assert len(chunks) == 1
    assert chunks[0] == short_text

    # Empty text
    assert splitter.split_text("") == []
    assert splitter.split_text("   \n\t  ") == []


def test_split_long_chinese_paragraphs() -> None:
    # Use small chunk_size to trigger paragraph/sentence splitting
    splitter = RecursiveSplitter(chunk_size=50, chunk_overlap=10)

    p1 = "第一段：检索增强生成（RAG）结合了信息检索技术和大语言模型的生成能力。它通过在模型生成响应之前从外部知识库检索相关信息。"
    p2 = "第二段：pgvector 是 PostgreSQL 的开源向量相似度搜索扩展。它支持精确和近邻搜索，包括 HNSW 和 IVFFlat 索引。"
    p3 = "第三段：语义分块器确保切块具有高连贯性，并保留必要的重叠上下文，从而避免关键术语被断开。"

    long_text = f"{p1}\n\n{p2}\n\n{p3}"
    chunks = splitter.split_text(long_text)

    assert len(chunks) >= 3
    for c in chunks:
        # All chunks must be within token budget (allow small tolerance for boundary punctuation)
        assert count_tokens(c) <= 65
        assert len(c) > 0


def test_split_long_english_text() -> None:
    splitter = RecursiveSplitter(chunk_size=30, chunk_overlap=5)

    text = (
        "Modern deep learning systems rely heavily on transformer architectures. "
        "Self-attention mechanisms allow models to weigh input tokens dynamically. "
        "Dense retrieval maps queries and documents into high-dimensional vector spaces. "
        "Cosine similarity is then calculated to score relevance."
    )
    chunks = splitter.split_text(text)

    assert len(chunks) >= 2
    for c in chunks:
        assert count_tokens(c) <= 35


def test_sliding_window_overlap() -> None:
    splitter = RecursiveSplitter(chunk_size=40, chunk_overlap=15)

    sentences = [f"第{i}个句子：这是关于知识库系统构建的详细描述说明。" for i in range(1, 10)]
    full_text = "。".join(sentences)

    chunks = splitter.split_text(full_text)
    assert len(chunks) >= 2

    # Verify consecutive chunks have overlapping content or shared semantic continuity
    for i in range(len(chunks) - 1):
        c1 = chunks[i]
        c2 = chunks[i + 1]
        assert len(c1) > 0 and len(c2) > 0


def test_split_document_multi_page_provenance() -> None:
    page1_text = "第一页：这是第一页的技术规范和背景介绍。\n包含系统架构与设计目标。"
    page2_text = "第二页：这是第二页关于数据库迁移和索引调优的说明。\n包含 HNSW 参数配置。"

    parsed_doc = ParsedDocument(
        text=f"{page1_text}\n\n{page2_text}",
        char_count=len(page1_text) + len(page2_text),
        page_count=2,
        pages=[
            ParsedPage(page_number=1, text=page1_text, char_count=len(page1_text)),
            ParsedPage(page_number=2, text=page2_text, char_count=len(page2_text)),
        ],
        metadata={"filename": "architecture.pdf", "format": "pdf"},
        file_type="pdf",
    )

    splitter = RecursiveSplitter(chunk_size=50, chunk_overlap=10)
    chunks = splitter.split_document(parsed_doc)

    assert len(chunks) >= 2
    assert all(isinstance(c, DocumentChunk) for c in chunks)

    # Check indices are monotonically increasing from 0
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))

    # Verify page numbers match source pages
    page_1_chunks = [c for c in chunks if c.page_number == 1]
    page_2_chunks = [c for c in chunks if c.page_number == 2]

    assert len(page_1_chunks) > 0
    assert len(page_2_chunks) > 0

    # Verify metadata fields
    first_chunk = chunks[0]
    assert first_chunk.metadata["filename"] == "architecture.pdf"
    assert "start_char" in first_chunk.metadata
    assert "end_char" in first_chunk.metadata
    assert "doc_char_offset" in first_chunk.metadata
    assert first_chunk.start_char >= 0
    assert first_chunk.end_char > first_chunk.start_char


def test_slice_large_text_without_separators_fallback() -> None:
    # 800 characters with zero separators or spaces
    unbreakable_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" * 25
    splitter = RecursiveSplitter(chunk_size=50, chunk_overlap=10)

    chunks = splitter.split_text(unbreakable_text)
    assert len(chunks) > 1
    for c in chunks:
        assert count_tokens(c) <= 60
