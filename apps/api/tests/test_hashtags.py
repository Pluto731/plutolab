"""Unit tests for core.hashtags — Phase 3.1.polish B.1."""

import pytest

from plutolab_api.core.hashtags import extract_hashtags


class TestExtractHashtags:
    def test_empty(self) -> None:
        assert extract_hashtags("") == []
        assert extract_hashtags("没有 tag 的笔记") == []

    def test_single_english(self) -> None:
        assert extract_hashtags("今天学了 #python 很爽") == ["python"]

    def test_single_chinese(self) -> None:
        assert extract_hashtags("今天 #想法 来了") == ["想法"]

    def test_multiple(self) -> None:
        result = extract_hashtags("#python #想法 #read 三个标签")
        assert result == ["python", "想法", "read"]

    def test_dedup_case_insensitive(self) -> None:
        # Python / PYTHON 视为同一 tag, 保留首次出现的大小写
        result = extract_hashtags("#Python rule #PYTHON repeat #python")
        assert result == ["Python"]

    def test_skip_markdown_heading(self) -> None:
        # markdown heading 是 # 后跟空格, 不当 tag
        assert extract_hashtags("# 标题\n## 副标题\n#tag 是 tag") == ["tag"]

    def test_skip_inline_a_pound_b(self) -> None:
        # a#bcd 不识别 (# 前必须空白或行首)
        assert extract_hashtags("a#bcd 不算") == []

    def test_at_line_start(self) -> None:
        assert extract_hashtags("#firstword 行首也算") == ["firstword"]

    def test_with_punctuation_before(self) -> None:
        # (tag) / 中文 「」 之类前置标点应该可识别
        assert extract_hashtags("看了(#标签)和「#其他」") == ["标签", "其他"]

    def test_numbers_underscore(self) -> None:
        assert extract_hashtags("#tag_123 #v2") == ["tag_123", "v2"]

    def test_double_hash_not_match(self) -> None:
        # ## h2 不识别
        assert extract_hashtags("## 二级标题 #tag") == ["tag"]


@pytest.mark.parametrize(
    "content,expected",
    [
        ("无", []),
        ("#a", ["a"]),
        (" #a ", ["a"]),
        ("#a #b", ["a", "b"]),
    ],
)
def test_parametrized(content: str, expected: list[str]) -> None:
    assert extract_hashtags(content) == expected
