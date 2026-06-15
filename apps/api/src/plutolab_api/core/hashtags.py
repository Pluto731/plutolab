"""Hashtag 解析 — Phase 3.1.polish B.1.

从笔记 content 提取 #hashtag, 大小写不敏感去重, 保留首次出现的大小写形式.
markdown heading (# 后跟空格) 不当作 hashtag.

规则:
  - # 前面必须是行首 / 空白 / 标点 (非字字符), 排除 a#tag 这种 inline
  - # 后必须紧跟 1+ 字字符 (字母 / 数字 / 下划线 / 汉字)
  - 跨行用 MULTILINE
"""

import re

# 不包含 # 字符本身, 避免 ##h2 / ###h3 也被识别为 hashtag
HASHTAG_RE = re.compile(
    r"(?:^|[^\w#])#([A-Za-z0-9_一-鿿]+)",
    re.MULTILINE,
)


def extract_hashtags(content: str) -> list[str]:
    """从笔记正文提取 hashtag 列表, 去重保序 (按 lower-case 去重, 保留首次大小写)."""
    if not content:
        return []
    matches = HASHTAG_RE.findall(content)
    seen: set[str] = set()
    result: list[str] = []
    for tag in matches:
        lower = tag.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(tag)
    return result
