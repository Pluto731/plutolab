import { API_URL } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

export interface ActivityItem {
  kind: "note" | "task" | "rag" | "image" | "agent" | "chat";
  title: string;
  timestamp: string;
  /** 可跳转实体的 id (笔记/任务). 展示性活动可缺省. */
  id?: string;
}

export interface RecentTaskItem {
  id: string;
  title: string;
}

export interface DashboardSummary {
  is_authenticated: boolean;
  notes_count: number;
  tasks_count: number;
  rag_docs_count: number;
  agents_count: number;
  images_count: number;
  tokens_this_month: number;
  tokens_limit: number;
  today_words: number;
  writing_streak: number;
  recent_activities: ActivityItem[];
  recent_tasks: RecentTaskItem[];
}

export async function fetchDashboard(): Promise<DashboardSummary> {
  const token = getAccessToken();
  const res = await fetch(`${API_URL}/api/v1/dashboard/summary`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Dashboard ${res.status}`);
  return res.json() as Promise<DashboardSummary>;
}
