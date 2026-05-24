"use client";

import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { useEffect } from "react";

/**
 * 全屏背景层 — 跟随鼠标的浮动光球 + 多层径向渐变
 * fixed inset-0 全屏覆盖, -z-10 在内容之下
 * 整个站点共用一套, 滚动时光晕"穿透"到第二屏, 不会断开
 */
export function BackgroundOrbs() {
  const mouseX = useMotionValue(0.5);
  const mouseY = useMotionValue(0.5);

  const ball1X = useSpring(useTransform(mouseX, [0, 1], [-50, 50]), {
    damping: 30,
    stiffness: 40,
  });
  const ball1Y = useSpring(useTransform(mouseY, [0, 1], [-50, 50]), {
    damping: 30,
    stiffness: 40,
  });
  const ball2X = useSpring(useTransform(mouseX, [0, 1], [70, -70]), {
    damping: 40,
    stiffness: 25,
  });
  const ball2Y = useSpring(useTransform(mouseY, [0, 1], [70, -70]), {
    damping: 40,
    stiffness: 25,
  });
  const ball3X = useSpring(useTransform(mouseX, [0, 1], [-30, 30]), {
    damping: 25,
    stiffness: 60,
  });
  const ball3Y = useSpring(useTransform(mouseY, [0, 1], [30, -30]), {
    damping: 25,
    stiffness: 60,
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
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      {/* 底层渐变 — 自上而下色调微变, 不至于第二屏纯白/纯黑 */}
      <div className="absolute inset-0 bg-gradient-to-b from-zinc-50 via-violet-50/40 to-pink-50/30 dark:from-black dark:via-violet-950/30 dark:to-pink-950/25" />

      {/* 浮动球 1 — 紫色, 右上 */}
      <motion.div
        style={{ x: ball1X, y: ball1Y }}
        className="absolute -right-32 -top-32 size-[32rem] rounded-full bg-violet-400/35 blur-3xl dark:bg-violet-600/45"
      />
      {/* 浮动球 2 — 粉色, 左中 (跨第一二屏交界处, 制造连贯) */}
      <motion.div
        style={{ x: ball2X, y: ball2Y }}
        className="absolute left-[-15rem] top-[55vh] size-[36rem] rounded-full bg-fuchsia-400/30 blur-3xl dark:bg-fuchsia-600/35"
      />
      {/* 浮动球 3 — 中央上 */}
      <motion.div
        style={{ x: ball3X, y: ball3Y }}
        className="absolute left-1/2 top-1/4 size-[24rem] -translate-x-1/2 rounded-full bg-pink-300/25 blur-3xl dark:bg-pink-700/30"
      />
      {/* 浮动球 4 — 右下, 让 Features 区也有色彩, 第二屏不显空 */}
      <motion.div
        style={{ x: ball1X, y: ball2Y }}
        className="absolute -bottom-32 right-[-10rem] size-[30rem] rounded-full bg-violet-300/25 blur-3xl dark:bg-violet-700/30"
      />
    </div>
  );
}
