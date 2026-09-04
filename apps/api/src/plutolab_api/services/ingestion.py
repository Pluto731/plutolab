"""Document ingestion service for processing and vectorizing uploaded files (Phase 4.3.b).

Orchestrates:
1. Status transition: pending -> parsing -> ready / failed
2. Multi-format parsing via DocumentParser (4.2.a)
3. Recursive semantic chunking via RecursiveSplitter (4.2.b)
4. Vector embedding via EmbeddingService (4.2.c) with Fernet key decryption
5. Bulk chunk persistence into PostgreSQL + pgvector
"""

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from plutolab_api.db.session import AsyncSessionLocal
from plutolab_api.models.rag import RAGChunk, RAGDocument
from plutolab_api.services.doc_parser import DocParseError, DocumentParser
from plutolab_api.services.embedder import EmbeddingError, EmbeddingService
from plutolab_api.services.text_splitter import RecursiveSplitter

logger = structlog.get_logger(__name__)


class DocumentIngestionService:
    """End-to-end ingestion pipeline worker."""

    def __init__(
        self,
        embedder: EmbeddingService | None = None,
        splitter: RecursiveSplitter | None = None,
    ) -> None:
        self.embedder = embedder or EmbeddingService()
        self.splitter = splitter or RecursiveSplitter()

    async def process_document(
        self,
        doc_id: UUID,
        content: bytes,
        filename: str,
        file_type: str,
        kb_id: UUID,
        user_id: UUID,
        session: AsyncSession | None = None,
    ) -> bool:
        """Run the end-to-end ingestion pipeline for a single document.

        Args:
            doc_id: RAGDocument primary key.
            content: Raw file bytes or text.
            filename: Original file name.
            file_type: Extension or source type (md, txt, pdf, docx, note).
            kb_id: Target knowledge base UUID.
            user_id: Owner user UUID.
            session: Optional existing AsyncSession (used for test isolation).

        Returns:
            True if ingestion succeeded, False if failed.
        """
        if session is not None:
            return await self._execute_pipeline(
                session=session,
                doc_id=doc_id,
                content=content,
                filename=filename,
                file_type=file_type,
                kb_id=kb_id,
                user_id=user_id,
            )

        # In production background task: manage autonomous session
        async with AsyncSessionLocal() as autonomous_session:
            return await self._execute_pipeline(
                session=autonomous_session,
                doc_id=doc_id,
                content=content,
                filename=filename,
                file_type=file_type,
                kb_id=kb_id,
                user_id=user_id,
            )

    async def _execute_pipeline(
        self,
        session: AsyncSession,
        doc_id: UUID,
        content: bytes,
        filename: str,
        file_type: str,
        kb_id: UUID,
        user_id: UUID,
    ) -> bool:
        doc = await session.get(RAGDocument, doc_id)
        if not doc:
            logger.error("ingestion_doc_not_found", doc_id=str(doc_id))
            return False

        try:
            # 1. Update status to parsing
            doc.status = "parsing"
            doc.error_msg = None
            await session.commit()
            await session.refresh(doc)

            # 2. Parse document text & extract pages
            # Normalize 'note' file_type to 'md' for parsing
            norm_type = "md" if file_type == "note" else file_type
            parsed_doc = DocumentParser.parse(content=content, filename=filename, file_type=norm_type)

            # 3. Recursively split into semantic chunks
            chunks = self.splitter.split_document(parsed_doc)
            if not chunks:
                raise DocParseError("Document produced 0 semantic chunks after splitting.")

            # 4. Resolve user's OpenAI API Key (Fernet decrypted)
            user_api_key = await self.embedder.get_user_openai_key(session, user_id)

            # 5. Generate 1536-dimensional embeddings (Batch 64)
            chunk_texts = [c.content for c in chunks]
            embeddings = await self.embedder.embed_texts(
                chunk_texts,
                api_key=user_api_key,
                mock_fallback=True,
            )

            # 6. Clear any old chunks for this document (idempotency)
            await session.execute(delete(RAGChunk).where(RAGChunk.document_id == doc_id))

            # 7. Insert new RAGChunks
            db_chunks: list[RAGChunk] = []
            for chunk_meta, emb in zip(chunks, embeddings, strict=True):
                db_chunk = RAGChunk(
                    document_id=doc_id,
                    kb_id=kb_id,
                    chunk_index=chunk_meta.chunk_index,
                    content=chunk_meta.content,
                    embedding=emb,
                    token_count=chunk_meta.token_count,
                    metadata_=chunk_meta.metadata,
                )
                db_chunks.append(db_chunk)

            session.add_all(db_chunks)

            # 8. Mark document as ready
            doc.status = "ready"
            doc.char_count = parsed_doc.char_count
            doc.chunk_count = len(chunks)
            doc.error_msg = None
            await session.commit()

            logger.info(
                "document_ingestion_success",
                doc_id=str(doc_id),
                filename=filename,
                chunks=len(chunks),
                chars=parsed_doc.char_count,
            )
            return True

        except Exception as exc:
            logger.error(
                "document_ingestion_failed",
                doc_id=str(doc_id),
                filename=filename,
                error=str(exc),
            )
            await session.rollback()

            # Refresh and set status to failed
            failed_doc = await session.get(RAGDocument, doc_id)
            if failed_doc:
                failed_doc.status = "failed"
                failed_doc.error_msg = str(exc)[:500]
                await session.commit()

            return False
