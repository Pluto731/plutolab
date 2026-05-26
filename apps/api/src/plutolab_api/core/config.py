"""App configuration loaded from environment variables / .env file."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = Field(default="development")
    version: str = Field(default="0.0.1")
    log_level: str = Field(default="INFO")

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"]
    )

    database_url: str = Field(default="postgresql+asyncpg://pluto:changeme@localhost:5432/pluto")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Auth / JWT. jwt_secret MUST be overridden in production via env.
    jwt_secret: str = Field(default="dev-insecure-change-me")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_ttl_min: int = Field(default=15)
    jwt_refresh_ttl_days: int = Field(default=7)

    # 头像本地存储目录 (prod 用 docker volume 挂载 /data/avatars)
    avatar_dir: str = Field(default="/data/avatars")
    avatar_max_bytes: int = Field(default=2 * 1024 * 1024)  # 2 MB

    # GitHub OAuth (未配置时 /auth/github 返回 503, 前端按钮禁用)
    github_client_id: str = Field(default="")
    github_client_secret: str = Field(default="")


settings = Settings()
