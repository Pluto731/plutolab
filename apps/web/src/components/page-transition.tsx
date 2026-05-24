"use client";

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";

// 路由切换时入场动画 — fade + 微 slide
// (Next.js App Router RSC 下不做 exit, 只做 enter)
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <motion.div
      key={pathname}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
