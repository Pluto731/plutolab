"use client";

import { motion } from "framer-motion";
import { ArrowDown, Github, Rocket } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

// 浮动球已抽到 <BackgroundOrbs />, Hero 只负责内容
export function Hero() {
  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-24">
      {/* 内容区 */}
      <div className="relative z-10 mx-auto flex max-w-4xl flex-col items-center text-center">
        {/* 🪐 行星: 弹簧入场 + 呼吸 idle */}
        <motion.div
          initial={{ scale: 0, rotate: -180, opacity: 0 }}
          animate={{ scale: 1, rotate: 0, opacity: 1 }}
          transition={{ type: "spring", duration: 1, delay: 0.1 }}
          className="animate-breathe text-8xl drop-shadow-lg select-none"
        >
          🪐
        </motion.div>

        {/* PlutoLab 大标题 — 流光 + hover 放大 */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.4 }}
          className="mt-8 cursor-pointer select-none bg-[length:200%_auto] bg-clip-text text-7xl font-bold tracking-tight text-transparent transition-all duration-500 ease-out hover:scale-110 hover:tracking-wider hover:drop-shadow-[0_0_40px_rgba(236,72,153,0.6)] sm:text-8xl
                     bg-gradient-to-r from-violet-600 via-fuchsia-500 via-pink-500 via-fuchsia-500 to-violet-600 animate-shine
                     dark:from-violet-400 dark:via-fuchsia-400 dark:via-pink-400 dark:via-fuchsia-400 dark:to-violet-400"
        >
          PlutoLab
        </motion.h1>

        {/* 副标题 */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="mt-6 text-2xl font-light text-zinc-700 dark:text-zinc-300 sm:text-3xl"
        >
          Your AI Workshop
        </motion.p>

        {/* 描述 */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="mt-4 max-w-xl text-base leading-relaxed text-zinc-500 dark:text-zinc-400 sm:text-lg"
        >
          一站式 AI 工作台
        </motion.p>

        {/* CTA 双按钮 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 1.0 }}
          className="mt-10 flex flex-wrap items-center justify-center gap-4"
        >
          <Button size="lg" className="group gap-2" asChild>
            <Link href="#features">
              <Rocket className="size-4 transition-transform group-hover:-translate-y-0.5 group-hover:rotate-12" />
              开始探索
            </Link>
          </Button>
          <Button size="lg" variant="outline" className="group gap-2" asChild>
            <Link
              href="https://github.com/Pluto731/plutolab"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Github className="size-4 transition-transform group-hover:scale-110" />
              GitHub
            </Link>
          </Button>
        </motion.div>
      </div>

      {/* 滚动提示 — 固定在 Hero 视口底部 */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1, y: [0, 8, 0] }}
        transition={{
          opacity: { duration: 1, delay: 1.5 },
          y: { duration: 2, repeat: Infinity, ease: "easeInOut", delay: 1.8 },
        }}
        className="pointer-events-none absolute bottom-8 left-1/2 z-10 -translate-x-1/2 font-mono text-xs text-zinc-400 dark:text-zinc-600"
      >
        <ArrowDown className="mx-auto mb-1 size-3" />
        scroll
      </motion.div>
    </section>
  );
}
