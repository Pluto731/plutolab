"""FastAPI dependency: yields an AsyncSession scoped to the request."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.db.session import AsyncSessionLocal


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
