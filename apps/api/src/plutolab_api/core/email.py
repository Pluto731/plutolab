"""Email sending: Jinja2 HTML templates + aiosmtplib delivery.

`Mailer` is wrapped in a FastAPI dependency (`get_mailer`) so tests can swap
in a fake that records sends instead of hitting a real SMTP server.
"""

from email.message import EmailMessage
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from plutolab_api.core.config import settings
from plutolab_api.core.logging import get_logger

logger = get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=False,
)


def render(template_name: str, **ctx: object) -> str:
    return _env.get_template(template_name).render(**ctx)


class Mailer:
    """Thin async SMTP wrapper. Holds no state — one instance per request is fine."""

    async def send(self, to: str, subject: str, html_body: str, text_body: str) -> None:
        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_use_tls,
            start_tls=settings.smtp_start_tls,
        )
        logger.info("plutolab.email.sent", to=to, subject=subject)

    async def send_password_reset(self, to: str, reset_url: str, ttl_minutes: int) -> None:
        html = render(
            "reset_password.html",
            reset_url=reset_url,
            ttl_minutes=ttl_minutes,
        )
        text = (
            "你请求了 PlutoLab 密码重置。\n\n"
            f"请打开以下链接设置新密码 (有效期 {ttl_minutes} 分钟):\n"
            f"{reset_url}\n\n"
            "如果不是你本人操作，请忽略此邮件。"
        )
        await self.send(to=to, subject="重置你的 PlutoLab 密码", html_body=html, text_body=text)


def get_mailer() -> Mailer:
    """FastAPI dependency: stateless mailer instance per request."""
    return Mailer()
