"""RAG API routes (Phase 4.3.b).

Includes:
- Knowledge base CRUD (Create, Read, Update, Delete with cascade)
- Multi-file asynchronous upload & background parsing/chunking/embedding
- Single-click note import from Phase 3.1 Notes
- Document status polling & deletion
- Unified Hybrid Retrieval endpoint (Vector + FTS + RRF)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.logging import get_logger
from plutolab_api.db.deps import get_db
from plutolab_api.models.note import Note
from plutolab_api.models.rag import RAGDocument, RAGKnowledgeBase
from plutolab_api.schemas.rag import (
    DocumentImportNoteRequest,
    DocumentPublic,
    KnowledgeBaseCreate,
    KnowledgeBasePublic,
    KnowledgeBaseSummary,
    KnowledgeBaseUpdate,
    SearchResultItem,
)
from plutolab_api.services.embedder import EmbeddingService
from plutolab_api.services.ingestion import DocumentIngestionService
from plutolab_api.services.retriever import HybridRetriever, SearchMode

logger = get_logger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])
DbSession = Annotated[AsyncSession, Depends(get_db)]

ALLOWED_EXTENSIONS = {"md", "txt", "pdf", "docx"}


class SearchRequest(BaseModel):
    """Payload for knowledge base semantic & lexical search."""

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    mode: SearchMode = Field(default="hybrid")
    vector_weight: float = Field(default=1.0, ge=0.0)
    fts_weight: float = Field(default=1.0, ge=0.0)


async def _get_owned_kb(db: AsyncSession, kb_id: UUID, user_id: UUID) -> RAGKnowledgeBase:
    """Fetch knowledge base and ensure it belongs to the authenticated user."""
    kb = await db.get(RAGKnowledgeBase, kb_id)
    if kb is None or kb.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


# --- Knowledge Base CRUD Endpoints ---


@router.post(
    "/knowledge-bases",
    response_model=KnowledgeBasePublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_base(
    user: CurrentUser,
    db: DbSession,
    payload: KnowledgeBaseCreate,
) -> KnowledgeBasePublic:
    """Create a new knowledge base container."""
    kb = RAGKnowledgeBase(
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        icon=payload.icon,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)

    return KnowledgeBasePublic(
        id=kb.id,
        user_id=kb.user_id,
        title=kb.title,
        description=kb.description,
        icon=kb.icon,
        doc_count=0,
        char_count=0,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.get(
    "/knowledge-bases",
    response_model=list[KnowledgeBaseSummary],
)
async def list_knowledge_bases(
    user: CurrentUser,
    db: DbSession,
) -> list[KnowledgeBaseSummary]:
    """List all knowledge bases belonging to the user with aggregated statistics."""
    # Query KBs with left join aggregation for document and character counts
    stmt = (
        select(
            RAGKnowledgeBase,
            func.coalesce(func.count(RAGDocument.id), 0).label("doc_count"),
            func.coalesce(func.sum(RAGDocument.char_count), 0).label("char_count"),
        )
        .outerjoin(RAGDocument, RAGKnowledgeBase.id == RAGDocument.kb_id)
        .where(RAGKnowledgeBase.user_id == user.id)
        .group_by(RAGKnowledgeBase.id)
        .order_by(RAGKnowledgeBase.created_at.desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    summaries: list[KnowledgeBaseSummary] = []
    for kb, doc_count, char_count in rows:
        summaries.append(
            KnowledgeBaseSummary(
                id=kb.id,
                title=kb.title,
                description=kb.description,
                icon=kb.icon,
                doc_count=int(doc_count),
                char_count=int(char_count),
                created_at=kb.created_at,
                updated_at=kb.updated_at,
            )
        )
    return summaries


@router.get(
    "/knowledge-bases/{kb_id}",
    response_model=KnowledgeBasePublic,
)
async def get_knowledge_base(
    kb_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> KnowledgeBasePublic:
    """Get detailed knowledge base info including counts."""
    kb = await _get_owned_kb(db, kb_id, user.id)

    # Compute stats
    stats_stmt = select(
        func.coalesce(func.count(RAGDocument.id), 0),
        func.coalesce(func.sum(RAGDocument.char_count), 0),
    ).where(RAGDocument.kb_id == kb_id)
    stats_res = await db.execute(stats_stmt)
    doc_count, char_count = stats_res.one()

    return KnowledgeBasePublic(
        id=kb.id,
        user_id=kb.user_id,
        title=kb.title,
        description=kb.description,
        icon=kb.icon,
        doc_count=int(doc_count),
        char_count=int(char_count),
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.patch(
    "/knowledge-bases/{kb_id}",
    response_model=KnowledgeBasePublic,
)
async def update_knowledge_base(
    kb_id: UUID,
    user: CurrentUser,
    db: DbSession,
    payload: KnowledgeBaseUpdate,
) -> KnowledgeBasePublic:
    """Partially update a knowledge base title, description, or icon."""
    kb = await _get_owned_kb(db, kb_id, user.id)

    if payload.title is not None:
        kb.title = payload.title
    if payload.description is not None:
        kb.description = payload.description
    if payload.icon is not None:
        kb.icon = payload.icon

    await db.commit()
    await db.refresh(kb)

    # Fetch stats
    stats_stmt = select(
        func.coalesce(func.count(RAGDocument.id), 0),
        func.coalesce(func.sum(RAGDocument.char_count), 0),
    ).where(RAGDocument.kb_id == kb_id)
    stats_res = await db.execute(stats_stmt)
    doc_count, char_count = stats_res.one()

    return KnowledgeBasePublic(
        id=kb.id,
        user_id=kb.user_id,
        title=kb.title,
        description=kb.description,
        icon=kb.icon,
        doc_count=int(doc_count),
        char_count=int(char_count),
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.delete(
    "/knowledge-bases/{kb_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_knowledge_base(
    kb_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete knowledge base and cascade delete all documents, chunks, and sessions."""
    kb = await _get_owned_kb(db, kb_id, user.id)
    await db.delete(kb)
    await db.commit()


