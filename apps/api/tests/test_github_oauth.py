"""Integration tests for GitHub OAuth login (exchange_code mocked)."""

import pytest
from httpx import AsyncClient

import plutolab_api.api.v1.auth as auth_module
from plutolab_api.core.config import settings
from plutolab_api.core.github_oauth import GitHubUser

GITHUB = "/api/v1/auth/github"
CONFIG = "/api/v1/auth/github/config"
REGISTER = "/api/v1/auth/register"
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
            GitHubUser(id=999, login="octocat", email="octo@example.com", name="Octo", avatar="http://x/a.png"),
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
