"""GitHub OAuth — exchange an authorization code for the GitHub user profile.

Isolated here (no DB, no FastAPI) so the endpoint stays thin and this can be
mocked in tests.
"""

from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from plutolab_api.core.config import settings

_TOKEN_URL = "https://github.com/login/oauth/access_token"
_USER_URL = "https://api.github.com/user"
_EMAILS_URL = "https://api.github.com/user/emails"


@dataclass(frozen=True)
class GitHubUser:
    id: int
    login: str
    email: str | None
    name: str | None
    avatar: str | None


async def exchange_code(code: str, redirect_uri: str) -> GitHubUser:
    """Trade an OAuth code for the authenticated GitHub user. Raises HTTP 400/502
    on failure."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            token_resp = await client.post(
                _TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="GitHub 授权失败")

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            }
            user = (await client.get(_USER_URL, headers=headers)).json()
            email = user.get("email")
            if not email:
                emails = (await client.get(_EMAILS_URL, headers=headers)).json()
                if isinstance(emails, list):
                    email = next(
                        (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                        None,
                    )
        except httpx.HTTPError as e:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, detail="无法连接 GitHub"
            ) from e

    return GitHubUser(
        id=user["id"],
        login=user["login"],
        email=email,
        name=user.get("name"),
        avatar=user.get("avatar_url"),
    )
