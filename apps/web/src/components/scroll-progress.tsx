"use client";

import { motion, useScroll, useSpring } from "framer-motion";

// 顶部 2px 进度条 — 流光渐变 + spring 平滑跟随滚动
export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001,
  });

  return (
    <motion.div
      style={{ scaleX }}
      className="fixed inset-x-0 top-0 z-[60] h-0.5 origin-left bg-gradient-to-r from-violet-500 via-fuchsia-500 to-pink-500"
    />
  );
}
