"""Domain and real PostgreSQL migration checks in freshly created disposable databases.

Never uses the application's database or the shared pluto_test database. Only the
codex interpreter may run the Alembic subprocess. DB creation/deletion is restricted
to a loopback server and a UUID-named database created by this fixture itself.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from plutolab_api.core.config import settings
from plutolab_api.db.base import Base
from plutolab_api.models.review import ReviewSettings
from plutolab_api.models.user import User
from plutolab_api.services.review.settings import (
    ReviewAccessDeniedError,
    ReviewConflictError,
    ReviewRules,
    create_installation,
    create_settings,
    get_installation,
    get_settings,
    replace_rules,
    revoke_installation,
)

CODEX = Path("/opt/homebrew/Caskroom/miniconda/base/envs/codex/bin/python")
API_ROOT = Path(__file__).resolve().parents[1]
REVIEW_TABLES = {"github_installations", "review_settings"}


def migrate(url: URL, action: str, revision: str) -> None:
    assert Path(sys.executable).resolve() == CODEX.resolve(), "Use the dedicated codex Python"
    assert url.host in {"localhost", "127.0.0.1"} and url.port == 5432
    assert url.database is not None and url.database.startswith("plutolab_review_test_")
    env = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False)}
    with tempfile.NamedTemporaryFile(
        prefix="phase5-review-migration-", suffix=".log", delete=False
    ) as log:
        result = subprocess.run(
            [str(CODEX), "-m", "alembic", action, revision],
            cwd=API_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if result.returncode:
        tail = "\n".join(Path(log.name).read_text().splitlines()[-25:])
        # Do not include connection strings in test failure reports.
        if url.password:
            tail = tail.replace(url.password, "[REDACTED]")
        pytest.fail(f"Alembic {action} {revision}: exit {result.returncode}; {log.name}\n{tail}")


@asynccontextmanager
async def disposable_database() -> AsyncIterator[URL]:
    url = make_url(settings.database_url)
    if url.host not in {"localhost", "127.0.0.1"} or url.port != 5432:
        pytest.fail("Review migrations require loopback PostgreSQL on port 5432")
    name = f"plutolab_review_test_{uuid4().hex}"
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    created = False
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        yield url.set(database=name)
    finally:
        try:
            if created:
                # Only the exact database created above; no FORCE/terminate/drop of existing DBs.
                async with admin.connect() as conn:
                    await conn.execute(text(f'DROP DATABASE "{name}"'))
        finally:
            await admin.dispose()


@pytest_asyncio.fixture(scope="module")
async def review_engine() -> AsyncIterator[AsyncEngine]:
    async with disposable_database() as url:
        migrate(url, "upgrade", "head")
        engine = create_async_engine(url)
        try:
            yield engine
        finally:
            await engine.dispose()


@pytest_asyncio.fixture
async def review_db(review_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with review_engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
        await transaction.rollback()


@pytest_asyncio.fixture
async def owners(review_db: AsyncSession) -> tuple[User, User]:
    first = User(email=f"{uuid4()}@review.test")
    second = User(email=f"{uuid4()}@review.test")
    review_db.add_all([first, second])
    await review_db.flush()
    return first, second


@pytest.mark.parametrize(
    "rules",
    [
        {"min_pr_lines": 0},
        {"min_pr_lines": -1},
        {"min_pr_lines": True},
        {"min_pr_lines": "10"},
        {"min_pr_lines": 1.5},
        {"min_pr_lines": 2_147_483_648},
        {"enabled": "false"},
        {"enabled": 1},
        {"rules_version": 2},
        {"focus": []},
        {"focus": ["correctness"]},
        {"focus": ["security", "security"]},
        {"focus": ["security", "performance", "quality", "security"]},
        {"skip_paths": [""]},
        {"skip_paths": ["/etc/passwd"]},
        {"skip_paths": ["../secret"]},
        {"skip_paths": ["a/../b"]},
        {"skip_paths": ["a\\b"]},
        {"skip_paths": ["a\nb"]},
        {"skip_paths": ["a//b"]},
        {"skip_paths": ["./a"]},
        {"skip_paths": ["[abc]"]},
        {"skip_paths": ["{a,b}"]},
        {"skip_paths": ["!secret"]},
        {"skip_paths": ["https://a"]},
        {"skip_paths": ["a" * 257]},
        {"skip_paths": [str(i) for i in range(101)]},
        {"skip_paths": ["a", "a"]},
        {"skip_paths": [" a"]},
    ],
)
def test_invalid_rules(rules: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ReviewRules.model_validate(rules)


def test_valid_rule_boundaries() -> None:
    rules = ReviewRules(
        min_pr_lines=2_147_483_647, skip_paths=["src/**/*.py", "docs/?.md", "文档/*"]
    )
    assert rules.enabled is False
    assert rules.focus == ["security", "performance", "quality"]
    assert len(ReviewRules(skip_paths=[str(i) for i in range(100)]).skip_paths) == 100
    assert ReviewRules(skip_paths=["a" * 256]).skip_paths == ["a" * 256]


async def test_defaults_and_identity(review_db, owners):
    first, _ = owners
    await create_installation(review_db, first.id, "123")
    row = await create_settings(review_db, first.id, "123", "9007199254740993", "owner/repo")
    assert (row.enabled, row.min_pr_lines, row.rules_version) == (False, 1, 1)
    assert row.skip_paths == []
    assert row.focus == ["security", "performance", "quality"]
    assert row.repo_id == "9007199254740993"
    assert (await get_settings(review_db, first.id, "123", row.repo_id)).id == row.id
    # Verify database defaults independently of SQLAlchemy/Pydantic defaults.
    result = (
        await review_db.execute(
            text(
                "INSERT INTO review_settings (installation_id, owner_id, repo_id, repo_name) "
                "VALUES ('123', :owner, '456', 'owner/other') "
                "RETURNING enabled, min_pr_lines, rules_version, skip_paths, focus"
            ),
            {"owner": first.id},
        )
    ).one()
    assert tuple(result) == (False, 1, 1, [], ["security", "performance", "quality"])


async def test_uniqueness_and_session_survives_conflict(review_db, owners):
    first, second = owners
    await create_installation(review_db, first.id, "123")
    with pytest.raises(ReviewConflictError):
        await create_installation(review_db, second.id, "123")
    await create_settings(review_db, first.id, "123", "456", "owner/repo")
    with pytest.raises(ReviewConflictError):
        await create_settings(review_db, first.id, "123", "456", "renamed/repo")
    await create_installation(review_db, second.id, "124")
    other = await create_settings(review_db, second.id, "124", "456", "owner/repo")
    assert other.owner_id == second.id
    assert (await get_installation(review_db, first.id, "123")).owner_id == first.id


async def test_tenant_isolation(review_db, owners):
    first, second = owners
    await create_installation(review_db, first.id, "123")
    row = await create_settings(review_db, first.id, "123", "456", "owner/repo")
    operations = [
        lambda: get_installation(review_db, second.id, "123"),
        lambda: get_settings(review_db, second.id, "123", "456"),
        lambda: create_settings(review_db, second.id, "123", "457", "owner/other"),
        lambda: replace_rules(review_db, second.id, "123", "456", ReviewRules(enabled=True)),
        lambda: revoke_installation(review_db, second.id, "123"),
        lambda: get_settings(review_db, first.id, "123", "999"),
        lambda: get_installation(review_db, first.id, "999"),
    ]
    for operation in operations:
        with pytest.raises(ReviewAccessDeniedError):
            await operation()
    assert row.enabled is False and row.rules_version == 1
    assert (await get_installation(review_db, first.id, "123")).revoked_at is None
    # Composite FK also prevents mismatched owners if service logic is bypassed.
    with pytest.raises(IntegrityError):
        async with review_db.begin_nested():
            review_db.add(
                ReviewSettings(
                    installation_id="123",
                    owner_id=second.id,
                    repo_id="789",
                    repo_name="owner/other",
                )
            )
            await review_db.flush()


async def test_rule_versioning_revalidation_and_rollback(review_db, owners):
    first, _ = owners
    await create_installation(review_db, first.id, "123")
    row = await create_settings(review_db, first.id, "123", "456", "owner/repo")
    rules = ReviewRules(enabled=True, min_pr_lines=5, skip_paths=["docs/**"], focus=["quality"])
    await replace_rules(review_db, first.id, "123", "456", rules)
    assert row.rules_version == 2 and row.enabled
    await replace_rules(review_db, first.id, "123", "456", rules)
    assert row.rules_version == 2  # idempotent save
    rules.focus.append("quality")
    with pytest.raises(ValidationError):
        await replace_rules(review_db, first.id, "123", "456", rules)
    assert row.rules_version == 2
    savepoint = await review_db.begin_nested()
    await replace_rules(review_db, first.id, "123", "456", ReviewRules())
    await savepoint.rollback()
    row = await get_settings(review_db, first.id, "123", "456")
    assert row.enabled and row.rules_version == 2  # no internal commit


async def test_revocation_is_scoped_idempotent_and_blocks_rules(review_db, owners):
    first, second = owners
    for owner, installation in [(first, "123"), (second, "124")]:
        await create_installation(review_db, owner.id, installation)
        await create_settings(
            review_db, owner.id, installation, "456", "owner/repo", rules=ReviewRules(enabled=True)
        )
    revoked = await revoke_installation(review_db, first.id, "123")
    timestamp = revoked.revoked_at
    assert timestamp is not None
    assert (await revoke_installation(review_db, first.id, "123")).revoked_at == timestamp
    for operation in [
        lambda: get_settings(review_db, first.id, "123", "456"),
        lambda: replace_rules(review_db, first.id, "123", "456", ReviewRules(enabled=True)),
        lambda: create_settings(review_db, first.id, "123", "789", "owner/other"),
    ]:
        with pytest.raises(ReviewAccessDeniedError):
            await operation()
    row = await review_db.scalar(
        select(ReviewSettings).where(ReviewSettings.installation_id == "123")
    )
    assert row.enabled is False and row.rules_version == 2
    assert (await get_settings(review_db, second.id, "124", "456")).enabled is True


@pytest.mark.parametrize(
    "field,value",
    [("repo_id", "0"), ("repo_id", True), ("repo_name", "../bad"), ("repo_name", "repo")],
)
async def test_invalid_repository_identity(review_db, owners, field, value):
    first, _ = owners
    await create_installation(review_db, first.id, "123")
    values = {"repo_id": "456", "repo_name": "owner/repo", field: value}
    with pytest.raises(ValidationError):
        await create_settings(review_db, first.id, "123", **values)


@pytest.mark.parametrize(
    "values",
    [
        {"min_pr_lines": 0},
        {"rules_version": 0},
        {"focus": []},
        {"focus": ["unknown"]},
        {"skip_paths": ["a"] * 101},
        {"repo_id": "0"},
    ],
)
async def test_database_constraints(review_db, owners, values):
    first, _ = owners
    await create_installation(review_db, first.id, "123")
    with pytest.raises(IntegrityError):
        async with review_db.begin_nested():
            review_db.add(
                ReviewSettings(
                    **{
                        "installation_id": "123",
                        "owner_id": first.id,
                        "repo_id": "456",
                        "repo_name": "owner/repo",
                        **values,
                    }
                )
            )
            await review_db.flush()


async def test_concurrent_replacements_keep_version_monotonic(review_engine):
    owner_id = uuid4()
    async with AsyncSession(review_engine) as db:
        db.add(User(id=owner_id, email=f"{owner_id}@review.test"))
        await db.flush()
        await create_installation(db, owner_id, "987")
        await create_settings(db, owner_id, "987", "654", "owner/concurrent")
        await db.commit()

    async def write(minimum):
        async with AsyncSession(review_engine) as db:
            row = await replace_rules(db, owner_id, "987", "654", ReviewRules(min_pr_lines=minimum))
            version = row.rules_version
            await db.commit()
            return version

    versions = await asyncio.gather(write(2), write(3))
    assert sorted(versions) == [2, 3]


async def test_migration_round_trip_and_metadata():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0012")
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO users (email) VALUES ('sentinel@review.test')")
                )
            migrate(url, "upgrade", "head")
            async with engine.connect() as conn:

                def check(sync):
                    assert set(inspect(sync).get_table_names()) >= REVIEW_TABLES
                    ctx = MigrationContext.configure(
                        sync,
                        opts={
                            "include_object": lambda obj, name, kind, reflected, compare: (
                                kind != "table" or name in REVIEW_TABLES
                            ),
                            "compare_server_default": True,
                        },
                    )
                    assert compare_metadata(ctx, Base.metadata) == []

                await conn.run_sync(check)
                assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == (
                    ScriptDirectory(str(API_ROOT / "alembic")).get_current_head()
                )
            migrate(url, "downgrade", "0012")
            async with engine.connect() as conn:
                tables = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
                assert not REVIEW_TABLES & tables
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM users WHERE email='sentinel@review.test'")
                    )
                    == 1
                )
                assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "0012"
            migrate(url, "upgrade", "head")
            async with engine.connect() as conn:
                await conn.run_sync(check)
                assert (
                    await conn.scalar(
                        text("SELECT count(*) FROM users WHERE email='sentinel@review.test'")
                    )
                    == 1
                )
        finally:
            await engine.dispose()
