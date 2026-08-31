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

    # 头像本地存储目录 (dev 默认 ./_avatars; prod 用 docker volume 挂载 /data/avatars)
    avatar_dir: str = Field(default="./_avatars")
    avatar_max_bytes: int = Field(default=2 * 1024 * 1024)  # 2 MB

    # GitHub OAuth (未配置时 /auth/github 返回 503, 前端按钮禁用)
    github_client_id: str = Field(default="")
    github_client_secret: str = Field(default="")

    # 邮件 (本地默认指向 Mailpit; 生产用环境变量覆盖指向真实 SMTP)
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=1025)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="PlutoLab <noreply@plutolab.local>")
    smtp_use_tls: bool = Field(default=False)
    smtp_start_tls: bool = Field(default=False)

    # 前端站点 base url (拼邮件里的链接用; 生产用环境变量覆盖成对外域名/IP)
    app_base_url: str = Field(default="http://localhost:3000")

    # 密码重置 token 有效期 (秒, 链接式流程)
    password_reset_ttl_seconds: int = Field(default=3600)
    # 同邮箱发送间隔 (秒) — 防刷
    password_reset_rate_limit_seconds: int = Field(default=60)
    # 密码重置验证码 (Phase 2.3.c) 有效期 — 10 分钟比链接式短
    password_reset_code_ttl_seconds: int = Field(default=600)
    # 验证码错码次数上限 (达到后该次申请作废, 要重新申请)
    password_reset_code_max_attempts: int = Field(default=3)

    # 邮箱验证 token 有效期 (秒, 默认 24 小时)
    email_verify_ttl_seconds: int = Field(default=86400)
    # 同用户重发验证邮件间隔 (秒)
    email_verify_rate_limit_seconds: int = Field(default=60)

    # API Key 加密 (Phase 2.5) — Fernet 对称密钥, 生产必须用真随机值
    # 生成: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # dev 默认值不安全 (是从已知字符串 b64 来的), 启动时 log warning 提醒生产换
    fernet_key: str = Field(default="cGx1dG9sYWJfZGV2X2luc2VjdXJlX2tleV94eF8xMjM=")

    # Onboarding: 注册成功后是否自动写入示例笔记 (Phase 3.1.polish A.1-4)
    # 生产/dev 都 True; 测试用 pytest fixture 关掉 (避免"新用户 0 笔记"前提失效)
    onboarding_sample_note: bool = Field(default=True)


settings = Settings()
