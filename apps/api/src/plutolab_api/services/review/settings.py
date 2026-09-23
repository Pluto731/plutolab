"""Tenant-scoped rules. Caller supplies authenticated owner and controls the transaction.

Low-level create functions require verified ownership. API-facing functions below
verify membership through the installation adapter and recheck revocation under lock.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.github_app import GitHubAppError
from plutolab_api.models.review import GitHubInstallation, ReviewSettings
from plutolab_api.schemas.review import Focus
from plutolab_api.services.review.github_client import GitHubAppClient, Repository

GitHubId = Annotated[str, Field(strict=True, pattern=r"^[1-9][0-9]{0,31}$")]
RepoName = Annotated[
    str, Field(strict=True, max_length=201, pattern=r"^[A-Za-z0-9-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
]


class ReviewRules(BaseModel):
    """Full replacement rules, not a patch. Omitted enabled always means disabled.

    Globs support relative paths with *, ** and ? only, at most 100 x 256 chars.
    The SQL integer threshold is not a token/line execution budget (later slice).
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = False
    min_pr_lines: int = Field(default=1, gt=0, le=2_147_483_647)
    max_pr_lines: int | None = Field(default=None, gt=0, le=2_147_483_647)
    skip_paths: list[Annotated[str, Field(max_length=256, min_length=1)]] = Field(
        default_factory=list, max_length=100
    )
    focus: list[Focus] = Field(
        default_factory=lambda: ["security", "performance", "quality"], min_length=1, max_length=3
    )

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ReviewRules":
        if self.max_pr_lines is not None and self.max_pr_lines < self.min_pr_lines:
            raise ValueError("max_pr_lines must be at least min_pr_lines")
        return self

    @field_validator("skip_paths")
    @classmethod
    def validate_paths(cls, paths: list[str]) -> list[str]:
        for path in paths:
            if (
                not path.isprintable()
                or path != path.strip()
                or any(c in path for c in "\\:[]{}!^$()|")
                or any(part in ("", ".", "..") for part in path.split("/"))
                or any("**" in part and part != "**" for part in path.split("/"))
            ):
                raise ValueError("skip_paths must be bounded relative globs using *, ** or ?")
        if len(set(paths)) != len(paths):
            raise ValueError("skip_paths must be unique")
        return paths

    @field_validator("focus")
    @classmethod
    def validate_focus(cls, focus: list[Focus]) -> list[Focus]:
        if len(set(focus)) != len(focus):
            raise ValueError("focus dimensions must be unique")
        return focus


class ReviewAccessDeniedError(LookupError):
    """Uniform absent/foreign/revoked resource result; HTTP mapping is a later slice."""


class ReviewConflictError(ValueError):
    """Installation or repository already registered; existing owner is never disclosed."""


async def get_installation(
    db: AsyncSession,
    owner_id: UUID,
    installation_id: str,
    *,
    active: bool = False,
    lock: bool = False,
) -> GitHubInstallation:
    installation_id = TypeAdapter(GitHubId).validate_python(installation_id)
    query = (
        select(GitHubInstallation)
        .where(
            GitHubInstallation.installation_id == installation_id,
            GitHubInstallation.owner_id == owner_id,
        )
        .execution_options(populate_existing=True)
    )
    if active:
        query = query.where(GitHubInstallation.revoked_at.is_(None))
    if lock:
        query = query.with_for_update()
    installation = await db.scalar(query)
    if installation is None:
        raise ReviewAccessDeniedError("Installation unavailable")
    return installation


async def _insert(db: AsyncSession, row: GitHubInstallation | ReviewSettings) -> None:
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ReviewConflictError("Review resource already registered") from exc
        raise


async def create_installation(
    db: AsyncSession, owner_id: UUID, installation_id: str
) -> GitHubInstallation:
    row = GitHubInstallation(
        owner_id=owner_id, installation_id=TypeAdapter(GitHubId).validate_python(installation_id)
    )
    await _insert(db, row)
    return row


