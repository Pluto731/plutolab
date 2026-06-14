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

/** 兜底"载入示例笔记" — 注册时后端已自动建一条, 此处给"删了想再要"用.
 *  模板内容由后端 `core/sample_note.py` 维护 (source of truth).
 */
export async function createSampleNote(): Promise<NotePublic> {
  const res = await fetch(`${API_URL}/api/v1/notes/sample`, {
    method: "POST",
    headers: authHeaders(),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "载入示例失败"));
  return data as NotePublic;
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
