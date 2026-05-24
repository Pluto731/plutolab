"use client";

import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { ArrowDown, Github, Rocket } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export function Hero() {
  // 鼠标归一化位置 (0..1)
  const mouseX = useMotionValue(0.5);
  const mouseY = useMotionValue(0.5);

  // 三个球的视差幅度不同 → 制造深度
  // 用 spring 让跟随平滑, 不是死跟
  const ball1X = useSpring(useTransform(mouseX, [0, 1], [-40, 40]), {
    damping: 30,
    stiffness: 50,
  });
  const ball1Y = useSpring(useTransform(mouseY, [0, 1], [-40, 40]), {
    damping: 30,
    stiffness: 50,
  });
  const ball2X = useSpring(useTransform(mouseX, [0, 1], [60, -60]), {
    damping: 40,
    stiffness: 30,
  });
  const ball2Y = useSpring(useTransform(mouseY, [0, 1], [60, -60]), {
    damping: 40,
    stiffness: 30,
  });
  const ball3X = useSpring(useTransform(mouseX, [0, 1], [-20, 20]), {
    damping: 25,
    stiffness: 70,
  });
  const ball3Y = useSpring(useTransform(mouseY, [0, 1], [20, -20]), {
    damping: 25,
    stiffness: 70,
  });

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      mouseX.set(e.clientX / window.innerWidth);
      mouseY.set(e.clientY / window.innerHeight);
    };
    window.addEventListener("mousemove", handler);
    return () => window.removeEventListener("mousemove", handler);
  }, [mouseX, mouseY]);

  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-24">
      {/* 浮动渐变球 1 — 紫色, 右上 */}
      <motion.div
        style={{ x: ball1X, y: ball1Y }}
        className="pointer-events-none absolute -right-32 -top-32 size-96 rounded-full bg-violet-400/30 blur-3xl dark:bg-violet-600/40"
      />
      {/* 浮动渐变球 2 — 粉色, 左下, 反向跟随 */}
      <motion.div
        style={{ x: ball2X, y: ball2Y }}
        className="pointer-events-none absolute -bottom-40 -left-40 size-[28rem] rounded-full bg-fuchsia-400/25 blur-3xl dark:bg-fuchsia-600/30"
      />
      {/* 浮动渐变球 3 — 中央, 制造光晕层次 */}
      <motion.div
        style={{ x: ball3X, y: ball3Y }}
        className="pointer-events-none absolute left-1/2 top-1/3 size-72 -translate-x-1/2 rounded-full bg-pink-300/20 blur-3xl dark:bg-pink-700/25"
      />

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

        {/* PlutoLab 大标题 — 流光 + hover 放大 (Phase 1.b.0 已实现, 现在加入场动画) */}
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

      {/* 滚动提示 — 固定在 Hero 视口底部, 与内容解耦 */}
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
