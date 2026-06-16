"""URL metadata 抓取 — Phase 3.3 链接收藏.

抓 title / description / image / favicon. 解析 OpenGraph / Twitter cards
优先, fallback 到 <title> + <meta name="description"> + /favicon.ico.

设计要点:
  - timeout 5s, 失败时 fallback: title = url, 其他 None
  - User-Agent 装作浏览器避免 403
  - 限制 response body 大小 (5MB) 防大文件耗内存
  - 相对 URL 转绝对 (image / favicon)
"""

import asyncio
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from plutolab_api.core.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 PlutoLab/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
_MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 MB


@dataclass(frozen=True)
class LinkMetadata:
    """fetch_url_metadata 返回值. 任何字段抓不到都 fallback."""

    title: str
    description: str | None
    image_url: str | None
    favicon_url: str | None


def _abs_url(base: str, candidate: str | None) -> str | None:
    if not candidate:
        return None
    try:
        return urljoin(base, candidate.strip())
    except Exception:
        return None


def _meta_content(soup: BeautifulSoup, **filters: str) -> str | None:
    """找符合 filters 的第一个 <meta> 的 content 属性."""
    tag = soup.find("meta", attrs=filters)
    if isinstance(tag, Tag):
        content = tag.get("content")
        if isinstance(content, str):
            stripped = content.strip()
            return stripped or None
    return None


def _parse_metadata(html: str, base_url: str) -> LinkMetadata:
    soup = BeautifulSoup(html, "html.parser")

    title = (
        _meta_content(soup, property="og:title")
        or _meta_content(soup, name="twitter:title")
        or (soup.title.string.strip() if soup.title and soup.title.string else None)
        or base_url
    )
    # 标题截断防止超长 (DB 500 字符限制)
    title = title[:500]

    description = (
        _meta_content(soup, property="og:description")
        or _meta_content(soup, name="twitter:description")
        or _meta_content(soup, name="description")
    )
    if description:
        description = description[:2000]

    image_raw = (
        _meta_content(soup, property="og:image")
        or _meta_content(soup, name="twitter:image")
    )
    image_url = _abs_url(base_url, image_raw)

    favicon_tag = soup.find("link", rel=lambda r: r and "icon" in r)
    favicon_raw = None
    if isinstance(favicon_tag, Tag):
        href = favicon_tag.get("href")
        if isinstance(href, str):
            favicon_raw = href
    favicon_url = _abs_url(base_url, favicon_raw) or _abs_url(base_url, "/favicon.ico")

    return LinkMetadata(
        title=title,
        description=description,
        image_url=image_url,
        favicon_url=favicon_url,
    )


async def fetch_url_metadata(url: str) -> LinkMetadata:
    """抓 URL 元数据. 失败时 title=url 其他 None — 不抛, 让上层正常保存."""
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            headers=_HEADERS,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            resp = await client.get(url)
            final_url = str(resp.url)
            ctype = resp.headers.get("content-type", "")
            if "html" not in ctype.lower():
                # 非 HTML (PDF / image / 直接资源) — 用 URL 当 title
                return LinkMetadata(
                    title=url[:500],
                    description=None,
                    image_url=None,
                    favicon_url=_abs_url(final_url, "/favicon.ico"),
                )
            content = resp.content[:_MAX_BODY_BYTES]
            html = content.decode(resp.encoding or "utf-8", errors="replace")
            return _parse_metadata(html, final_url)
    except (httpx.HTTPError, asyncio.TimeoutError) as e:
        logger.warning("plutolab.link.metadata_failed", url=url, error=str(e))
        return LinkMetadata(
            title=url[:500],
            description=None,
            image_url=None,
            favicon_url=None,
        )
