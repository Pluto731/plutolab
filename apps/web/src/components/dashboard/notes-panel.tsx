"use client";

import { motion } from "framer-motion";
import { ArrowUpRight, Feather, FileText, Flame, Plus } from "lucide-react";
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
 * 笔记主面板 — Phase 3.1.polish A.1-3 (合并版)
 * 5×2 竖向卡, 含: 头部 + Today/Streak 双 chip + 总数 + 最近 2 篇 + CTA.
 * 替代原独立的 TodayCard / StreakCard, 减一行 bento 高度.
 */
export function NotesPanel({
  count,
  recent,
  todayWords,
  streakDays,
}: {
  count: number;
  recent: ActivityItem[];
  todayWords: number;
  streakDays: number;
}) {
  const recentNotes = recent.filter((a) => a.kind === "note" && a.id).slice(0, 2);
  const empty = count === 0;
  const streakHot = streakDays >= 7;

  return (
    <div className="group relative flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md">
      {/* 紫色辉光底纹 */}
      <div className="pointer-events-none absolute -left-10 -top-10 size-48 rounded-full bg-violet-400/15 blur-3xl" />
      <div className="pointer-events-none absolute -right-8 bottom-0 size-36 rounded-full bg-fuchsia-400/15 blur-3xl" />
      {/* 连击 ≥7 时火焰呼吸 */}
      {streakHot && (
        <motion.div
          className="pointer-events-none absolute right-2 top-2 size-24 rounded-full bg-orange-400/25 blur-2xl"
          animate={{ scale: [1, 1.15, 1], opacity: [0.55, 0.9, 0.55] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />
      )}

      <div className="relative flex h-full flex-col">
        {/* Header — 图标 + 标签 */}
        <div className="mb-3 flex items-center gap-2">
          <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 shadow-md">
            <FileText className="size-4 text-white" />
          </div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            笔记
          </p>
        </div>

        {/* 今日 + 连击 chip 行 */}
        <div className="mb-4 flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-500/20 bg-violet-500/10 px-2.5 py-1 text-xs font-medium text-violet-700 dark:text-violet-300">
            <Feather className="size-3" />
            今日 <span className="tabular-nums">{todayWords}</span> 字
          </span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
              streakHot
                ? "border-orange-500/30 bg-gradient-to-r from-amber-500/15 to-orange-500/15 text-orange-700 dark:text-orange-300"
                : streakDays > 0
                  ? "border-orange-500/20 bg-orange-500/10 text-orange-700 dark:text-orange-300"
                  : "border-border bg-muted/50 text-muted-foreground"
            }`}
          >
            <Flame className="size-3" />
            连击 <span className="tabular-nums">{streakDays}</span> 天
          </span>
        </div>

        {/* 总数大字 */}
        <div>
          <p className="text-4xl font-bold tabular-nums leading-none">
            {empty ? (
              <span className="text-muted-foreground">0</span>
            ) : (
              <CountUp value={count} />
            )}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {empty ? "想到就写。" : `${count} 条笔记`}
          </p>
        </div>

        {/* 最近 2 篇 */}
        <div className="mt-4 min-h-0 flex-1">
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            最近
          </p>
          {recentNotes.length === 0 ? (
            <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-border bg-background/30 p-3 text-center text-xs text-muted-foreground">
              新建一条笔记后会出现在这
            </div>
          ) : (
            <ul className="space-y-0.5">
              {recentNotes.map((n, i) => (
                <motion.li
                  key={n.id}
                  initial={{ opacity: 0, x: 6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.12 + i * 0.05 }}
                >
                  <Link
                    href={`/notes/${n.id}`}
                    className="group/item flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-violet-500/10"
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

        {/* CTA */}
        <div className="mt-3 flex gap-2">
          <Link
            href="/notes"
            className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 px-3 py-2 text-xs font-semibold text-white shadow-sm shadow-fuchsia-500/30 transition-all hover:brightness-110"
          >
            {empty ? <Plus className="size-3.5" /> : <ArrowUpRight className="size-3.5" />}
            {empty ? "写第一条" : "全部笔记"}
          </Link>
          {!empty && (
            <Link
              href="/notes"
              className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-background/50 px-3 py-2 text-xs font-semibold text-zinc-700 backdrop-blur transition-colors hover:bg-background/80 dark:text-zinc-200"
              aria-label="新建笔记"
            >
              <Plus className="size-3.5" />
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
