"""Vector embedding service for RAG ingestion and retrieval (Phase 4.2.c).

Features:
- Decrypts user's stored OpenAI API keys using Fernet symmetric cryptography (Phase 2.5).
- Batched remote vector generation via OpenAI text-embedding-3-small (1536 dimensions).
- Deterministic L2-normalized MockEmbedder fallback for testing and keyless offline development.
"""

import hashlib
import math
import random
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from plutolab_api.core.crypto import decrypt
from plutolab_api.models.user_api_key import UserApiKey

logger = structlog.get_logger(__name__)

EMBEDDING_DIM = 1536
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class EmbeddingError(Exception):
    """Domain exception raised when vector embedding generation fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


def generate_mock_vector(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Generate a deterministic, L2-normalized mock vector based on SHA-256 hash.

    Same input text always produces the exact same unit vector (norm = 1.0).
    """
    if not text:
        text = "<empty>"

    # Use first 8 hex characters of SHA-256 hash as deterministic seed
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Sample standard Gaussian variables
    raw = [rng.gauss(0.0, 1.0) for _ in range(dim)]

    # Compute Euclidean (L2) norm
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0

    # Project to unit hypersphere
    return [round(x / norm, 6) for x in raw]


class EmbeddingService:
    """Service to handle embedding requests and user API key decryption."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client

    async def get_user_openai_key(self, db: AsyncSession, user_id: UUID) -> str | None:
        """Fetch and Fernet-decrypt the user's latest OpenAI API key from the database."""
        stmt = (
            select(UserApiKey)
            .where(UserApiKey.user_id == user_id, UserApiKey.provider == "openai")
            .order_by(UserApiKey.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        record = result.scalars().first()

        if not record:
            return None

        try:
            return decrypt(record.key_ciphertext)
        except Exception as exc:
            logger.error("failed_to_decrypt_user_api_key", user_id=str(user_id), error=str(exc))
            raise EmbeddingError("Failed to decrypt stored OpenAI API key.", exc) from exc

    async def embed_texts(
        self,
        texts: list[str],
        api_key: str | None = None,
        model: str = DEFAULT_EMBEDDING_MODEL,
        batch_size: int = 64,
        mock_fallback: bool = True,
    ) -> list[list[float]]:
        """Generate 1536-dimensional embeddings for a batch of text chunks.

        Args:
            texts: List of text strings to embed.
            api_key: Plaintext OpenAI API Key.
            model: OpenAI embedding model name.
            batch_size: Max chunks per remote request (default 64).
            mock_fallback: Whether to use deterministic mock if api_key is None.

        Returns:
            List of 1536-dimensional float vectors matching the order of input texts.
        """
        if not texts:
            return []

        # If no API key provided, evaluate mock fallback
        if not api_key:
            if mock_fallback:
                logger.info("embedding_mock_fallback_used", count=len(texts))
                return [generate_mock_vector(t) for t in texts]
            raise EmbeddingError(
                "OpenAI API key is required but not provided or configured in user settings."
            )

        embeddings: list[list[float]] = []
        client_provided = self._http_client is not None
        client = self._http_client or httpx.AsyncClient(timeout=30.0)

        try:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                # Replace newlines as recommended by OpenAI guide for text-embedding-3
                sanitized_batch = [t.replace("\n", " ").strip() or " " for t in batch]

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": model,
                    "input": sanitized_batch,
                }

                try:
                    resp = await client.post(OPENAI_EMBEDDINGS_URL, headers=headers, json=payload)
                except httpx.TimeoutException as exc:
                    raise EmbeddingError(
                        "OpenAI embedding request timed out. Please try again.", exc
                    ) from exc
                except httpx.RequestError as exc:
                    raise EmbeddingError(
                        f"Network error while calling OpenAI embeddings: {exc}", exc
                    ) from exc

                if resp.status_code == 401:
                    raise EmbeddingError("Invalid OpenAI API key. Authentication failed.")
                elif resp.status_code == 429:
                    raise EmbeddingError(
                        "OpenAI API rate limit or quota exceeded. Please check your billing/limits."
                    )
                elif resp.status_code != 200:
                    raise EmbeddingError(
                        f"OpenAI API returned error status {resp.status_code}: {resp.text}"
                    )

                data = resp.json()
                sorted_data = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                for item in sorted_data:
                    embeddings.append(item["embedding"])

        finally:
            if not client_provided:
                await client.aclose()

        return embeddings

    async def embed_query(
        self,
        query: str,
        api_key: str | None = None,
        model: str = DEFAULT_EMBEDDING_MODEL,
        mock_fallback: bool = True,
    ) -> list[float]:
        """Generate embedding vector for a single search query."""
        results = await self.embed_texts(
            [query],
            api_key=api_key,
            model=model,
            batch_size=1,
            mock_fallback=mock_fallback,
        )
        if not results:
            return generate_mock_vector(query)
        return results[0]
