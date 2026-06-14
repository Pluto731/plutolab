"use client";

import { Activity, ArrowUpRight, Bot, FileText, ImageIcon, MessageSquare, ScrollText } from "lucide-react";
import Link from "next/link";

import type { ActivityItem } from "@/lib/dashboard";

const KIND_META: Record<
  ActivityItem["kind"],
  { icon: typeof FileText; color: string; label: string }
> = {
  note: { icon: FileText, color: "from-violet-500 to-fuchsia-500", label: "笔记" },
  task: { icon: ScrollText, color: "from-emerald-500 to-teal-500", label: "任务" },
  rag: { icon: ScrollText, color: "from-blue-500 to-cyan-500", label: "文档" },
  image: { icon: ImageIcon, color: "from-pink-500 to-rose-500", label: "图像" },
  agent: { icon: Bot, color: "from-indigo-500 to-violet-500", label: "Agent" },
  chat: { icon: MessageSquare, color: "from-amber-500 to-orange-500", label: "对话" },
};

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  const diff = Math.max(0, Date.now() - t);
  const min = Math.floor(diff / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const d = Math.floor(hr / 24);
  return `${d} 天前`;
}

export function ActivitiesCard({ items }: { items: ActivityItem[] }) {
  return (
    <div className="relative h-full overflow-hidden rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md">
      <div className="mb-4 flex items-center gap-2">
        <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-slate-500 to-zinc-600 shadow-md">
          <Activity className="size-4 text-white" />
        </div>
        <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
          最近活动
        </h2>
      </div>

      {items.length === 0 ? (
        <div className="flex h-32 flex-col items-center justify-center text-center">
          <p className="text-sm text-muted-foreground">这里还很安静</p>
          <p className="mt-1 text-xs text-muted-foreground/70">
            创建笔记、上传文档、发起对话后，活动会出现在这里
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((a, i) => {
            const meta = KIND_META[a.kind] ?? KIND_META.note;
            const Icon = meta.icon;
            // 笔记类活动有 id 时可跳转到编辑页
            const href = a.kind === "note" && a.id ? `/notes/${a.id}` : null;
            const inner = (
              <>
                <div
                  className={`flex size-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ${meta.color} shadow-sm`}
                >
                  <Icon className="size-4 text-white" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{a.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {meta.label} · {relativeTime(a.timestamp)}
                  </p>
                </div>
                {href && (
                  <ArrowUpRight className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover/row:opacity-100" />
                )}
              </>
            );
            return (
              <li key={i}>
                {href ? (
                  <Link
                    href={href}
                    className="group/row flex items-center gap-3 rounded-xl px-2 py-1.5 transition-colors hover:bg-muted/50"
                  >
                    {inner}
                  </Link>
                ) : (
                  <div className="group/row flex items-center gap-3 rounded-xl px-2 py-1.5 transition-colors hover:bg-muted/50">
                    {inner}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
