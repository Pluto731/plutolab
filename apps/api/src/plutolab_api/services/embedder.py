"""Vector embedding service for RAG ingestion and retrieval (Phase 4.2.c).

Features:
- Decrypts user's stored OpenAI API keys using Fernet symmetric cryptography (Phase 2.5).
- Batched remote vector generation via OpenAI text-embedding-3-small (1536 dimensions).
- Deterministic L2-normalized MockEmbedder fallback for testing and keyless offline development.
"""

import hashlib
import math
import random
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.crypto import decrypt
from plutolab_api.core.logging import get_logger
from plutolab_api.models.user_api_key import UserApiKey

logger = get_logger(__name__)

EMBEDDING_DIM = 1536
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class EmbeddingError(Exception):
    """Domain exception raised when vector embedding generation fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class _EmbeddingItem(BaseModel):
    model_config = ConfigDict(strict=True, allow_inf_nan=False)

    index: int = Field(ge=0)
    embedding: list[float] = Field(min_length=EMBEDDING_DIM, max_length=EMBEDDING_DIM)


class _EmbeddingResponse(BaseModel):
    data: list[_EmbeddingItem]


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

        if batch_size < 1:
            raise EmbeddingError("Embedding batch size must be positive.")

        # If no API key provided, evaluate mock fallback
        if not api_key:
            if mock_fallback:
                logger.info("embedding_mock_fallback_used", count=len(texts))
                return [generate_mock_vector(t) for t in texts]
            raise EmbeddingError(
                "OpenAI API key is required but not provided or configured in user settings."
            )

        # Provider failures must never switch an existing corpus to mock vectors.
        return await self._embed_remote(texts, api_key, model, batch_size)

    async def _embed_remote(
        self, texts: list[str], api_key: str, model: str, batch_size: int
    ) -> list[list[float]]:
        """Generate and validate provider vectors without a mock fallback path."""
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
                        "Network error while calling OpenAI embeddings. Please try again.", exc
                    ) from exc

                if resp.status_code == 401:
                    raise EmbeddingError("Invalid OpenAI API key. Authentication failed.")
                elif resp.status_code == 429:
                    raise EmbeddingError(
                        "OpenAI API rate limit or quota exceeded. Please check your billing/limits."
                    )
                elif resp.status_code != 200:
                    raise EmbeddingError(
                        f"OpenAI API returned error status {resp.status_code}. Please try again."
                    )

                try:
                    data = _EmbeddingResponse.model_validate_json(resp.content)
                except ValidationError as exc:
                    raise EmbeddingError(
                        "OpenAI returned an invalid embedding response.", exc
                    ) from exc
                sorted_data = sorted(data.data, key=lambda item: item.index)
                if [item.index for item in sorted_data] != list(range(len(batch))):
                    raise EmbeddingError(
                        "OpenAI returned an incomplete or duplicate embedding batch."
                    )
                if any(not any(item.embedding) for item in sorted_data):
                    raise EmbeddingError("OpenAI returned a zero embedding vector.")
                embeddings.extend(item.embedding for item in sorted_data)

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
            raise EmbeddingError("No embedding was returned for the query.")
        return results[0]
