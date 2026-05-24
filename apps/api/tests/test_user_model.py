"""Integration test for the User model: insert + read back."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models import User


@pytest.mark.asyncio
async def test_user_insert_and_select(db_session: AsyncSession) -> None:
    user = User(email="test@plutolab.local", name="Test", plan="free")
    db_session.add(user)
    await db_session.flush()  # populate server defaults like id

    fetched = await db_session.scalar(select(User).where(User.email == "test@plutolab.local"))
    assert fetched is not None
    assert fetched.email == "test@plutolab.local"
    assert fetched.plan == "free"
    assert fetched.id is not None
    assert fetched.created_at is not None
