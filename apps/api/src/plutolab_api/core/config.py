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


settings = Settings()
