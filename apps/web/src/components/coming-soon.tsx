"use client";

import { motion } from "framer-motion";
import { ArrowLeft, Construction, Sparkles } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

type Props = {
  emoji: string;
  title: string;
  phase: string;
  description: string;
  features: string[];
};

// 占位页 — 所有 Phase 3-7 路由共用此组件
export function ComingSoon({
  emoji,
  title,
  phase,
  description,
  features,
}: Props) {
  return (
    <section className="relative flex min-h-screen items-center justify-center px-6 py-32">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7 }}
        className="mx-auto max-w-2xl text-center"
      >
        {/* emoji 弹簧入场 */}
        <motion.div
          initial={{ scale: 0, rotate: -180 }}
          animate={{ scale: 1, rotate: 0 }}
          transition={{ type: "spring", duration: 1, delay: 0.1 }}
          className="text-7xl drop-shadow-lg select-none sm:text-8xl"
        >
          {emoji}
        </motion.div>

        {/* 标题 (流光渐变) */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-6 bg-[length:200%_auto] bg-clip-text text-5xl font-bold tracking-tight text-transparent
                     bg-gradient-to-r from-violet-600 via-fuchsia-500 via-pink-500 via-fuchsia-500 to-violet-600 animate-shine
                     dark:from-violet-400 dark:via-fuchsia-400 dark:via-pink-400 dark:via-fuchsia-400 dark:to-violet-400
                     sm:text-6xl"
        >
          {title}
        </motion.h1>

        {/* Phase 建设中标签 */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="mt-5 inline-flex items-center gap-2 rounded-full border border-white/40 bg-white/30 px-4 py-1.5 text-sm backdrop-blur-xl
                     shadow-[inset_0_1px_0_0_rgba(255,255,255,0.6)]
                     dark:border-white/[0.06] dark:bg-white/[0.03]
                     dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]"
        >
          <Construction className="size-4 text-amber-500" />
          <span className="font-medium text-zinc-700 dark:text-zinc-300">
            {phase} · 建设中
          </span>
        </motion.div>

        {/* 描述 */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="mt-6 text-lg leading-relaxed text-zinc-600 dark:text-zinc-400"
        >
          {description}
        </motion.p>

        {/* 即将上线的功能列表 — 苹果毛玻璃卡片 */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.7 }}
          className="mt-10 rounded-2xl border border-white/40 bg-white/30 p-6 text-left backdrop-blur-2xl
                     shadow-[inset_0_1px_0_0_rgba(255,255,255,0.6),0_20px_50px_-20px_rgba(0,0,0,0.1)]
                     dark:border-white/[0.06] dark:bg-white/[0.03]
                     dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_20px_50px_-20px_rgba(0,0,0,0.5)]"
        >
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold tracking-wider text-zinc-600 uppercase dark:text-zinc-400">
            <Sparkles className="size-4" />
            即将上线
          </h3>
          <ul className="space-y-3">
            {features.map((f, i) => (
              <motion.li
                key={f}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.4, delay: 0.9 + i * 0.08 }}
                className="flex items-start gap-2.5 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300"
              >
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500" />
                <span>{f}</span>
              </motion.li>
            ))}
          </ul>
        </motion.div>

        {/* 返回按钮 */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 1.2 }}
          className="mt-10"
        >
          <Button variant="outline" size="lg" className="group gap-2" asChild>
            <Link href="/">
              <ArrowLeft className="size-4 transition-transform group-hover:-translate-x-1" />
              回到首页
            </Link>
          </Button>
        </motion.div>
      </motion.div>
    </section>
  );
}