# --- Document Upload & Management Endpoints ---


@router.post(
    "/knowledge-bases/{kb_id}/documents/upload",
    response_model=list[DocumentPublic],
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_documents(
    kb_id: UUID,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> list[DocumentPublic]:
    """Upload one or more documents (md, txt, pdf, docx) and trigger background ingestion."""
    await _get_owned_kb(db, kb_id, user.id)

    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No files provided")

    created_docs: list[DocumentPublic] = []
    ingestion_service = DocumentIngestionService()

    for upload_file in files:
        filename = upload_file.filename or "untitled.txt"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail=f"File format '.{ext}' not supported. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        content = await upload_file.read()
        file_size = len(content)

        doc = RAGDocument(
            kb_id=kb_id,
            user_id=user.id,
            filename=filename,
            file_type=ext,
            file_size=file_size,
            status="pending",
            source_type="upload",
        )
        db.add(doc)
        await db.flush()

        # Enqueue async background parsing and embedding pipeline
        background_tasks.add_task(
            ingestion_service.process_document,
            doc_id=doc.id,
            content=content,
            filename=filename,
            file_type=ext,
            kb_id=kb_id,
            user_id=user.id,
            session=db,
        )

        created_docs.append(DocumentPublic.model_validate(doc))

    await db.commit()
    return created_docs


@router.post(
    "/knowledge-bases/{kb_id}/documents/import-notes",
    response_model=list[DocumentPublic],
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_notes_to_knowledge_base(
    kb_id: UUID,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    payload: DocumentImportNoteRequest,
) -> list[DocumentPublic]:
    """Import existing Phase 3.1 user notes into this knowledge base."""
    await _get_owned_kb(db, kb_id, user.id)

    # Fetch notes belonging to the user
    stmt = select(Note).where(Note.user_id == user.id, Note.id.in_(payload.note_ids))
    result = await db.execute(stmt)
    notes = result.scalars().all()

    if not notes:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="No matching notes found for current user"
        )

    created_docs: list[DocumentPublic] = []
    ingestion_service = DocumentIngestionService()

    for note in notes:
        content_bytes = note.content.encode("utf-8")
        filename = f"{note.title}.md"

        doc = RAGDocument(
            kb_id=kb_id,
            user_id=user.id,
            filename=filename,
            file_type="note",
            file_size=len(content_bytes),
            status="pending",
            source_type="note",
            source_note_id=note.id,
        )
        db.add(doc)
        await db.flush()

        background_tasks.add_task(
            ingestion_service.process_document,
            doc_id=doc.id,
            content=content_bytes,
            filename=filename,
            file_type="note",
            kb_id=kb_id,
            user_id=user.id,
            session=db,
        )

        created_docs.append(DocumentPublic.model_validate(doc))

    await db.commit()
    return created_docs


@router.get(
    "/knowledge-bases/{kb_id}/documents",
    response_model=list[DocumentPublic],
)
async def list_documents(
    kb_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> list[DocumentPublic]:
    """List all documents in the knowledge base with their parsing statuses."""
    await _get_owned_kb(db, kb_id, user.id)

    stmt = (
        select(RAGDocument)
        .where(RAGDocument.kb_id == kb_id)
        .order_by(RAGDocument.created_at.desc())
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [DocumentPublic.model_validate(d) for d in docs]


@router.get(
    "/knowledge-bases/{kb_id}/documents/{doc_id}",
    response_model=DocumentPublic,
)
async def get_document(
    kb_id: UUID,
    doc_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> DocumentPublic:
    """Get single document detail and current ingestion status."""
    await _get_owned_kb(db, kb_id, user.id)

    doc = await db.get(RAGDocument, doc_id)
    if not doc or doc.kb_id != kb_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")

    return DocumentPublic.model_validate(doc)


@router.delete(
    "/knowledge-bases/{kb_id}/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    kb_id: UUID,
    doc_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    """Delete a document and cascade remove all its indexed chunks."""
    await _get_owned_kb(db, kb_id, user.id)

    doc = await db.get(RAGDocument, doc_id)
    if not doc or doc.kb_id != kb_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")

    await db.delete(doc)
    await db.commit()


# --- Hybrid Retrieval Endpoint ---


@router.post(
    "/knowledge-bases/{kb_id}/search",
    response_model=list[SearchResultItem],
)
async def search_knowledge_base(
    kb_id: UUID,
    user: CurrentUser,
    db: DbSession,
    payload: SearchRequest,
) -> list[SearchResultItem]:
    """Execute hybrid (Vector + FTS + RRF) search within the knowledge base."""
    await _get_owned_kb(db, kb_id, user.id)

    # Optional: fetch user's decrypted OpenAI Key
    embedder = EmbeddingService()
    user_api_key = await embedder.get_user_openai_key(db, user.id)

    retriever = HybridRetriever(embedder=embedder)
    results = await retriever.search(
        db=db,
        kb_id=kb_id,
        query=payload.query,
        top_k=payload.top_k,
        mode=payload.mode,
        vector_weight=payload.vector_weight,
        fts_weight=payload.fts_weight,
        api_key=user_api_key,
    )
    return results
