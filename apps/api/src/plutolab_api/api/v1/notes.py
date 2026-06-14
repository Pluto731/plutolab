"""Notes CRUD endpoints (Phase 3.1).

用户隔离: 所有 query 强制 `Note.user_id == current_user.id`.
不存在 / 不属于当前用户一律返 404 (不返 403, 避免暴露 UUID 是否存在).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.logging import get_logger
from plutolab_api.core.sample_note import create_sample_note
from plutolab_api.db.deps import get_db
from plutolab_api.models.note import Note
from plutolab_api.schemas.note import (
    NoteCreate,
    NotePublic,
    NoteSummary,
    NoteUpdate,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/notes", tags=["notes"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

EXCERPT_LEN = 160


def _to_summary(note: Note) -> NoteSummary:
    return NoteSummary(
        id=note.id,
        title=note.title,
        excerpt=note.content[:EXCERPT_LEN],
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


async def _get_owned(db: AsyncSession, note_id: UUID, user_id: UUID) -> Note:
    note = await db.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.get("", response_model=list[NoteSummary])
async def list_notes(user: CurrentUser, db: DbSession) -> list[NoteSummary]:
    result = await db.scalars(
        select(Note)
        .where(Note.user_id == user.id)
        .order_by(Note.updated_at.desc())
    )
    return [_to_summary(n) for n in result.all()]


@router.post("/sample", response_model=NotePublic, status_code=status.HTTP_201_CREATED)
async def create_sample(user: CurrentUser, db: DbSession) -> Note:
    """注册时已自动写一条; 此端点给"删了想再要"或老用户的兜底入口."""
    note = await create_sample_note(db, user.id)
    logger.info("plutolab.note.sample_created", user_id=str(user.id), note_id=str(note.id))
    return note


@router.post("", response_model=NotePublic, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: NoteCreate, user: CurrentUser, db: DbSession
) -> Note:
    note = Note(user_id=user.id, title=body.title, content=body.content)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    logger.info("plutolab.note.created", user_id=str(user.id), note_id=str(note.id))
    return note


@router.get("/{note_id}", response_model=NotePublic)
async def get_note(note_id: UUID, user: CurrentUser, db: DbSession) -> Note:
    return await _get_owned(db, note_id, user.id)


@router.patch("/{note_id}", response_model=NotePublic)
async def update_note(
    note_id: UUID, body: NoteUpdate, user: CurrentUser, db: DbSession
) -> Note:
    note = await _get_owned(db, note_id, user.id)
    # 只更显式传的字段, None 表示不动 (区别于"清空" — 标题不可清空, 正文清空靠传 "")
    if body.title is not None:
        note.title = body.title
    if body.content is not None:
        note.content = body.content
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: UUID, user: CurrentUser, db: DbSession) -> None:
    note = await _get_owned(db, note_id, user.id)
    await db.delete(note)
    await db.commit()
    logger.info("plutolab.note.deleted", user_id=str(user.id), note_id=str(note_id))