async def create_settings(
    db: AsyncSession,
    owner_id: UUID,
    installation_id: str,
    repo_id: str,
    repo_name: str,
    *,
    rules: ReviewRules | None = None,
) -> ReviewSettings:
    await get_installation(db, owner_id, installation_id, active=True, lock=True)
    validated = ReviewRules.model_validate(rules.model_dump() if rules is not None else {})
    row = ReviewSettings(
        owner_id=owner_id,
        installation_id=installation_id,
        repo_id=TypeAdapter(GitHubId).validate_python(repo_id),
        repo_name=TypeAdapter(RepoName).validate_python(repo_name),
        **validated.model_dump(),
    )
    await _insert(db, row)
    return row


async def get_settings(
    db: AsyncSession, owner_id: UUID, installation_id: str, repo_id: str
) -> ReviewSettings:
    await get_installation(db, owner_id, installation_id, active=True)
    row = await db.scalar(
        select(ReviewSettings)
        .where(
            ReviewSettings.owner_id == owner_id,
            ReviewSettings.installation_id == installation_id,
            ReviewSettings.repo_id == TypeAdapter(GitHubId).validate_python(repo_id),
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise ReviewAccessDeniedError("Repository settings unavailable")
    return row


async def replace_rules(
    db: AsyncSession,
    owner_id: UUID,
    installation_id: str,
    repo_id: str,
    rules: ReviewRules,
) -> ReviewSettings:
    await get_installation(db, owner_id, installation_id, active=True, lock=True)
    row = await get_settings(db, owner_id, installation_id, repo_id)
    validated = ReviewRules.model_validate(rules.model_dump())
    values = validated.model_dump()
    if any(getattr(row, key) != value for key, value in values.items()):
        for key, value in values.items():
            setattr(row, key, value)
        row.rules_version += 1
        await db.flush()
    return row


async def revoke_installation(
    db: AsyncSession, owner_id: UUID, installation_id: str
) -> GitHubInstallation:
    row = await get_installation(db, owner_id, installation_id, lock=True)
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await db.execute(
            update(ReviewSettings)
            .where(
                ReviewSettings.owner_id == owner_id,
                ReviewSettings.installation_id == installation_id,
                ReviewSettings.enabled.is_(True),
            )
            .values(enabled=False, rules_version=ReviewSettings.rules_version + 1)
        )
        await db.flush()
    return row


class RepositoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(default="", max_length=100, pattern=r"^[A-Za-z0-9_. /-]*$")
    page: int = Field(default=1, ge=1, le=10000)
    per_page: int = Field(default=30, ge=1, le=100)


class RepositoryListItem(BaseModel):
    repo_id: str
    repo_name: str
    private: bool
    default_branch: str | None
    enabled: bool
    rules_version: int


class AccessibleRepositories(BaseModel):
    repositories: list[RepositoryListItem]
    total_count: int
    page: int
    per_page: int


class ReviewRepositoryGitHubClient(GitHubAppClient):
    async def repository_by_id(self, installation_id: str, repo_id: str) -> Repository:
        repo_id = TypeAdapter(GitHubId).validate_python(repo_id)
        response = await self._get(installation_id, f"/repositories/{repo_id}")
        try:
            repository = Repository.model_validate_json(response.content)
        except ValidationError:
            repository = None
        if repository is None or repository.id != repo_id:
            raise GitHubAppError("invalid_response")
        return repository


def _verified_repo_name(repository: Repository) -> str:
    try:
        return TypeAdapter(RepoName).validate_python(repository.full_name)
    except ValidationError:
        pass
    raise GitHubAppError("invalid_response")


async def _sync_repository(
    db: AsyncSession, owner_id: UUID, installation_id: str, repository: Repository
) -> ReviewSettings:
    name = _verified_repo_name(repository)
    row = await db.scalar(
        select(ReviewSettings)
        .where(
            ReviewSettings.owner_id == owner_id,
            ReviewSettings.installation_id == installation_id,
            ReviewSettings.repo_id == repository.id,
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        return await create_settings(db, owner_id, installation_id, repository.id, name)
    # Display metadata can change on rename; keep rules and immutable job snapshots intact.
    row.repo_name = name
    await db.flush()
    return row


async def list_accessible_repositories(
    db: AsyncSession,
    github: ReviewRepositoryGitHubClient,
    owner_id: UUID,
    installation_id: str,
    query: RepositoryQuery,
) -> AccessibleRepositories:
    query = RepositoryQuery.model_validate(query.model_dump())
    await get_installation(db, owner_id, installation_id, active=True)
    if query.q.strip():
        # GitHub's installation list has no search parameter. Filter a bounded COMPLETE
        # enumeration, then paginate matching results; never pretend one page is exhaustive.
        first = await github.list_repositories(installation_id, page=1, per_page=100)
        if first.total_count > 10000:
            raise GitHubAppError("repository_search_limit")
        repositories = list(first.repositories)
        for page in range(2, (first.total_count + 99) // 100 + 1):
            batch = await github.list_repositories(installation_id, page=page, per_page=100)
            if batch.total_count != first.total_count:
                raise GitHubAppError("repository_listing_changed", retryable=True)
            repositories.extend(batch.repositories)
        if len(repositories) != first.total_count or len({r.id for r in repositories}) != len(
            repositories
        ):
            raise GitHubAppError("repository_listing_changed", retryable=True)
        matches = sorted(
            (r for r in repositories if query.q.strip().casefold() in r.full_name.casefold()),
            key=lambda repository: (repository.full_name.casefold(), repository.id),
        )
        total_count = len(matches)
        offset = (query.page - 1) * query.per_page
        repositories = matches[offset : offset + query.per_page]
    else:
        batch = await github.list_repositories(
            installation_id, page=query.page, per_page=query.per_page
        )
        repositories = batch.repositories
        total_count = batch.total_count
        if len(repositories) > query.per_page or len({r.id for r in repositories}) != len(
            repositories
        ):
            raise GitHubAppError("invalid_response")
    items = []
    async with db.begin_nested():
        # Recheck revocation after HTTP, before synchronizing; same lock as revoke/updates.
        await get_installation(db, owner_id, installation_id, active=True, lock=True)
        for repository in repositories:
            row = await _sync_repository(db, owner_id, installation_id, repository)
            items.append(
                RepositoryListItem(
                    repo_id=row.repo_id,
                    repo_name=row.repo_name,
                    private=repository.private,
                    default_branch=repository.default_branch,
                    enabled=row.enabled,
                    rules_version=row.rules_version,
                )
            )
    return AccessibleRepositories(
        repositories=items, total_count=total_count, page=query.page, per_page=query.per_page
    )


async def read_repository_rules(
    db: AsyncSession,
    github: ReviewRepositoryGitHubClient,
    owner_id: UUID,
    installation_id: str,
    repo_id: str,
) -> ReviewSettings:
    await get_installation(db, owner_id, installation_id, active=True)
    repository = await github.repository_by_id(installation_id, repo_id)
    async with db.begin_nested():
        await get_installation(db, owner_id, installation_id, active=True, lock=True)
        return await _sync_repository(db, owner_id, installation_id, repository)


async def update_repository_rules(
    db: AsyncSession,
    github: ReviewRepositoryGitHubClient,
    owner_id: UUID,
    installation_id: str,
    repo_id: str,
    rules: ReviewRules,
    *,
    expected_rules_version: int,
) -> ReviewSettings:
    validated = ReviewRules.model_validate(rules.model_dump())
    await get_installation(db, owner_id, installation_id, active=True)
    repository = await github.repository_by_id(installation_id, repo_id)
    async with db.begin_nested():
        await get_installation(db, owner_id, installation_id, active=True, lock=True)
        row = await _sync_repository(db, owner_id, installation_id, repository)
        if row.rules_version != expected_rules_version:
            raise ReviewConflictError("Repository rules changed; reload before saving")
        if row.rules_version == 2_147_483_647 and any(
            getattr(row, key) != value for key, value in validated.model_dump().items()
        ):
            raise ReviewConflictError("Repository rules version exhausted")
        return await replace_rules(db, owner_id, installation_id, repo_id, validated)
