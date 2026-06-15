import { API_URL } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

export interface TaskPublic {
  id: string;
  title: string;
  done: boolean;
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

export async function listTasks(): Promise<TaskPublic[]> {
  const res = await fetch(`${API_URL}/api/v1/tasks`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`tasks ${res.status}`);
  return res.json() as Promise<TaskPublic[]>;
}

export async function createTask(title: string): Promise<TaskPublic> {
  const res = await fetch(`${API_URL}/api/v1/tasks`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ title }),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "创建失败"));
  return data as TaskPublic;
}

export async function updateTask(
  id: string,
  body: { title?: string; done?: boolean },
): Promise<TaskPublic> {
  const res = await fetch(`${API_URL}/api/v1/tasks/${id}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "更新失败"));
  return data as TaskPublic;
}

export async function deleteTask(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/tasks/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok && res.status !== 204) {
    const data: unknown = await res.json().catch(() => null);
    throw new Error(detailMessage(data, "删除失败"));
  }
}
