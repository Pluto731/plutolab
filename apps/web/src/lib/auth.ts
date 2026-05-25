import { API_URL } from "@/lib/api";

export interface AuthUser {
  id: string;
  email: string;
  name: string | null;
  avatar: string | null;
  plan: string;
  email_verified: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}

const ACCESS_KEY = "pl_access";
const REFRESH_KEY = "pl_refresh";

export function storeTokens(t: TokenResponse): void {
  localStorage.setItem(ACCESS_KEY, t.access_token);
  localStorage.setItem(REFRESH_KEY, t.refresh_token);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function postAuth(path: string, body: unknown): Promise<TokenResponse> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail;
    throw new Error(typeof detail === "string" ? detail : "请求失败，请稍后重试");
  }
  return data as TokenResponse;
}

export function register(body: { email: string; password: string; name?: string }): Promise<TokenResponse> {
  return postAuth("/api/v1/auth/register", body);
}

export function login(body: { email: string; password: string }): Promise<TokenResponse> {
  return postAuth("/api/v1/auth/login", body);
}

export async function fetchMe(): Promise<AuthUser> {
  const token = getAccessToken();
  const res = await fetch(`${API_URL}/api/v1/auth/me`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    clearTokens();
    throw new Error("unauthorized");
  }
  return res.json() as Promise<AuthUser>;
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

export async function updateProfile(body: { name: string }): Promise<AuthUser> {
  const res = await fetch(`${API_URL}/api/v1/users/me`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "更新失败，请稍后重试"));
  return data as AuthUser;
}

export async function changePassword(body: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/users/me/password`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data: unknown = await res.json().catch(() => null);
    throw new Error(detailMessage(data, "修改失败，请稍后重试"));
  }
}

export async function uploadAvatar(file: File): Promise<AuthUser> {
  const token = getAccessToken();
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/v1/users/me/avatar`, {
    method: "POST",
    // 不要手动设 Content-Type, 让浏览器带上 multipart boundary
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "上传失败，请稍后重试"));
  return data as AuthUser;
}

/** 头像绝对 URL (后端存相对路径, 拼上 API base 以兼容 dev 跨端口)。 */
export function avatarUrl(user: { avatar: string | null }): string | null {
  if (!user.avatar) return null;
  return user.avatar.startsWith("http") ? user.avatar : `${API_URL}${user.avatar}`;
}
