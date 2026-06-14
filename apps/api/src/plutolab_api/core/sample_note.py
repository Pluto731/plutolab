"""Onboarding 示例笔记 — Phase 3.1.polish A.1-4 收尾.

注册成功后自动为新用户写入一条欢迎笔记, 让首次进入 /notes 不再空荡.
老用户兜底走 `/notes/sample` POST 接口手动加载.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.models.note import Note

SAMPLE_NOTE_TITLE = "🪐 从这里开始 — PlutoLab 入门"

SAMPLE_NOTE_CONTENT = """这是一条示例笔记，展示笔记功能怎么用。

## 你可以试试

- 改这条标题（顶部输入框，已经换成 Lora 衬线字）
- 在下面正文继续写
- 写够 7 天连击 → 仪表盘的火焰会燃烧 🔥
- 按 ⌘+S / Ctrl+S 保存
- 点右上「全屏」进入沉浸式编辑

## Markdown 示例

Phase 3.1.polish A.2 上线后，下面这些会实时渲染成视觉元素。
现在先看裸文本。

**加粗** 和 *斜体* 是写作的两种节奏。

> 引文 — 把别人的话留在这里。

代码：

```python
def hello():
    print("Hello, PlutoLab")
```

链接：[PlutoLab on GitHub](https://github.com/Pluto731/plutolab)

## 不再需要这条？

随手删掉，开始写你的真笔记。"""


async def create_sample_note(db: AsyncSession, user_id: UUID) -> Note:
    """写入示例笔记并 commit. 调用方负责处理异常 (e.g. 不挡注册流程)."""
    note = Note(
        user_id=user_id,
        title=SAMPLE_NOTE_TITLE,
        content=SAMPLE_NOTE_CONTENT,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note
