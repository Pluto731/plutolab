"use client";

import { motion } from "framer-motion";
import { Zap } from "lucide-react";

import { CountUp } from "./count-up";

interface TokensCardProps {
  used: number;
  limit: number;
}

export function TokensCard({ used, limit }: TokensCardProps) {
  const pct = limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div className="group relative h-full overflow-hidden rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-md">
            <Zap className="size-4 text-white" />
          </div>
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            本月 Token
          </p>
        </div>
        <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400">
          {pct}%
        </span>
      </div>

      <div className="mb-3">
        <p className="text-3xl font-bold tabular-nums">
          <CountUp value={used} />
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          /{" "}
          <span className="tabular-nums">{limit.toLocaleString()}</span> 上限
        </p>
      </div>

      {/* 进度条 — 渐变填充 + 入场动画 */}
      <div className="relative h-2 overflow-hidden rounded-full bg-muted">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-amber-400 via-orange-500 to-rose-500"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
        />
      </div>
    </div>
  );
}
