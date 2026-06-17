import { API_URL } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

export type PomodoroKind = "focus" | "short_break" | "long_break";

export interface PomodoroWithTask {
  id: string;
  kind: PomodoroKind;
  planned_seconds: number;
  task_id: string | null;
  task_title: string | null;
  completed_at: string;
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  const base: Record<string, string> = { "Content-Type": "application/json" };
  if (token) base.Authorization = `Bearer ${token}`;
  return base;
}

export async function listPomodoros(days = 1): Promise<PomodoroWithTask[]> {
  const res = await fetch(`${API_URL}/api/v1/pomodoros?days=${days}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`pomodoros ${res.status}`);
  return res.json() as Promise<PomodoroWithTask[]>;
}

export async function recordPomodoro(body: {
  kind: PomodoroKind;
  planned_seconds: number;
  task_id?: string | null;
}): Promise<PomodoroWithTask> {
  const res = await fetch(`${API_URL}/api/v1/pomodoros`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail;
    throw new Error(typeof detail === "string" ? detail : `pomodoro ${res.status}`);
  }
  return data as PomodoroWithTask;
}
