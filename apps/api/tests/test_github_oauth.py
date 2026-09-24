"""Integration tests for GitHub OAuth login (exchange_code mocked)."""

import pytest
from httpx import AsyncClient

import plutolab_api.api.v1.auth as auth_module
from plutolab_api.core.config import settings
from plutolab_api.core.github_oauth import GitHubUser

GITHUB = "/api/v1/auth/github"
CONFIG = "/api/v1/auth/github/config"
REGISTER = "/api/v1/auth/register"
LINK_STATE = "/api/v1/auth/github/link/state"
LINK = "/api/v1/auth/github/link"
RU = "http://localhost:3000/auth/github/callback"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "github_client_id", "cid")
    monkeypatch.setattr(settings, "github_client_secret", "sec")


def _mock_exchange(monkeypatch: pytest.MonkeyPatch, gh: GitHubUser) -> None:
    async def fake(code: str, redirect_uri: str) -> GitHubUser:
        return gh

    monkeypatch.setattr(auth_module, "exchange_code", fake)


class TestGitHubConfig:
    async def test_unconfigured(self, client: AsyncClient) -> None:
        resp = await client.get(CONFIG)
        assert resp.status_code == 200
        assert resp.json()["configured"] is False

    async def test_configured(self, client: AsyncClient, configured: None) -> None:
        resp = await client.get(CONFIG)
        assert resp.json()["configured"] is True
        assert resp.json()["client_id"] == "cid"


class TestGitHubLogin:
    async def test_unconfigured_returns_503(self, client: AsyncClient) -> None:
        resp = await client.post(GITHUB, json={"code": "x", "redirect_uri": RU})
        assert resp.status_code == 503

    async def test_creates_new_user(
        self, client: AsyncClient, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _mock_exchange(
            monkeypatch,
            GitHubUser(
                id=999,
                login="octocat",
                email="octo@example.com",
                name="Octo",
                avatar="http://x/a.png",
            ),
        )
        resp = await client.post(GITHUB, json={"code": "x", "redirect_uri": RU})
        assert resp.status_code == 200
        user = resp.json()["user"]
        assert user["email"] == "octo@example.com"
        assert user["name"] == "Octo"
        assert user["email_verified"] is True
        assert resp.json()["access_token"]

    async def test_same_github_id_reuses_user(
        self, client: AsyncClient, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _mock_exchange(
            monkeypatch,
            GitHubUser(id=1000, login="repeat", email="repeat@example.com", name="R", avatar=None),
        )
        r1 = await client.post(GITHUB, json={"code": "x", "redirect_uri": RU})
        r2 = await client.post(GITHUB, json={"code": "y", "redirect_uri": RU})
        assert r1.json()["user"]["id"] == r2.json()["user"]["id"]

    async def test_links_existing_email(
        self, client: AsyncClient, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await client.post(REGISTER, json={"email": "merge@example.com", "password": "supersecret"})
        _mock_exchange(
            monkeypatch,
            GitHubUser(id=1001, login="m", email="merge@example.com", name="M", avatar=None),
        )
        resp = await client.post(GITHUB, json={"code": "x", "redirect_uri": RU})
        assert resp.status_code == 200
        assert resp.json()["user"]["email"] == "merge@example.com"


class TestGitHubAccountLink:
    async def test_links_to_authenticated_account_without_email_matching(
        self, client: AsyncClient, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        account = await client.post(
            REGISTER, json={"email": "pluto@example.com", "password": "supersecret"}
        )
        headers = {"Authorization": f"Bearer {account.json()['access_token']}"}
        state_resp = await client.post(LINK_STATE, headers=headers)
        assert state_resp.status_code == 200

        _mock_exchange(
            monkeypatch,
            GitHubUser(
                id=2001, login="pluto", email="different@example.com", name="Pluto", avatar=None
            ),
        )
        linked = await client.post(
            LINK,
            headers=headers,
            json={"code": "oauth-code", "redirect_uri": RU, "state": state_resp.json()["state"]},
        )
        assert linked.status_code == 200
        assert linked.json()["github_id"] == 2001
        assert linked.json()["email"] == "pluto@example.com"

        replay = await client.post(
            LINK,
            headers=headers,
            json={"code": "oauth-code", "redirect_uri": RU, "state": state_resp.json()["state"]},
        )
        assert replay.status_code == 400

    async def test_link_requires_authenticated_account(
        self, client: AsyncClient, configured: None
    ) -> None:
        response = await client.post(LINK_STATE)
        assert response.status_code == 401

    async def test_link_state_is_bound_to_issuing_account(
        self, client: AsyncClient, configured: None
    ) -> None:
        owner = await client.post(
            REGISTER, json={"email": "owner@example.com", "password": "supersecret"}
        )
        other = await client.post(
            REGISTER, json={"email": "other@example.com", "password": "supersecret"}
        )
        owner_headers = {"Authorization": f"Bearer {owner.json()['access_token']}"}
        other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
        state = (await client.post(LINK_STATE, headers=owner_headers)).json()["state"]

        response = await client.post(
            LINK,
            headers=other_headers,
            json={"code": "oauth-code", "redirect_uri": RU, "state": state + "tampered"},
        )
        assert response.status_code == 400

        cross_account = await client.post(
            LINK,
            headers=other_headers,
            json={"code": "oauth-code", "redirect_uri": RU, "state": state},
        )
        assert cross_account.status_code == 400

    async def test_rejects_github_identity_owned_by_another_account(
        self, client: AsyncClient, configured: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = await client.post(
            REGISTER, json={"email": "first@example.com", "password": "supersecret"}
        )
        second = await client.post(
            REGISTER, json={"email": "second@example.com", "password": "supersecret"}
        )
        headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
        state = (await client.post(LINK_STATE, headers=headers)).json()["state"]
        _mock_exchange(
            monkeypatch,
            GitHubUser(id=2002, login="taken", email="other@example.com", name=None, avatar=None),
        )
        first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
        first_state = (await client.post(LINK_STATE, headers=first_headers)).json()["state"]
        accepted = await client.post(
            LINK,
            headers=first_headers,
            json={"code": "first-code", "redirect_uri": RU, "state": first_state},
        )
        assert accepted.status_code == 200

        rejected = await client.post(
            LINK,
            headers=headers,
            json={"code": "second-code", "redirect_uri": RU, "state": state},
        )
        assert rejected.status_code == 409
