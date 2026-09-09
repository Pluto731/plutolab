"""Exercise ingestion using committed records and independent database connections."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from plutolab_api.models.rag import RAGChunk, RAGDocument, RAGKnowledgeBase
from plutolab_api.models.user import User
from plutolab_api.services.embedder import EmbeddingService
from plutolab_api.services.ingestion import DocumentIngestionService


@pytest.mark.parametrize(
    "content,expected", [(b"A short knowledge document.", "ready"), (b"", "failed")]
)
async def test_ingestion_after_request_session_closed(
    test_engine: AsyncEngine, content: bytes, expected: str
) -> None:
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    user_id, kb_id, doc_id = uuid4(), uuid4(), uuid4()
    try:
        async with factory() as request:
            request.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="test"))
            await request.flush()
            request.add(RAGKnowledgeBase(id=kb_id, user_id=user_id, title="Independent session"))
            await request.flush()
            request.add(
                RAGDocument(
                    id=doc_id,
                    kb_id=kb_id,
                    user_id=user_id,
                    filename="test.txt",
                    file_type="txt",
                    file_size=len(content),
                    source_type="upload",
                    status="pending",
                )
            )
            await request.commit()

        worker = DocumentIngestionService(session_factory=factory)
        result = await worker.process_document(doc_id, content, "test.txt", "txt", kb_id, user_id)
        assert result == (expected == "ready")
        async with factory() as verification:
            doc = await verification.get(RAGDocument, doc_id)
            assert doc is not None and doc.status == expected
            count = await verification.scalar(
                select(func.count()).select_from(RAGChunk).where(RAGChunk.document_id == doc_id)
            )
            assert count == doc.chunk_count
            if expected == "ready":
                assert count and count > 0
            else:
                assert doc.error_msg
    finally:
        async with factory() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()


async def test_unexpected_ingestion_error_is_sanitized(db_session) -> None:
    class BrokenEmbedder(EmbeddingService):
        async def embed_texts(self, *args, **kwargs):
            raise RuntimeError("private document and secret credential")

    user_id, kb_id, doc_id = uuid4(), uuid4(), uuid4()
    db_session.add(User(id=user_id, email=f"{user_id}@example.com", password_hash="test"))
    await db_session.flush()
    db_session.add(RAGKnowledgeBase(id=kb_id, user_id=user_id, title="Failure"))
    await db_session.flush()
    db_session.add(
        RAGDocument(
            id=doc_id,
            kb_id=kb_id,
            user_id=user_id,
            filename="test.txt",
            file_type="txt",
            file_size=10,
            source_type="upload",
            status="pending",
        )
    )
    await db_session.commit()
    assert not await DocumentIngestionService(embedder=BrokenEmbedder()).process_document(
        doc_id, b"Test content", "test.txt", "txt", kb_id, user_id, session=db_session
    )
    doc = await db_session.get(RAGDocument, doc_id)
    assert doc.status == "failed"
    assert "secret" not in doc.error_msg
