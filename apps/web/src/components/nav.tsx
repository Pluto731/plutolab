"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ApiStatusDot } from "@/components/api-status-dot";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const navItems = [
  { name: "首页", href: "/" },
  { name: "笔记", href: "/notes" },
  { name: "RAG", href: "/rag" },
  { name: "评审", href: "/review" },
  { name: "Agent", href: "/agents" },
  { name: "画作", href: "/gallery" },
];

export function Nav() {
  const pathname = usePathname();
  const { scrollY } = useScroll();
  // 滚动 > 80px 时背景渐显
  const bgOpacity = useTransform(scrollY, [0, 80], [0, 1]);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <motion.header className="fixed inset-x-0 top-0 z-40">
      {/* 背景层 — 滚动时渐显 */}
      <motion.div
        style={{ opacity: bgOpacity }}
        aria-hidden
        className="absolute inset-0 border-b border-white/30 bg-white/50 backdrop-blur-xl
                   shadow-[inset_0_1px_0_0_rgba(255,255,255,0.6)]
                   dark:border-white/[0.06] dark:bg-black/30
                   dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]"
      />

      <div className="relative mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        {/* Logo */}
        <Link
          href="/"
          className="group flex items-center gap-2 select-none"
        >
          <span className="text-2xl transition-transform duration-300 group-hover:rotate-12 group-hover:scale-110">
            🪐
          </span>
          <span
            className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-pink-500 bg-clip-text text-lg font-bold text-transparent
                       dark:from-violet-400 dark:via-fuchsia-400 dark:to-pink-400"
          >
            PlutoLab
          </span>
        </Link>

        {/* 主导航 (桌面) */}
        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "relative px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "text-zinc-900 dark:text-zinc-100"
                    : "text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100",
                )}
              >
                {item.name}
                {active && (
                  <motion.div
                    layoutId="nav-active-pill"
                    className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
              </Link>
            );
          })}
        </nav>

        {/* 右侧 — API 状态 + 主题 + (移动端) 菜单按钮 */}
        <div className="flex items-center gap-3">
          <ApiStatusDot />
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            className="inline-flex size-10 items-center justify-center rounded-full border border-white/40 bg-white/30 text-zinc-700 backdrop-blur-xl transition-colors hover:bg-white/50 md:hidden dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-zinc-300 dark:hover:bg-white/[0.05]"
            aria-label={mobileOpen ? "关闭菜单" : "打开菜单"}
          >
            {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {/* 移动端展开菜单 */}
      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative mx-auto max-w-6xl px-6 pb-4 md:hidden"
        >
          <div
            className="flex flex-col gap-1 rounded-2xl border border-white/40 bg-white/70 p-2 backdrop-blur-2xl
                       shadow-[inset_0_1px_0_0_rgba(255,255,255,0.7)]
                       dark:border-white/[0.08] dark:bg-zinc-900/80
                       dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]"
          >
            {navItems.map((item) => {
              const active =
                item.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={cn(
                    "rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-gradient-to-r from-violet-500/20 to-fuchsia-500/20 text-zinc-900 dark:text-zinc-100"
                      : "text-zinc-600 hover:bg-zinc-100/60 dark:text-zinc-400 dark:hover:bg-zinc-800/60",
                  )}
                >
                  {item.name}
                </Link>
              );
            })}
          </div>
        </motion.div>
      )}
    </motion.header>
  );
}
