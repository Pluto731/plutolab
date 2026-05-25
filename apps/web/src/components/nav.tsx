"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import { Menu, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiStatusDot } from "@/components/api-status-dot";
import { useAuthUser } from "@/components/auth/use-auth";
import { UserMenu } from "@/components/auth/user-menu";
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
  const { user, logout } = useAuthUser();
  const { scrollY } = useScroll();
  // 滚动 > 80px 时背景渐显
  const bgOpacity = useTransform(scrollY, [0, 80], [0, 1]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMac, setIsMac] = useState(false);

  useEffect(() => {
    setIsMac(/Mac|iPhone|iPod|iPad/i.test(navigator.platform));
  }, []);

  // 触发命令面板 — dispatch keyboard event 给全局监听器 (CommandPalette 监听 cmd/ctrl+k)
  const openCommand = () => {
    const evt = new KeyboardEvent("keydown", {
      key: "k",
      ctrlKey: !isMac,
      metaKey: isMac,
      bubbles: true,
    });
    document.dispatchEvent(evt);
  };

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

      <div className="relative flex h-16 items-center justify-between px-6 md:px-10 lg:px-16">
        {/* Logo (绝对位置 — 左) */}
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

        {/* 主导航 (桌面) — 绝对居中, 不受 logo/控件宽度影响 */}
        <nav className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-1 md:flex">
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

        {/* 右侧 — 搜索 + API 状态 + 主题 + (移动端) 菜单按钮 */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* ⌘K 命令面板触发按钮 — 移动端隐藏 (手机没物理键盘, ⌘K 无意义) */}
          <button
            type="button"
            onClick={openCommand}
            className="hidden h-9 items-center gap-2 rounded-full border border-white/40 bg-white/30 px-3 text-zinc-600 backdrop-blur-xl transition-colors hover:bg-white/50 hover:text-zinc-900 md:inline-flex dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-zinc-400 dark:hover:bg-white/[0.05] dark:hover:text-zinc-100"
            aria-label="打开命令面板"
          >
            <Search className="size-4" />
            <kbd className="font-mono text-xs">
              {isMac ? "⌘K" : "Ctrl K"}
            </kbd>
          </button>
          <ApiStatusDot />
          <ThemeToggle />
          {/* 登录态: 已登录显示用户菜单, 否则显示 登录/注册 入口 (桌面一对等高胶囊) */}
          {user ? (
            <UserMenu user={user} onLogout={logout} />
          ) : (
            <>
              <Link
                href="/login"
                className="hidden h-9 items-center rounded-full border border-white/40 bg-white/30 px-4 text-sm font-medium text-zinc-700 backdrop-blur-xl transition-colors hover:bg-white/50 hover:text-zinc-900 sm:inline-flex dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-zinc-200 dark:hover:bg-white/[0.08] dark:hover:text-white"
              >
                登录
              </Link>
              <Link
                href="/register"
                className="hidden h-9 items-center rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 px-4 text-sm font-medium text-white shadow-sm shadow-fuchsia-500/20 transition-all hover:shadow-md hover:brightness-110 sm:inline-flex"
              >
                注册
              </Link>
            </>
          )}
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
          className="relative px-6 pb-4 md:hidden"
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
            <div className="my-1 h-px bg-zinc-200/70 dark:bg-white/10" />
            {user ? (
              <>
                <div className="px-3 py-2">
                  <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
                    {user.name || user.email}
                  </p>
                  <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">{user.email}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setMobileOpen(false);
                    logout();
                  }}
                  className="rounded-lg px-3 py-2.5 text-left text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100/60 dark:text-zinc-300 dark:hover:bg-zinc-800/60"
                >
                  退出登录
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-lg px-3 py-2.5 text-sm font-medium text-zinc-600 transition-colors hover:bg-zinc-100/60 dark:text-zinc-300 dark:hover:bg-zinc-800/60"
                >
                  登录
                </Link>
                <Link
                  href="/register"
                  onClick={() => setMobileOpen(false)}
                  className="rounded-lg bg-gradient-to-r from-violet-600 to-fuchsia-500 px-3 py-2.5 text-center text-sm font-medium text-white"
                >
                  注册
                </Link>
              </>
            )}
          </div>
        </motion.div>
      )}
    </motion.header>
  );
}
