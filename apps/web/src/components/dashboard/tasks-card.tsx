"use client";

import { ArrowUpRight, CheckSquare, Circle } from "lucide-react";
import Link from "next/link";

import type { RecentTaskItem } from "@/lib/dashboard";

interface TasksCardProps {
  count: number;
  recent: RecentTaskItem[];
}

export function TasksCard({ count, recent }: TasksCardProps) {
  return (
    <div className="group relative h-full overflow-hidden rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 shadow-md">
          <CheckSquare className="size-4 text-white" />
        </div>
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          待办
        </p>
        <span className="ml-auto text-2xl font-bold tabular-nums">{count}</span>
      </div>

      {recent.length === 0 ? (
        <div className="flex h-20 flex-col items-center justify-center text-center">
          <p className="text-sm text-muted-foreground">
            {count === 0 ? "全部完成 ✨" : "暂无待办"}
          </p>
          <Link
            href="/tasks"
            className="mt-1 inline-flex items-center gap-1 text-xs text-emerald-600 transition-colors hover:text-emerald-500 dark:text-emerald-400"
          >
            打开任务页 <ArrowUpRight className="size-3" />
          </Link>
        </div>
      ) : (
        <>
          <ul className="space-y-1.5">
            {recent.slice(0, 3).map((t) => (
              <li key={t.id}>
                <Link
                  href="/tasks"
                  className="group/item flex items-center gap-2 rounded-lg px-1.5 py-1 text-sm transition-colors hover:bg-emerald-500/10"
                >
                  <Circle className="size-3.5 shrink-0 text-emerald-500" />
                  <span className="line-clamp-1 flex-1">{t.title}</span>
                  <ArrowUpRight className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover/item:opacity-100" />
                </Link>
              </li>
            ))}
          </ul>
          {count > 3 && (
            <Link
              href="/tasks"
              className="mt-2 inline-flex items-center gap-1 px-1.5 text-xs text-muted-foreground transition-colors hover:text-emerald-600 dark:hover:text-emerald-400"
            >
              查看其余 {count - 3} 条 <ArrowUpRight className="size-3" />
            </Link>
          )}
        </>
      )}
    </div>
  );
}
