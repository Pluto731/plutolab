"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch, type HealthResponse } from "@/lib/api";

// 紧凑型: 右上角小胶囊, 含状态点 + "API" 标签
// hover 弹出 tooltip 显示 version + env
export function ApiStatusDot() {
  const { data, error, isLoading } = useQuery<HealthResponse>({
    queryKey: ["api-health"],
    queryFn: () => apiFetch<HealthResponse>("/api/v1/health"),
  });

  const status: "loading" | "ok" | "error" = isLoading
    ? "loading"
    : error
      ? "error"
      : "ok";

  const dotColors = {
    ok: "bg-emerald-500",
    error: "bg-rose-500",
    loading: "bg-amber-400",
  };
  const pingColors = {
    ok: "bg-emerald-400",
    error: "bg-rose-400",
    loading: "bg-amber-300",
  };

  const tooltip =
    status === "loading"
      ? "checking API…"
      : status === "error"
        ? `API offline · ${(error as Error)?.message ?? "unreachable"}`
        : `API · v${data?.version} · ${data?.env}`;

  return (
    <div className="group relative">
      {/* 胶囊 */}
      <div
        className="flex items-center gap-2 rounded-full border border-white/40 bg-white/30 px-3 py-1.5 backdrop-blur-xl
                   shadow-[inset_0_1px_0_0_rgba(255,255,255,0.7),0_4px_20px_-12px_rgba(0,0,0,0.1)]
                   dark:border-white/[0.06] dark:bg-white/[0.03]
                   dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_4px_20px_-12px_rgba(0,0,0,0.5)]"
      >
        <span className="relative flex size-2">
          {status !== "error" && (
            <span
              className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${pingColors[status]}`}
            />
          )}
          <span className={`relative inline-flex size-2 rounded-full ${dotColors[status]}`} />
        </span>
        <span className="font-mono text-xs text-zinc-700 dark:text-zinc-300">API</span>
      </div>

      {/* Tooltip on hover */}
      <div
        className="pointer-events-none absolute right-0 top-full mt-2 whitespace-nowrap rounded-md border border-white/40 bg-white/80 px-2.5 py-1.5 font-mono text-xs text-zinc-700 opacity-0 backdrop-blur-xl transition-opacity duration-200 group-hover:opacity-100
                   dark:border-white/[0.08] dark:bg-zinc-900/80 dark:text-zinc-200"
      >
        {tooltip}
      </div>
    </div>
  );
}
