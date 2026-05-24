"""DB connectivity health check."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.db.deps import get_db

router = APIRouter()


class DbHealthResponse(BaseModel):
    status: str
    dialect: str
    server_version: str


@router.get("/db/health", response_model=DbHealthResponse, summary="DB connectivity check")
async def db_health(db: Annotated[AsyncSession, Depends(get_db)]) -> DbHealthResponse:
    result = await db.execute(text("SELECT version()"))
    version = result.scalar_one()
    return DbHealthResponse(
        status="ok",
        dialect=db.bind.dialect.name if db.bind else "unknown",
        server_version=version.split(",")[0],  # 取首句, 别带平台细节
    )
