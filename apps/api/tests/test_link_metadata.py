"""Unit tests for core.link_metadata HTML parsing — Phase 3.3."""

from plutolab_api.core.link_metadata import _parse_metadata


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

    def test_empty_meta_content_falls_back(self) -> None:
        html = """
        <html><head>
          <title>真标题</title>
          <meta property="og:title" content="">
        </head></html>
        """
        m = _parse_metadata(html, "https://example.com/")
        assert m.title == "真标题"
