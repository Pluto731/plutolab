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

export interface MessageResponse {
  message: string;
}

async function postMessage(path: string, body: unknown): Promise<MessageResponse> {
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
  return data as MessageResponse;
}

export function forgotPassword(email: string): Promise<MessageResponse> {
  return postMessage("/api/v1/auth/forgot-password", { email });
}

export function resetPassword(token: string, password: string): Promise<MessageResponse> {
  return postMessage("/api/v1/auth/reset-password", { token, password });
}

export function verifyEmail(token: string): Promise<MessageResponse> {
  return postMessage("/api/v1/auth/verify-email", { token });
}

export type ApiKeyProvider = "anthropic" | "openai" | "replicate";

export interface ApiKeyPublic {
  id: string;
  provider: ApiKeyProvider;
  key_preview: string;
  label: string | null;
  created_at: string;
}

export async function listApiKeys(): Promise<ApiKeyPublic[]> {
  const res = await fetch(`${API_URL}/api/v1/users/me/api-keys`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`API keys ${res.status}`);
  return res.json() as Promise<ApiKeyPublic[]>;
}

export async function createApiKey(body: {
  provider: ApiKeyProvider;
  key: string;
  label?: string;
}): Promise<ApiKeyPublic> {
  const res = await fetch(`${API_URL}/api/v1/users/me/api-keys`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "添加失败"));
  return data as ApiKeyPublic;
}

export async function deleteApiKey(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/users/me/api-keys/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok && res.status !== 204) {
    const data: unknown = await res.json().catch(() => null);
    throw new Error(detailMessage(data, "删除失败"));
  }
}

/** 新流程: 输邮箱+新密码 → 服务端发 6 位验证码邮件 (代码式) */
export function requestPasswordCode(
  email: string,
  password: string,
): Promise<MessageResponse> {
  return postMessage("/api/v1/auth/request-password-code", { email, password });
}

/** 新流程: 输验证码确认改密码 */
export function verifyPasswordCode(
  email: string,
  code: string,
): Promise<MessageResponse> {
  return postMessage("/api/v1/auth/verify-password-code", { email, code });
}

export async function sendVerification(): Promise<MessageResponse> {
  const res = await fetch(`${API_URL}/api/v1/auth/send-verification`, {
    method: "POST",
    headers: authHeaders(),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "发送失败，请稍后重试"));
  return data as MessageResponse;
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

export interface GitHubConfig {
  client_id: string;
  configured: boolean;
}

export async function githubConfig(): Promise<GitHubConfig> {
  const res = await fetch(`${API_URL}/api/v1/auth/github/config`);
  if (!res.ok) return { client_id: "", configured: false };
  return res.json() as Promise<GitHubConfig>;
}

export async function githubLogin(code: string, redirectUri: string): Promise<TokenResponse> {
  const res = await fetch(`${API_URL}/api/v1/auth/github`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, redirect_uri: redirectUri }),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new Error(detailMessage(data, "GitHub 登录失败"));
  return data as TokenResponse;
}

/** 发起 GitHub 授权跳转 (带 state 防 CSRF, 存 sessionStorage 供回调校验)。
 *  用 getRandomValues 而非 randomUUID: 后者在 http (非 secure context) 下不可用。 */
export function startGitHubAuth(clientId: string): void {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  const state = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  sessionStorage.setItem("gh_oauth_state", state);
  const redirectUri = `${window.location.origin}/auth/github/callback`;
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: "read:user user:email",
    state,
  });
  window.location.assign(`https://github.com/login/oauth/authorize?${params}`);
}
