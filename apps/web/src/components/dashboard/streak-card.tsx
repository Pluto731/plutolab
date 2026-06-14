"use client";

import { motion } from "framer-motion";
import { Flame } from "lucide-react";

import { CountUp } from "./count-up";

/**
 * 写作连击卡 — Phase 3.1.polish A.1-3
 * 从今天往前数, 连续每天至少更新过一条笔记的天数. 灵感: Reflect / Streaks.
 */
export function StreakCard({ days }: { days: number }) {
  const lit = days > 0;
  return (
    <div className="group relative h-full overflow-hidden rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md">
      {/* 火焰晕 — 有连击时呼吸动 */}
      {lit && (
        <motion.div
          className="pointer-events-none absolute -right-8 -top-8 size-40 rounded-full bg-orange-400/25 blur-3xl"
          animate={{ scale: [1, 1.15, 1], opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <div className="relative">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className={`flex size-9 items-center justify-center rounded-xl shadow-md ${
                lit
                  ? "bg-gradient-to-br from-amber-400 via-orange-500 to-rose-500"
                  : "bg-gradient-to-br from-zinc-400 to-zinc-500"
              }`}
            >
              <Flame className="size-4 text-white" />
            </div>
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              连击
            </p>
          </div>
          {lit && days >= 7 && (
            <motion.span
              initial={{ scale: 0.7, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.3, type: "spring" }}
              className="rounded-full bg-orange-500/10 px-2 py-0.5 text-xs font-medium text-orange-600 dark:text-orange-400"
            >
              在状态 🔥
            </motion.span>
          )}
        </div>

        <div className="flex items-baseline gap-1.5">
          <p className="text-3xl font-bold tabular-nums">
            {lit ? <CountUp value={days} /> : <span className="text-muted-foreground">0</span>}
          </p>
          <p className="text-base text-muted-foreground">天</p>
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {lit ? "别让链条断。" : "今天写一条就开始。"}
        </p>
      </div>
    </div>
  );
}
