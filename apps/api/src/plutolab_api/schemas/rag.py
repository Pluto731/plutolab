"""Pydantic v2 schemas for RAG (Phase 4.1.c).

Defines strongly-typed data transfer objects for:
- Knowledge base management (Create, Update, Public, Summary)
- Document ingestion & status tracking
- Semantic chunks with vector metadata
- Multi-turn conversation sessions & messages
- Structured citations & hybrid search retrieval results
- SSE streaming deltas & Agentic query rewriting
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- Enums / Literals ---

DocumentStatus = Literal["pending", "parsing", "ready", "failed"]
DocumentFileType = Literal["md", "pdf", "docx", "txt", "note"]
DocumentSourceType = Literal["upload", "note"]
MessageRole = Literal["user", "assistant", "system"]
RetrievalSource = Literal["vector", "fts", "hybrid"]


# --- Citation & Retrieval Schemas ---


class CitationItem(BaseModel):
    """Structured citation item for provenance display and drawer highlights."""

    document_id: UUID
    chunk_id: UUID
    filename: str
    chunk_index: int
    content: str
    similarity: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class SearchResultItem(BaseModel):
    """Retrieved chunk result from vector, FTS, or hybrid RRF search."""

    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    content: str
    score: float
    retrieval_source: RetrievalSource = "hybrid"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


# --- Knowledge Base Schemas ---


class KnowledgeBaseCreate(BaseModel):
    """Request payload for creating a knowledge base."""

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    icon: str = Field(default="folder", max_length=30)


class KnowledgeBaseUpdate(BaseModel):
    """Request payload for partial update of a knowledge base."""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    icon: str | None = Field(default=None, max_length=30)


class KnowledgeBasePublic(BaseModel):
    """Full detail view of a knowledge base."""

    id: UUID
    user_id: UUID
    title: str
    description: str
    icon: str
    doc_count: int = 0
    char_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseSummary(BaseModel):
    """Card item view for knowledge base list grid."""

    id: UUID
    title: str
    description: str
    icon: str
    doc_count: int = 0
    char_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Document Schemas ---


class DocumentImportNoteRequest(BaseModel):
    """Request payload to import existing user notes into a knowledge base."""

    note_ids: list[UUID] = Field(min_length=1, max_length=50)


class DocumentPublic(BaseModel):
    """Public document entity with ingestion status."""

    id: UUID
    kb_id: UUID
    filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    error_msg: str | None = None
    char_count: int
    chunk_count: int
    source_type: DocumentSourceType
    source_note_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Chunk Schemas ---


class ChunkPublic(BaseModel):
    """Public representation of an embedded chunk snippet."""

    id: UUID
    document_id: UUID
    kb_id: UUID
    chunk_index: int
    content: str
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _map_orm_metadata(cls, data: Any) -> Any:
        """Seamlessly map SQLAlchemy model's `metadata_` attribute to `metadata`."""
        if hasattr(data, "metadata_"):
            return {
                "id": getattr(data, "id"),
                "document_id": getattr(data, "document_id"),
                "kb_id": getattr(data, "kb_id"),
                "chunk_index": getattr(data, "chunk_index"),
                "content": getattr(data, "content"),
                "token_count": getattr(data, "token_count"),
                "metadata": getattr(data, "metadata_", {}) or {},
                "created_at": getattr(data, "created_at"),
            }
        if isinstance(data, dict) and "metadata_" in data and "metadata" not in data:
            data["metadata"] = data.pop("metadata_")
        return data


# --- Conversation & Message Schemas ---


class ConversationCreate(BaseModel):
    """Request payload to initiate a new RAG conversation."""

    title: str = Field(default="新对话", max_length=150)


class ConversationUpdate(BaseModel):
    """Request payload to rename a conversation."""

    title: str = Field(min_length=1, max_length=150)


class MessageCreate(BaseModel):
    """Request payload for sending a user question in RAG chat."""

    content: str = Field(min_length=1, max_length=100_000)
    model: str | None = Field(default="gpt-4o-mini", max_length=50)
    stream: bool = Field(default=True)
    top_k: int = Field(default=5, ge=1, le=20)
    hybrid_search: bool = Field(default=True)


class MessagePublic(BaseModel):
    """Public chat message item with citations."""

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    citations: list[CitationItem] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationPublic(BaseModel):
    """Full conversation with ordered message history."""

    id: UUID
    kb_id: UUID
    title: str
    messages: list[MessagePublic] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationSummary(BaseModel):
    """Conversation list item for side navigation history tree."""

    id: UUID
    kb_id: UUID
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Streaming & Agentic RAG Schemas ---


class ChatStreamChunk(BaseModel):
    """SSE streaming data chunk payload."""

    delta: str = ""
    citation: CitationItem | None = None
    finish_reason: str | None = None


class ChatQueryRewrite(BaseModel):
    """Agentic RAG query rewriting result for hybrid and sub-query dispatch."""

    original_query: str
    rewritten_query: str
    sub_queries: list[str] = Field(default_factory=list)
