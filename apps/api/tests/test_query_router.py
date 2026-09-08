"""Tests for deterministic Agentic RAG query planning and reflection."""

from uuid import uuid4

import pytest

from plutolab_api.schemas.rag import SearchResultItem
from plutolab_api.services.chat import RAGChatService
from plutolab_api.services.query_router import (
    build_query_plan,
    retrieval_confidence,
    should_reflect,
)


def _result(content: str, score: float = 0.8) -> SearchResultItem:
    return SearchResultItem(
        chunk_id=uuid4(),
        document_id=uuid4(),
        filename="test.md",
        chunk_index=0,
        content=content,
        score=score,
        retrieval_source="hybrid",
    )


def test_build_query_plan_removes_courtesy_prefix_and_extracts_terms() -> None:
    plan = build_query_plan("请问 Pluto 的卫星数量是多少？")

    assert plan.original_query == "请问 Pluto 的卫星数量是多少？"
    assert "请问" not in plan.semantic_query
    assert "pluto" in plan.keyword_query
    assert "卫星数量" in plan.keyword_query


def test_build_query_plan_uses_recent_user_context() -> None:
    plan = build_query_plan(
        "它有几个？",
        history=[
            {"role": "assistant", "content": "我们正在讨论 Pluto。"},
            {"role": "user", "content": "先介绍 Pluto 的基本信息"},
        ],
    )

    assert "pluto" in plan.semantic_query.casefold()


def test_retrieval_confidence_is_bounded_and_reflects_coverage() -> None:
    results = [_result("Pluto is a dwarf planet with five satellites.", score=0.9)]
    confidence = retrieval_confidence(results, "Pluto 有几颗卫星")

    assert 0.0 <= confidence <= 1.0
    assert confidence > retrieval_confidence([], "Pluto")
    assert should_reflect([], "Pluto")


def test_should_reflect_skips_high_confidence_results() -> None:
    results = [_result("PostgreSQL pgvector vector similarity", score=0.95)]

    assert not should_reflect(results, "PostgreSQL pgvector vector similarity")


def test_retrieval_confidence_scales_hybrid_rrf_scores() -> None:
    results = [_result("PostgreSQL pgvector vector similarity", score=0.03)]

    assert retrieval_confidence(results, "PostgreSQL pgvector vector similarity") > 0.7


@pytest.mark.asyncio
async def test_chat_retrieval_reflection_merges_retry_results() -> None:
    first = _result("unrelated content", score=0.1)
    second = _result("Pluto 卫星数量 five", score=0.9)

    class FakeRetriever:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def search(self, **kwargs: object) -> list[SearchResultItem]:
            query = str(kwargs["query"])
            self.queries.append(query)
            return [first] if len(self.queries) == 1 else [second]

    class Conversation:
        kb_id = uuid4()
        id = uuid4()

    retriever = FakeRetriever()
    service = RAGChatService(retriever=retriever)  # type: ignore[arg-type]
    results, plan = await service._retrieve_with_reflection(
        db=None,  # type: ignore[arg-type]
        conversation=Conversation(),  # type: ignore[arg-type]
        query="请问 Pluto 卫星数量？",
        history=[],
        top_k=1,
        search_mode="hybrid",
        api_key=None,
    )

    assert len(retriever.queries) == 2
    assert plan.original_query == "请问 Pluto 卫星数量？"
    assert results[0].chunk_id == second.chunk_id
