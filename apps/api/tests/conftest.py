"""Test fixtures: a dedicated `pluto_test` database + per-test rollback isolation.

The test DB is created on first run. Each test gets an AsyncSession wrapped in an
outer transaction that is rolled back on teardown; endpoint-level commits stay
isolated via savepoints (join_transaction_mode="create_savepoint").
"""

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

import plutolab_api.models.note  # noqa: F401  (register on Base.metadata)
import plutolab_api.models.task  # noqa: F401  (register on Base.metadata)
import plutolab_api.models.user  # (register on Base.metadata; referenced elsewhere)
import plutolab_api.models.user_api_key  # noqa: F401  (register on Base.metadata)
from plutolab_api.api.deps import get_db
from plutolab_api.core.config import settings
from plutolab_api.core.email import Mailer, get_mailer
from plutolab_api.core.redis import get_redis
from plutolab_api.db.base import Base
from plutolab_api.main import app

TEST_DB_NAME = "pluto_test"


class FakeMailer(Mailer):
    """Test double — records sends instead of hitting SMTP.

    Use `.reset_emails` / `.verify_emails` to assert on a specific kind
    without worrying about other emails the flow happens to trigger
    (e.g. register now sends a verification email)."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    @property
    def reset_emails(self) -> list[dict[str, object]]:
        return [s for s in self.sent if s.get("kind") == "reset"]

    @property
    def verify_emails(self) -> list[dict[str, object]]:
        return [s for s in self.sent if s.get("kind") == "verify"]

    @property
    def code_emails(self) -> list[dict[str, object]]:
        return [s for s in self.sent if s.get("kind") == "code"]

    async def send(self, to, subject, html_body, text_body):
        # 兜底; 我们的接口只走 send_password_reset / send_email_verification.
        self.sent.append({"kind": "raw", "to": to, "subject": subject})

    async def send_password_reset(self, to, reset_url, ttl_minutes):
        self.sent.append(
            {"kind": "reset", "to": to, "reset_url": reset_url, "ttl_minutes": ttl_minutes}
        )

    async def send_email_verification(self, to, verify_url, ttl_hours):
        self.sent.append(
            {"kind": "verify", "to": to, "verify_url": verify_url, "ttl_hours": ttl_hours}
        )

    async def send_password_reset_code(self, to, code, ttl_minutes):
        self.sent.append(
            {"kind": "code", "to": to, "code": code, "ttl_minutes": ttl_minutes}
        )


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
async def fake_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


@pytest_asyncio.fixture
async def fake_mailer() -> FakeMailer:
    return FakeMailer()


@pytest_asyncio.fixture(autouse=True)
def _disable_onboarding_sample_note(monkeypatch) -> None:
    """关掉注册时自动写入示例笔记 — 保持"新用户 0 笔记"测试前提."""
    monkeypatch.setattr(settings, "onboarding_sample_note", False)


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    fake_redis: fakeredis.aioredis.FakeRedis,
    fake_mailer: FakeMailer,
) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_mailer] = lambda: fake_mailer
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
