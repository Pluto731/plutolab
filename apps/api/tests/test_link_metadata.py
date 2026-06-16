"""Unit tests for core.link_metadata HTML parsing + SSRF 防御 — Phase 3.3."""

import pytest

from plutolab_api.core.link_metadata import (
    UnsafeURLError,
    _check_url_scheme_and_host,
    _parse_metadata,
    _resolve_and_check_safe,
)


class TestParseMetadata:
    def test_og_tags_preferred(self) -> None:
        html = """
        <html><head>
          <title>Title 标题</title>
          <meta property="og:title" content="OG Title">
          <meta property="og:description" content="OG Desc">
          <meta property="og:image" content="/img.jpg">
        </head></html>
        """
        m = _parse_metadata(html, "https://example.com/")
        assert m.title == "OG Title"
        assert m.description == "OG Desc"
        assert m.image_url == "https://example.com/img.jpg"

    def test_twitter_fallback(self) -> None:
        html = """
        <html><head>
          <title>T</title>
          <meta name="twitter:title" content="Tweet Title">
          <meta name="twitter:description" content="Tweet Desc">
        </head></html>
        """
        m = _parse_metadata(html, "https://example.com/")
        assert m.title == "Tweet Title"
        assert m.description == "Tweet Desc"

    def test_title_tag_fallback(self) -> None:
        html = "<html><head><title>仅标题</title></head></html>"
        m = _parse_metadata(html, "https://example.com/")
        assert m.title == "仅标题"
        assert m.description is None
        assert m.image_url is None

    def test_no_title_uses_url(self) -> None:
        html = "<html><head></head></html>"
        m = _parse_metadata(html, "https://example.com/page")
        assert m.title == "https://example.com/page"

    def test_meta_description(self) -> None:
        html = """
        <html><head>
          <title>T</title>
          <meta name="description" content="标准描述">
        </head></html>
        """
        m = _parse_metadata(html, "https://example.com/")
        assert m.description == "标准描述"

    def test_favicon_link_tag(self) -> None:
        html = """
        <html><head>
          <title>T</title>
          <link rel="icon" href="/static/favicon.png">
        </head></html>
        """
        m = _parse_metadata(html, "https://example.com/page")
        assert m.favicon_url == "https://example.com/static/favicon.png"

    def test_favicon_fallback_default(self) -> None:
        html = "<html><head><title>T</title></head></html>"
        m = _parse_metadata(html, "https://example.com/page")
        assert m.favicon_url == "https://example.com/favicon.ico"

    def test_title_truncated_to_500(self) -> None:
        long = "x" * 800
        html = f"<html><head><title>{long}</title></head></html>"
        m = _parse_metadata(html, "https://example.com/")
        assert len(m.title) == 500

    def test_absolute_image_url_preserved(self) -> None:
        html = """
        <html><head>
          <title>T</title>
          <meta property="og:image" content="https://cdn.example.com/img.png">
        </head></html>
        """
        m = _parse_metadata(html, "https://example.com/")
        assert m.image_url == "https://cdn.example.com/img.png"

    def test_empty_meta_content_falls_back_first(self) -> None:
        html = """
        <html><head>
          <title>真标题</title>
          <meta property="og:title" content="">
        </head></html>
        """
        m = _parse_metadata(html, "https://example.com/")
        assert m.title == "真标题"


class TestSSRFGuard:
    """SSRF 防御: scheme 校验 + 内网 IP 拒绝 + redirect 每跳重新校验."""

    def test_reject_non_http_scheme(self) -> None:
        for bad in ["ftp://example.com", "file:///etc/passwd", "gopher://h"]:
            with pytest.raises(UnsafeURLError, match="scheme"):
                _check_url_scheme_and_host(bad)

    def test_accept_http_and_https(self) -> None:
        assert _check_url_scheme_and_host("http://example.com") == "example.com"
        assert _check_url_scheme_and_host("https://a.b.cn/path") == "a.b.cn"

    async def test_reject_loopback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # mock getaddrinfo 返回 127.0.0.1
        def fake_getaddrinfo(host: str, _port: object) -> list[tuple]:
            return [(2, 1, 6, "", ("127.0.0.1", 0))]

        monkeypatch.setattr(
            "plutolab_api.core.link_metadata.socket.getaddrinfo",
            fake_getaddrinfo,
        )
        with pytest.raises(UnsafeURLError, match="受限范围"):
            await _resolve_and_check_safe("localhost")

    async def test_reject_private_10x(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_getaddrinfo(host: str, _port: object) -> list[tuple]:
            return [(2, 1, 6, "", ("10.0.0.1", 0))]

        monkeypatch.setattr(
            "plutolab_api.core.link_metadata.socket.getaddrinfo",
            fake_getaddrinfo,
        )
        with pytest.raises(UnsafeURLError, match="受限范围"):
            await _resolve_and_check_safe("internal.example")

    async def test_reject_link_local_metadata_169_254(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # AWS/GCP/Azure 云元数据 IP
        def fake_getaddrinfo(host: str, _port: object) -> list[tuple]:
            return [(2, 1, 6, "", ("169.254.169.254", 0))]

        monkeypatch.setattr(
            "plutolab_api.core.link_metadata.socket.getaddrinfo",
            fake_getaddrinfo,
        )
        with pytest.raises(UnsafeURLError, match="受限范围"):
            await _resolve_and_check_safe("metadata.example")

    async def test_reject_ipv6_loopback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_getaddrinfo(host: str, _port: object) -> list[tuple]:
            return [(10, 1, 6, "", ("::1", 0, 0, 0))]

        monkeypatch.setattr(
            "plutolab_api.core.link_metadata.socket.getaddrinfo",
            fake_getaddrinfo,
        )
        with pytest.raises(UnsafeURLError, match="受限范围"):
            await _resolve_and_check_safe("ipv6-localhost.example")

    async def test_accept_public_ip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 8.8.8.8 (Google Public DNS) 是合法公网 IP
        def fake_getaddrinfo(host: str, _port: object) -> list[tuple]:
            return [(2, 1, 6, "", ("8.8.8.8", 0))]

        monkeypatch.setattr(
            "plutolab_api.core.link_metadata.socket.getaddrinfo",
            fake_getaddrinfo,
        )
        # 不抛 = 通过
        await _resolve_and_check_safe("dns.google")

    async def test_reject_mixed_results_with_private(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DNS 同时返回公网 + 内网 → 任一不安全就拒绝 (防 DNS pinning 绕过)."""
        def fake_getaddrinfo(host: str, _port: object) -> list[tuple]:
            return [
                (2, 1, 6, "", ("8.8.8.8", 0)),
                (2, 1, 6, "", ("10.0.0.5", 0)),
            ]

        monkeypatch.setattr(
            "plutolab_api.core.link_metadata.socket.getaddrinfo",
            fake_getaddrinfo,
        )
        with pytest.raises(UnsafeURLError, match="受限范围"):
            await _resolve_and_check_safe("evil.example")

    async def test_dns_resolve_fail_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import socket as _socket

        def fake_getaddrinfo(host: str, _port: object) -> list[tuple]:
            raise _socket.gaierror("no such host")

        monkeypatch.setattr(
            "plutolab_api.core.link_metadata.socket.getaddrinfo",
            fake_getaddrinfo,
        )
        with pytest.raises(UnsafeURLError, match="DNS 解析失败"):
            await _resolve_and_check_safe("nx.invalid")
