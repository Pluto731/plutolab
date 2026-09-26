"""Round-trip the new permission constraint only in a disposable database."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.test_review_domain import disposable_database, migrate


async def test_github_permission_migration_round_trip():
    async with disposable_database() as url:
        migrate(url, "upgrade", "0025")
        engine = create_async_engine(url)

        async def constraint():
            async with engine.connect() as conn:
                return await conn.scalar(
                    text(
                        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conname = 'ck_agents_registered_tools'"
                    )
                )

        try:
            assert "search_github" not in await constraint()
            migrate(url, "upgrade", "head")
            assert "search_github" in await constraint()
            migrate(url, "downgrade", "0025")
            assert "search_github" not in await constraint()
            migrate(url, "upgrade", "head")
            assert "search_github" in await constraint()
        finally:
            await engine.dispose()
