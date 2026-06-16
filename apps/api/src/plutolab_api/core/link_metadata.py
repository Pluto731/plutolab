"""URL metadata 抓取 — Phase 3.3 链接收藏 + SSRF 防御.

抓 title / description / image / favicon. 解析 OpenGraph / Twitter cards
优先, fallback 到 <title> + <meta name="description"> + /favicon.ico.

SSRF 防御:
  1. URL scheme 强制 http / https
  2. 每次连接前 socket.getaddrinfo 解析所有 A/AAAA, 任一 IP 落在 loopback /
     private / link-local / reserved / multicast / unspecified 范围 → 拒绝
  3. follow_redirects=False + 手动循环, 每跳重新校验 host
  4. body 限 5MB 防大文件耗内存

注意 — DNS rebinding 残留风险:
  校验时 DNS 返回 A=公网, 连接时 DNS 返回 B=内网, 是经典 TOCTOU. 完美防御需要
  pinned IP transport (httpx.HTTPTransport 不直接支持). 我们用 5s timeout +
  follow_redirects=False 把攻击窗口压到极短, 现实风险较低. 如果未来要承接
  Phase 4 RAG 等需要抓任意外部 URL 的能力, 考虑把 fetch 模块迁到独立子进程
  + 容器网络隔离 (deny private CIDR egress).
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

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
_MAX_REDIRECTS = 5


class UnsafeURLError(Exception):
    """URL scheme 非 http(s) / host 解析到内网 / 元数据 IP 等不安全目标."""


@dataclass(frozen=True)
class LinkMetadata:
    """fetch_url_metadata 返回值. 任何字段抓不到都 fallback."""

    title: str
    description: str | None
    image_url: str | None
    favicon_url: str | None


def _check_url_scheme_and_host(url: str) -> str:
    """校验 URL scheme 在 {http, https} 并返回 hostname."""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise UnsafeURLError(f"不允许的 scheme: {scheme!r}")
    if not parsed.hostname:
        raise UnsafeURLError("URL 缺少 host")
    return parsed.hostname


async def _resolve_and_check_safe(host: str) -> None:
    """异步解析 host 的所有 A/AAAA, 任一落在受限范围就 raise.

    覆盖:
      - is_loopback: 127.0.0.0/8, ::1
      - is_private: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7
      - is_link_local: 169.254.0.0/16 (含云元数据!), fe80::/10
      - is_reserved: 0.0.0.0/8, 240.0.0.0/4 等
      - is_multicast / is_unspecified
    """
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"DNS 解析失败: {host}") from e

    safe_count = 0
    for _af, _st, _proto, _can, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeURLError(
                f"目标 IP {ip} 在受限范围 (host={host})"
            )
        safe_count += 1
    if safe_count == 0:
        raise UnsafeURLError(f"host {host} 无可用公网 IP")


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


async def _safe_get(
    client: httpx.AsyncClient, start_url: str
) -> httpx.Response:
    """手动 redirect 循环 — 每跳重新校验 host 防 SSRF 绕过."""
    current = start_url
    for _ in range(_MAX_REDIRECTS + 1):
        host = _check_url_scheme_and_host(current)
        await _resolve_and_check_safe(host)
        resp = await client.get(current)
        if resp.is_redirect:
            location = resp.headers.get("location")
            if not location:
                return resp
            current = urljoin(current, location)
            continue
        return resp
    raise UnsafeURLError("超过最大跳转次数")


async def fetch_url_metadata(url: str) -> LinkMetadata:
    """抓 URL 元数据. 失败 / 不安全时 fallback (title=url 其他 None) 不抛."""
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            headers=_HEADERS,
            follow_redirects=False,  # SSRF 防御: 手动循环 + 每跳重新校验
        ) as client:
            resp = await _safe_get(client, url)
            final_url = str(resp.url)
            ctype = resp.headers.get("content-type", "")
            if "html" not in ctype.lower():
                return LinkMetadata(
                    title=url[:500],
                    description=None,
                    image_url=None,
                    favicon_url=_abs_url(final_url, "/favicon.ico"),
                )
            content = resp.content[:_MAX_BODY_BYTES]
            html = content.decode(resp.encoding or "utf-8", errors="replace")
            return _parse_metadata(html, final_url)
    except UnsafeURLError as e:
        logger.warning("plutolab.link.metadata_unsafe", url=url, error=str(e))
    except (httpx.HTTPError, asyncio.TimeoutError) as e:
        logger.warning("plutolab.link.metadata_failed", url=url, error=str(e))
    return LinkMetadata(
        title=url[:500],
        description=None,
        image_url=None,
        favicon_url=None,
    )
