// 注意 ?? 而非 ||: 生产 NEXT_PUBLIC_API_URL="" 表示同源相对路径, || 会错误回退到 localhost:8000
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export type HealthResponse = {
  status: string;
  version: string;
  env: string;
};
