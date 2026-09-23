"""Slice 7 discovery addition: owner-only DB reads, no GitHub traffic or mutations."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from plutolab_api.models.review import GitHubInstallation
from tests.test_review_installations_api import PREFIX
from tests.test_review_installations_api import api as api
from tests.test_review_installations_api import local_only as local_only
from tests.test_review_installations_api import owners as owners
from tests.test_review_installations_api import review_db as review_db
from tests.test_review_installations_api import review_engine as review_engine


async def test_empty_list_and_verified_account_identity(api):
    response = await api.client.get(PREFIX)
    assert response.status_code == 200
    assert response.json() == {"installations": [], "github_account_id": "101"}
    assert response.headers["cache-control"] == "no-store"
    assert api.requests == []


async def test_discovery_is_owner_scoped_including_revoked_history(api, review_db):
    review_db.add_all(
        [
            GitHubInstallation(installation_id="301", owner_id=api.users[0].id),
            GitHubInstallation(
                installation_id="302",
                owner_id=api.users[0].id,
                revoked_at=datetime(2026, 9, 18, tzinfo=UTC),
            ),
            GitHubInstallation(installation_id="401", owner_id=api.users[1].id),
        ]
    )
    await review_db.flush()
    before = await review_db.scalar(select(func.count()).select_from(GitHubInstallation))
    response = await api.client.get(PREFIX, params={"user_id": str(api.users[1].id)})
    assert response.status_code == 200
    rows = response.json()["installations"]
    assert {row["installation_id"] for row in rows} == {"301", "302"}
    assert {row["installation_id"]: row["active"] for row in rows} == {"301": True, "302": False}
    other = await api.client.get(PREFIX, headers=api.other_auth())
    assert other.status_code == 200
    assert other.json()["github_account_id"] == "202"
    assert [row["installation_id"] for row in other.json()["installations"]] == ["401"]
    assert await review_db.scalar(select(func.count()).select_from(GitHubInstallation)) == before
    assert not review_db.dirty and not review_db.new
    assert api.requests == []


async def test_discovery_requires_current_user(api):
    api.client.headers.pop("Authorization")
    response = await api.client.get(PREFIX)
    assert response.status_code in (401, 403)
    assert api.requests == []


async def test_unlinked_account_reports_no_verified_github_identity(api, review_db):
    api.users[0].github_id = None
    await review_db.flush()
    response = await api.client.get(PREFIX)
    assert response.status_code == 200
    assert response.json() == {"installations": [], "github_account_id": None}
    assert api.requests == []
