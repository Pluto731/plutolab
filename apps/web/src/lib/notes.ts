import { API_URL } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

export interface NoteSummary {
  id: string;
  title: string;
  excerpt: string;
  created_at: string;
  updated_at: string;
}

export interface NotePublic {
  id: string;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  const base: Record<string, string> = { "Content-Type": "application/json" };
  if (token) base.Authorization = `Bearer ${token}`;
  return base;
}

function detailMessage(data: unknown, fallback: string): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : fallback;
}

export async function listNotes(): Promise<NoteSummary[]> {
  const res = await fetch(`${API_URL}/api/v1/notes`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`notes ${res.status}`);
  return res.json() as Promise<NoteSummary[]>;
}

export async function getNote(id: string): Promise<NotePublic> {
  const res = await fetch(`${API_URL}/api/v1/notes/${id}`, { headers: authHeaders() });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "加载失败"));
  return data as NotePublic;
}

export async function createNote(body: {
  title: string;
  content?: string;
}): Promise<NotePublic> {
  const res = await fetch(`${API_URL}/api/v1/notes`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "创建失败"));
  return data as NotePublic;
}

export async function updateNote(
  id: string,
  body: { title?: string; content?: string },
): Promise<NotePublic> {
  const res = await fetch(`${API_URL}/api/v1/notes/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "保存失败"));
  return data as NotePublic;
}

/** 预置欢迎笔记模板 — Phase 3.1.polish A.1-4
 *  让新用户能立刻看到字体 / 配色 / 三栏布局长什么样.
 *  Markdown 在 textarea 是原文, 实时渲染 A.2 上线后自动美化此条.
 */
export const SAMPLE_NOTE_TITLE = "欢迎来到 PlutoLab 笔记";

const SAMPLE_NOTE_CONTENT = `这是一条示例笔记，展示笔记功能怎么用。

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

\`\`\`python
def hello():
    print("Hello, PlutoLab")
\`\`\`

链接：[PlutoLab on GitHub](https://github.com/Pluto731/plutolab)

## 不再需要这条？

随手删掉，开始写你的真笔记。`;

export function createSampleNote(): Promise<NotePublic> {
  return createNote({ title: SAMPLE_NOTE_TITLE, content: SAMPLE_NOTE_CONTENT });
}

export async function deleteNote(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/notes/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok && res.status !== 204) {
    const data: unknown = await res.json().catch(() => null);
    throw new Error(detailMessage(data, "删除失败"));
  }
}
