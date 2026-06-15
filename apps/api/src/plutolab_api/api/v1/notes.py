"""Notes CRUD endpoints (Phase 3.1 + B.1 hashtag).

用户隔离: 所有 query 强制 `Note.user_id == current_user.id`.
不存在 / 不属于当前用户一律返 404 (不返 403, 避免暴露 UUID 是否存在).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.hashtags import extract_hashtags
from plutolab_api.core.logging import get_logger
from plutolab_api.core.sample_note import create_sample_note
from plutolab_api.db.deps import get_db
from plutolab_api.models.note import Note
from plutolab_api.schemas.note import (
    NoteCreate,
    NotePublic,
    NoteSummary,
    NoteUpdate,
    TagWithCount,
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
        tags=note.tags or [],
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


async def _get_owned(db: AsyncSession, note_id: UUID, user_id: UUID) -> Note:
    note = await db.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


@router.get("", response_model=list[NoteSummary])
async def list_notes(
    user: CurrentUser,
    db: DbSession,
    tag: Annotated[str | None, Query(description="过滤指定 hashtag (大小写不敏感)")] = None,
) -> list[NoteSummary]:
    stmt = select(Note).where(Note.user_id == user.id)
    if tag:
        # Note.tags 是 ARRAY(String), 用 unnest + lower 做大小写不敏感匹配
        # SQLAlchemy postgres ARRAY 没原生 case-insensitive any, 用 raw any 数组 lowercase 比较
        # 简单做法: 在 SQL 里 LOWER(tag) = LOWER(:tag) 用 array_to_string 或 unnest
        # 但 array 'lower' 直接 select: WHERE :tag = ANY(SELECT LOWER(t) FROM UNNEST(notes.tags) t)
        # SQLAlchemy 表达式: 用 func.lower + Note.tags 整体不易. 退而求其次: 业务里把入库 tags
        # 先 lower-case 存. 但这丢失原始大小写显示. 折中: 入库存原始, 查询时遍历用户笔记内存过滤.
        # 由于单用户笔记量不会很大 (<10k), 这是可接受的做法.
        target = tag.strip().lower()
        result = await db.scalars(stmt.order_by(Note.updated_at.desc()))
        notes = [
            n
            for n in result.all()
            if any(t.lower() == target for t in (n.tags or []))
        ]
        return [_to_summary(n) for n in notes]
    result = await db.scalars(stmt.order_by(Note.updated_at.desc()))
    return [_to_summary(n) for n in result.all()]


@router.get("/search", response_model=list[NoteSummary])
async def search_notes(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=200, description="关键字 (匹配 title + content)")],
) -> list[NoteSummary]:
    """简单 ILIKE 跨笔记全文搜索. 后续可升级 PG tsvector + GIN."""
    pattern = f"%{q.strip()}%"
    stmt = (
        select(Note)
        .where(
            Note.user_id == user.id,
            (Note.title.ilike(pattern)) | (Note.content.ilike(pattern)),
        )
        .order_by(Note.updated_at.desc())
    )
    result = await db.scalars(stmt)
    return [_to_summary(n) for n in result.all()]


_LIST_TAGS_SQL = text(
    """
    SELECT MIN(t) AS name, COUNT(*) AS count
    FROM notes n, UNNEST(n.tags) t
    WHERE n.user_id = :user_id
    GROUP BY LOWER(t)
    ORDER BY COUNT(*) DESC, MIN(t)
    """
)


@router.get("/tags", response_model=list[TagWithCount])
async def list_tags(user: CurrentUser, db: DbSession) -> list[TagWithCount]:
    """该用户所有 hashtag + 笔记计数, 按计数降序, 同计数按标签字典序.

    Postgres 不允许 unnest() 直接在 SELECT 列里, 用 FROM ... UNNEST(...) lateral join,
    再 GROUP BY LOWER(t) 大小写不敏感聚合; MIN(t) 拿首次出现的原始大小写形式.
    """
    result = await db.execute(_LIST_TAGS_SQL, {"user_id": user.id})
    return [TagWithCount(name=row.name, count=row.count) for row in result.all()]


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
    note = Note(
        user_id=user.id,
        title=body.title,
        content=body.content,
        tags=extract_hashtags(body.content),
    )
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
    if body.title is not None:
        note.title = body.title
    if body.content is not None:
        note.content = body.content
        # content 变化时重新解析 hashtag
        note.tags = extract_hashtags(body.content)
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: UUID, user: CurrentUser, db: DbSession) -> None:
    note = await _get_owned(db, note_id, user.id)
    await db.delete(note)
    await db.commit()
    logger.info("plutolab.note.deleted", user_id=str(user.id), note_id=str(note_id))
