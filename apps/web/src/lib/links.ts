import { API_URL } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

export interface LinkPublic {
  id: string;
  url: string;
  title: string;
  description: string | null;
  image_url: string | null;
  favicon_url: string | null;
  created_at: string;
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

export async function listLinks(): Promise<LinkPublic[]> {
  const res = await fetch(`${API_URL}/api/v1/links`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`links ${res.status}`);
  return res.json() as Promise<LinkPublic[]>;
}

export async function createLink(url: string): Promise<LinkPublic> {
  const res = await fetch(`${API_URL}/api/v1/links`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ url }),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "保存失败"));
  return data as LinkPublic;
}

export async function deleteLink(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/links/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok && res.status !== 204) {
    const data: unknown = await res.json().catch(() => null);
    throw new Error(detailMessage(data, "删除失败"));
  }
}
