"""Shared pytest fixtures."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.db.session import AsyncSessionLocal


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Per-test session wrapped in a SAVEPOINT that rolls back at teardown.

    Keeps tests isolated without truncating tables. Requires a running DB.
    """
    async with AsyncSessionLocal() as session:
        await session.begin_nested()
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()
