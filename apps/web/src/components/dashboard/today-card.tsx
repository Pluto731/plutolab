"use client";

import { motion } from "framer-motion";
import { Feather } from "lucide-react";

import { CountUp } from "./count-up";

/**
 * 今日字数卡 — Phase 3.1.polish A.1-3
 * 显示用户今天编辑/创建的所有笔记 content 字符合计.
 */
export function TodayCard({ words }: { words: number }) {
  return (
    <div className="group relative h-full overflow-hidden rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md">
      {/* 背景晕染 */}
      <div className="pointer-events-none absolute -right-6 -top-6 size-36 rounded-full bg-violet-400/15 blur-3xl" />
      <div className="relative">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-500 shadow-md">
              <Feather className="size-4 text-white" />
            </div>
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              今日写作
            </p>
          </div>
          {words > 0 && (
            <motion.span
              initial={{ scale: 0.7, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.3, type: "spring" }}
              className="rounded-full bg-violet-500/10 px-2 py-0.5 text-xs font-medium text-violet-600 dark:text-violet-400"
            >
              在状态
            </motion.span>
          )}
        </div>

        <p className="text-3xl font-bold tabular-nums">
          {words === 0 ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            <CountUp value={words} />
          )}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          字 · 今天 {words === 0 ? "还没动笔" : "写了"}
        </p>
      </div>
    </div>
  );
}
