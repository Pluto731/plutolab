"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { apiFetch, type HealthResponse } from "@/lib/api";

export function ApiStatus() {
  const { data, error, isLoading } = useQuery<HealthResponse>({
    queryKey: ["api-health"],
    queryFn: () => apiFetch<HealthResponse>("/api/v1/health"),
  });

  const status = isLoading ? "loading" : error ? "error" : "ok";

  return (
    <div
      className="rounded-2xl border border-white/40 bg-white/30 p-5 backdrop-blur-2xl
                 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.7),0_8px_30px_-12px_rgba(0,0,0,0.08)]
                 transition
                 dark:border-white/[0.06] dark:bg-white/[0.03]
                 dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_8px_30px_-12px_rgba(0,0,0,0.5)]"
    >
      <div className="flex items-center gap-3">
        {status === "loading" && (
          <Loader2 className="size-5 shrink-0 animate-spin text-zinc-400" />
        )}
        {status === "ok" && (
          <CheckCircle2 className="size-5 shrink-0 text-emerald-500" />
        )}
        {status === "error" && (
          <XCircle className="size-5 shrink-0 text-rose-500" />
        )}
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
            Backend API
          </span>
          <span className="font-mono text-xs text-zinc-500 dark:text-zinc-400">
            {status === "loading" && "checking…"}
            {status === "ok" && data && `v${data.version} · ${data.env}`}
            {status === "error" && (error as Error).message}
          </span>
        </div>
      </div>
    </div>
  );
}
