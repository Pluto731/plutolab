"""Hybrid retrieval engine for RAG knowledge bases (Phase 4.3.a).

Combines:
- Dense vector similarity search using pgvector HNSW cosine distance (`<=>`).
- Sparse lexical search using PostgreSQL full-text search (`to_tsvector` + `plainto_tsquery`).
- Reciprocal Rank Fusion (RRF, k=60) for multi-channel score normalization and deduplication.
"""

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from plutolab_api.models.rag import RAGChunk, RAGDocument
from plutolab_api.schemas.rag import SearchResultItem
from plutolab_api.services.embedder import EmbeddingService

logger = structlog.get_logger(__name__)

SearchMode = Literal["hybrid", "vector", "fts"]


class HybridRetriever:
    """Dense + Sparse hybrid recall engine with Reciprocal Rank Fusion."""

    def __init__(self, embedder: EmbeddingService | None = None) -> None:
        self.embedder = embedder or EmbeddingService()

    async def search(
        self,
        db: AsyncSession,
        kb_id: UUID,
        query: str,
        top_k: int = 5,
        mode: SearchMode = "hybrid",
        vector_weight: float = 1.0,
        fts_weight: float = 1.0,
        rrf_k: int = 60,
        api_key: str | None = None,
    ) -> list[SearchResultItem]:
        """Perform hybrid or single-mode retrieval within a knowledge base.

        Args:
            db: Async SQLAlchemy database session.
            kb_id: Target knowledge base UUID.
            query: User's search query string.
            top_k: Maximum number of ranked results to return.
            mode: "hybrid" (dense+sparse), "vector" (dense only), or "fts" (sparse only).
            vector_weight: Multiplier for vector branch in RRF.
            fts_weight: Multiplier for full-text search branch in RRF.
            rrf_k: Smoothing constant for Reciprocal Rank Fusion (standard 60).
            api_key: Optional OpenAI API key for embedding generation.

        Returns:
            Ranked list of `SearchResultItem` records.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Pure Vector Mode
        if mode == "vector":
            vector_results = await self._vector_search(
                db=db,
                kb_id=kb_id,
                query=clean_query,
                limit=top_k,
                api_key=api_key,
            )
            return [
                self._build_result_item(
                    chunk=chunk,
                    filename=filename,
                    score=round(score, 4),
                    source="vector",
                )
                for chunk, filename, score in vector_results
            ]

        # 2. Pure Full-Text Search Mode
        if mode == "fts":
            fts_results = await self._fts_search(
                db=db,
                kb_id=kb_id,
                query=clean_query,
                limit=top_k,
            )
            return [
                self._build_result_item(
                    chunk=chunk,
                    filename=filename,
                    score=round(score, 4),
                    source="fts",
                )
                for chunk, filename, score in fts_results
            ]

        # 3. Hybrid Search Mode (RRF Fusion)
        candidate_limit = max(top_k * 2, 10)

        vector_results = await self._vector_search(
            db=db,
            kb_id=kb_id,
            query=clean_query,
            limit=candidate_limit,
            api_key=api_key,
        )

        fts_results = await self._fts_search(
            db=db,
            kb_id=kb_id,
            query=clean_query,
            limit=candidate_limit,
        )

        fused_results = self._reciprocal_rank_fusion(
            vector_results=vector_results,
            fts_results=fts_results,
            k=rrf_k,
            top_k=top_k,
            vector_weight=vector_weight,
            fts_weight=fts_weight,
        )

        logger.info(
            "hybrid_retrieval_completed",
            kb_id=str(kb_id),
            query=clean_query,
            vector_hits=len(vector_results),
            fts_hits=len(fts_results),
            fused_hits=len(fused_results),
        )

        return fused_results

    async def _vector_search(
        self,
        db: AsyncSession,
        kb_id: UUID,
        query: str,
        limit: int,
        api_key: str | None = None,
    ) -> list[tuple[RAGChunk, str, float]]:
        """Search by cosine distance using pgvector HNSW index."""
        try:
            query_vector = await self.embedder.embed_query(query, api_key=api_key)
        except Exception as exc:
            logger.warning("vector_search_embed_failed", error=str(exc))
            return []

        distance_col = RAGChunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(
                RAGChunk,
                RAGDocument.filename,
                distance_col.label("distance"),
            )
            .join(RAGDocument, RAGChunk.document_id == RAGDocument.id)
            .where(RAGChunk.kb_id == kb_id)
            .order_by(distance_col.asc())
            .limit(limit)
        )

        result = await db.execute(stmt)
        rows = result.all()

        results: list[tuple[RAGChunk, str, float]] = []
        for chunk, filename, distance in rows:
            # Cosine similarity = 1 - cosine distance, bounded in [0.0, 1.0]
            similarity = max(0.0, min(1.0, 1.0 - float(distance)))
            results.append((chunk, filename, similarity))

        return results

    async def _fts_search(
        self,
        db: AsyncSession,
        kb_id: UUID,
        query: str,
        limit: int,
    ) -> list[tuple[RAGChunk, str, float]]:
        """Search using PostgreSQL full-text search with plainto_tsquery."""
        ts_vector = func.to_tsvector("simple", RAGChunk.content)
        ts_query = func.plainto_tsquery("simple", query)
        rank_col = func.ts_rank(ts_vector, ts_query)

        stmt = (
            select(
                RAGChunk,
                RAGDocument.filename,
                rank_col.label("rank"),
            )
            .join(RAGDocument, RAGChunk.document_id == RAGDocument.id)
            .where(RAGChunk.kb_id == kb_id, ts_vector.op("@@")(ts_query))
            .order_by(rank_col.desc())
            .limit(limit)
        )

        result = await db.execute(stmt)
        rows = result.all()

        results: list[tuple[RAGChunk, str, float]] = []
        for chunk, filename, rank in rows:
            results.append((chunk, filename, float(rank)))

        return results

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[tuple[RAGChunk, str, float]],
        fts_results: list[tuple[RAGChunk, str, float]],
        k: int,
        top_k: int,
        vector_weight: float = 1.0,
        fts_weight: float = 1.0,
    ) -> list[SearchResultItem]:
        """Combine dense and sparse result lists using Reciprocal Rank Fusion."""
        chunk_map: dict[UUID, tuple[RAGChunk, str]] = {}
        rrf_scores: dict[UUID, float] = {}
        hit_sources: dict[UUID, set[str]] = {}

        # 1. Process Vector ranks (rank starts at 1)
        for rank_idx, (chunk, filename, _) in enumerate(vector_results, start=1):
            cid = chunk.id
            chunk_map[cid] = (chunk, filename)
            score = vector_weight / (k + rank_idx)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score
            hit_sources.setdefault(cid, set()).add("vector")

        # 2. Process FTS ranks (rank starts at 1)
        for rank_idx, (chunk, filename, _) in enumerate(fts_results, start=1):
            cid = chunk.id
            chunk_map[cid] = (chunk, filename)
            score = fts_weight / (k + rank_idx)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + score
            hit_sources.setdefault(cid, set()).add("fts")

        if not rrf_scores:
            return []

        # 3. Sort by aggregated RRF score descending
        sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

        final_items: list[SearchResultItem] = []
        for cid in sorted_ids[:top_k]:
            chunk, filename = chunk_map[cid]
            sources = hit_sources[cid]
            source_tag: Literal["hybrid", "vector", "fts"] = (
                "hybrid" if len(sources) > 1 else list(sources)[0]  # type: ignore[assignment]
            )

            final_items.append(
                self._build_result_item(
                    chunk=chunk,
                    filename=filename,
                    score=round(rrf_scores[cid], 5),
                    source=source_tag,
                )
            )

        return final_items

    @staticmethod
    def _build_result_item(
        chunk: RAGChunk,
        filename: str,
        score: float,
        source: Literal["hybrid", "vector", "fts"],
    ) -> SearchResultItem:
        """Helper to construct SearchResultItem from chunk and score."""
        return SearchResultItem(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            filename=filename,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=score,
            retrieval_source=source,
            metadata=getattr(chunk, "metadata_", {}) or {},
        )
