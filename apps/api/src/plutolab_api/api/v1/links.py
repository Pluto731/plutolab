"""Links CRUD endpoints — Phase 3.3 链接收藏.

POST 时服务端抓 URL metadata. 失败 fallback (title=url 其他 None) 不挡保存.
用户隔离 + 404 防猜 UUID.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.api.deps import CurrentUser
from plutolab_api.core.link_metadata import fetch_url_metadata
from plutolab_api.core.logging import get_logger
from plutolab_api.db.deps import get_db
from plutolab_api.models.link import Link
from plutolab_api.schemas.link import LinkCreate, LinkPublic

logger = get_logger(__name__)

router = APIRouter(prefix="/links", tags=["links"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_owned(db: AsyncSession, link_id: UUID, user_id: UUID) -> Link:
    link = await db.get(Link, link_id)
    if link is None or link.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Link not found")
    return link


@router.get("", response_model=list[LinkPublic])
async def list_links(user: CurrentUser, db: DbSession) -> list[Link]:
    result = await db.scalars(
        select(Link)
        .where(Link.user_id == user.id)
        .order_by(Link.created_at.desc())
    )
    return list(result.all())


@router.post("", response_model=LinkPublic, status_code=status.HTTP_201_CREATED)
async def create_link(
    body: LinkCreate, user: CurrentUser, db: DbSession
) -> Link:
    url_str = str(body.url)
    meta = await fetch_url_metadata(url_str)
    link = Link(
        user_id=user.id,
        url=url_str,
        title=meta.title,
        description=meta.description,
        image_url=meta.image_url,
        favicon_url=meta.favicon_url,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    logger.info("plutolab.link.created", user_id=str(user.id), link_id=str(link.id), url=url_str)
    return link


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(link_id: UUID, user: CurrentUser, db: DbSession) -> None:
    link = await _get_owned(db, link_id, user.id)
    await db.delete(link)
    await db.commit()
    logger.info("plutolab.link.deleted", user_id=str(user.id), link_id=str(link_id))
