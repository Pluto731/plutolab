"use client";

import { motion } from "framer-motion";
import { ArrowUpRight, FileText, Plus } from "lucide-react";
import Link from "next/link";

import type { ActivityItem } from "@/lib/dashboard";

import { CountUp } from "./count-up";

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

/**
 * 笔记主面板 — Phase 3.1.polish A.1-3
 * 接替原 StatCard "笔记" 格子, 升级到 7×2 大卡:
 *   - 左侧: 笔记总数大字 + 跳转 "全部笔记" 按钮 + "新建" 按钮
 *   - 右侧: 最近 3 篇标题列表 (取自 recent_activities 里 kind=note)
 */
export function NotesPanel({
  count,
  recent,
}: {
  count: number;
  recent: ActivityItem[];
}) {
  const recentNotes = recent.filter((a) => a.kind === "note" && a.id).slice(0, 3);
  const empty = count === 0;

  return (
    <div className="group relative flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md">
      {/* 紫色辉光底纹 */}
      <div className="pointer-events-none absolute -left-10 -top-10 size-56 rounded-full bg-violet-400/15 blur-3xl" />
      <div className="pointer-events-none absolute -right-8 bottom-0 size-40 rounded-full bg-fuchsia-400/15 blur-3xl" />

      <div className="relative flex h-full flex-col gap-4 lg:flex-row">
        {/* 左 — 数字 + CTA */}
        <div className="flex flex-col justify-between lg:w-2/5">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 shadow-md">
                <FileText className="size-4 text-white" />
              </div>
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                笔记
              </p>
            </div>
            <p className="text-5xl font-bold tabular-nums leading-none">
              {empty ? <span className="text-muted-foreground">0</span> : <CountUp value={count} />}
            </p>
            <p className="mt-1.5 text-sm text-muted-foreground">
              {empty ? "想到就写。" : `${count} 条笔记`}
            </p>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href="/notes"
              className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 px-3.5 py-2 text-xs font-semibold text-white shadow-sm shadow-fuchsia-500/30 transition-all hover:brightness-110"
            >
              {empty ? <Plus className="size-3.5" /> : <ArrowUpRight className="size-3.5" />}
              {empty ? "写第一条" : "全部笔记"}
            </Link>
            {!empty && (
              <Link
                href="/notes"
                className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-background/50 px-3.5 py-2 text-xs font-semibold text-zinc-700 backdrop-blur transition-colors hover:bg-background/80 dark:text-zinc-200"
              >
                <Plus className="size-3.5" />
                新建
              </Link>
            )}
          </div>
        </div>

        {/* 右 — 最近 3 篇 */}
        <div className="flex flex-1 flex-col">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            最近
          </p>
          {recentNotes.length === 0 ? (
            <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-border bg-background/30 p-4 text-center text-xs text-muted-foreground">
              新建一条笔记后会出现在这
            </div>
          ) : (
            <ul className="space-y-1">
              {recentNotes.map((n, i) => (
                <motion.li
                  key={n.id}
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.15 + i * 0.06 }}
                >
                  <Link
                    href={`/notes/${n.id}`}
                    className="group/item flex items-center gap-2 rounded-lg px-2.5 py-2 transition-colors hover:bg-violet-500/10"
                  >
                    <span className="size-1.5 shrink-0 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500" />
                    <span className="line-clamp-1 flex-1 text-sm">{n.title}</span>
                    <span className="shrink-0 text-[10px] font-mono text-muted-foreground">
                      {relativeTime(n.timestamp)}
                    </span>
                    <ArrowUpRight className="size-3 text-muted-foreground opacity-0 transition-opacity group-hover/item:opacity-100" />
                  </Link>
                </motion.li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
