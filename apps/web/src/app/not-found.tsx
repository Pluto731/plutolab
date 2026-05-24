"use client";

import { motion } from "framer-motion";
import { ArrowLeft, Telescope } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

// 全局 404 页 — 飘走的行星 + 流光 404 + 双 CTA
export default function NotFound() {
  return (
    <section className="relative flex min-h-screen items-center justify-center px-6 py-32">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7 }}
        className="mx-auto max-w-2xl text-center"
      >
        {/* 飘走的行星 — 持续上下浮动 + 摇摆 */}
        <motion.div
          animate={{
            y: [0, -20, 0],
            rotate: [0, 8, -8, 0],
          }}
          transition={{
            duration: 6,
            repeat: Infinity,
            ease: "easeInOut",
          }}
          className="text-9xl drop-shadow-2xl select-none"
        >
          🪐
        </motion.div>

        {/* 404 大数字 — 流光渐变 */}
        <motion.h1
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.2, type: "spring" }}
          className="mt-6 bg-[length:200%_auto] bg-clip-text text-[8rem] leading-none font-black tracking-tighter text-transparent
                     bg-gradient-to-r from-violet-600 via-fuchsia-500 via-pink-500 via-fuchsia-500 to-violet-600 animate-shine
                     dark:from-violet-400 dark:via-fuchsia-400 dark:via-pink-400 dark:via-fuchsia-400 dark:to-violet-400
                     sm:text-[10rem]"
        >
          404
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="mt-4 text-2xl font-light text-zinc-700 dark:text-zinc-300 sm:text-3xl"
        >
          Lost in space?
        </motion.p>

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="mt-4 text-base text-zinc-500 dark:text-zinc-400"
        >
          这个页面飘到柯伊伯带外面去了 🌌 别担心, 回头还能找到路
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.9 }}
          className="mt-12 flex flex-wrap items-center justify-center gap-4"
        >
          <Button size="lg" className="group gap-2" asChild>
            <Link href="/">
              <ArrowLeft className="size-4 transition-transform group-hover:-translate-x-1" />
              回到首页
            </Link>
          </Button>
          <Button size="lg" variant="outline" className="group gap-2" asChild>
            <Link href="/notes">
              <Telescope className="size-4 transition-transform group-hover:rotate-12" />
              探索其他模块
            </Link>
          </Button>
        </motion.div>
      </motion.div>
    </section>
  );
}
