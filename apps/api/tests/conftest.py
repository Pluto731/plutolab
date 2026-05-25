"""Test fixtures: a dedicated `pluto_test` database + per-test rollback isolation.

The test DB is created on first run. Each test gets an AsyncSession wrapped in an
outer transaction that is rolled back on teardown; endpoint-level commits stay
isolated via savepoints (join_transaction_mode="create_savepoint").
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

import plutolab_api.models.user  # noqa: F401  (register model on Base.metadata)
from plutolab_api.api.deps import get_db
from plutolab_api.core.config import settings
from plutolab_api.db.base import Base
from plutolab_api.main import app

TEST_DB_NAME = "pluto_test"


def _test_db_url() -> str:
    base, _, _name = settings.database_url.rpartition("/")
    return f"{base}/{TEST_DB_NAME}"


@pytest_asyncio.fixture(scope="session")
async def _ensure_test_db() -> None:
    admin = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB_NAME}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    await admin.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_engine(_ensure_test_db: None) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(_test_db_url())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    connection = await test_engine.connect()
    trans = await connection.begin()
    session = AsyncSession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
