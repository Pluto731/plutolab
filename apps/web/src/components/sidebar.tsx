"use client";

import { motion } from "framer-motion";
import {
  Bot,
  FileText,
  Home,
  ImageIcon,
  LogOut,
  Menu,
  ScrollText,
  Search,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiStatusDot } from "@/components/api-status-dot";
import { Avatar } from "@/components/auth/avatar";
import { useAuthUser } from "@/components/auth/use-auth";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

interface NavItem {
  name: string;
  href: string;
  icon: typeof Home;
  badge?: string;
}

const PRIMARY_ITEMS: NavItem[] = [
  { name: "工作台", href: "/dashboard", icon: Home },
  { name: "笔记", href: "/notes", icon: FileText },
  { name: "RAG", href: "/rag", icon: ScrollText, badge: "P4" },
  { name: "评审", href: "/review", icon: Sparkles, badge: "P5" },
  { name: "Agent", href: "/agents", icon: Bot, badge: "P6" },
  { name: "画作", href: "/gallery", icon: ImageIcon, badge: "P7" },
];

/**
 * 左侧主导航 sidebar — Linear / Notion 路线
 * - 桌面端 ≥ md: 固定 240px 左侧栏
 * - 移动端 < md: 抽屉, 汉堡按钮触发, 背景遮罩
 * - 营销首页 `/` 不显示 (全宽展示)
 */
export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthUser();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMac, setIsMac] = useState(false);

  useEffect(() => {
    setIsMac(/Mac|iPhone|iPod|iPad/i.test(navigator.platform));
  }, []);

  // 路由切换关闭抽屉
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // 营销首页不挂 sidebar
  if (pathname === "/") return null;

  const openCommand = () => {
    const evt = new KeyboardEvent("keydown", {
      key: "k",
      ctrlKey: !isMac,
      metaKey: isMac,
      bubbles: true,
    });
    document.dispatchEvent(evt);
    setMobileOpen(false);
  };

  return (
    <>
      {/* 移动端顶部胶囊条 — logo + 汉堡 (桌面端隐藏) */}
      <div className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-white/30 bg-white/60 px-4 backdrop-blur-xl md:hidden dark:border-white/[0.06] dark:bg-black/40">
        <Link href={user ? "/dashboard" : "/"} className="flex items-center gap-2">
          <span className="text-xl">🪐</span>
          <span className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-pink-500 bg-clip-text text-base font-bold text-transparent dark:from-violet-400 dark:via-fuchsia-400 dark:to-pink-400">
            PlutoLab
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label={mobileOpen ? "关闭菜单" : "打开菜单"}
            className="inline-flex size-9 items-center justify-center rounded-full border border-white/40 bg-white/30 text-zinc-700 backdrop-blur transition-colors hover:bg-white/60 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-zinc-200"
          >
            {mobileOpen ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
        </div>
      </div>

      {/* 移动端遮罩 */}
      {mobileOpen && (
        <button
          type="button"
          aria-label="关闭菜单"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm md:hidden"
        />
      )}

      {/* Sidebar 本体 */}
      <motion.aside
        initial={false}
        animate={{ x: 0 }}
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-white/30 bg-white/60 backdrop-blur-2xl",
          "shadow-[inset_-1px_0_0_0_rgba(255,255,255,0.4)] dark:border-white/[0.06] dark:bg-black/40 dark:shadow-[inset_-1px_0_0_0_rgba(255,255,255,0.04)]",
          // 移动端: 默认完全藏在屏幕左外侧, mobileOpen 时滑入
          mobileOpen
            ? "translate-x-0"
            : "-translate-x-full md:translate-x-0",
          "transition-transform duration-300 ease-out",
        )}
      >
        {/* Logo */}
        <Link
          href={user ? "/dashboard" : "/"}
          className="group flex items-center gap-2 px-5 py-5 select-none"
        >
          <span className="text-2xl transition-transform duration-300 group-hover:rotate-12 group-hover:scale-110">
            🪐
          </span>
          <span className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-pink-500 bg-clip-text text-lg font-bold text-transparent dark:from-violet-400 dark:via-fuchsia-400 dark:to-pink-400">
            PlutoLab
          </span>
        </Link>

        {/* 搜索 (触发命令面板) */}
        <div className="px-3 pb-3">
          <button
            type="button"
            onClick={openCommand}
            aria-label="打开命令面板"
            className="flex h-9 w-full items-center gap-2 rounded-lg border border-white/40 bg-white/40 px-3 text-sm text-zinc-500 transition-colors hover:bg-white/70 hover:text-zinc-700 dark:border-white/[0.06] dark:bg-white/[0.03] dark:text-zinc-400 dark:hover:bg-white/[0.06] dark:hover:text-zinc-100"
          >
            <Search className="size-4" />
            <span className="flex-1 text-left">搜索…</span>
            <kbd className="font-mono text-[10px] text-muted-foreground">
              {isMac ? "⌘K" : "Ctrl K"}
            </kbd>
          </button>
        </div>

        {/* 主导航 */}
        <nav className="flex-1 overflow-y-auto px-3 pb-3">
          <p className="px-3 pb-1.5 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            主导航
          </p>
          <ul className="space-y-0.5">
            {PRIMARY_ITEMS.map((item) => {
              const active = pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={cn(
                      "group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                      active
                        ? "text-zinc-900 dark:text-zinc-100"
                        : "text-zinc-600 hover:bg-zinc-100/60 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-white/[0.05] dark:hover:text-zinc-100",
                    )}
                  >
                    {active && (
                      <motion.span
                        layoutId="sidebar-active-bg"
                        className="absolute inset-0 -z-0 rounded-lg bg-gradient-to-r from-violet-500/15 to-fuchsia-500/15 ring-1 ring-violet-500/20 dark:from-violet-400/20 dark:to-fuchsia-400/20 dark:ring-violet-400/25"
                        transition={{ type: "spring", stiffness: 400, damping: 32 }}
                      />
                    )}
                    <Icon
                      className={cn(
                        "relative size-4 shrink-0",
                        active && "text-violet-600 dark:text-violet-400",
                      )}
                    />
                    <span className="relative flex-1 truncate">{item.name}</span>
                    {item.badge && (
                      <span className="relative rounded bg-zinc-100 px-1.5 py-0.5 text-[9px] font-semibold tracking-wider text-zinc-500 dark:bg-white/[0.06] dark:text-zinc-400">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* 底部用户区 */}
        <div className="border-t border-white/30 px-3 py-3 dark:border-white/[0.06]">
          {user ? (
            <UserBlock user={user} onLogout={logout} />
          ) : (
            <div className="space-y-1.5">
              <Link
                href="/login"
                className="flex h-9 w-full items-center justify-center rounded-lg border border-white/40 bg-white/40 text-sm font-medium text-zinc-700 transition-colors hover:bg-white/70 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-zinc-200 dark:hover:bg-white/[0.08]"
              >
                登录
              </Link>
              <Link
                href="/register"
                className="flex h-9 w-full items-center justify-center rounded-lg bg-gradient-to-r from-violet-500 to-fuchsia-500 text-sm font-medium text-white shadow-sm shadow-fuchsia-500/30 transition-all hover:brightness-110"
              >
                注册
              </Link>
            </div>
          )}
          {/* 状态条 — 主题 + API */}
          <div className="mt-3 flex items-center justify-between px-2 pt-2 border-t border-white/20 dark:border-white/[0.04]">
            <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <ApiStatusDot />
              <span>API</span>
            </div>
            <ThemeToggle />
          </div>
        </div>
      </motion.aside>
    </>
  );
}

function UserBlock({
  user,
  onLogout,
}: {
  user: NonNullable<ReturnType<typeof useAuthUser>["user"]>;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2.5 rounded-lg p-1.5 text-left transition-colors hover:bg-zinc-100/60 dark:hover:bg-white/[0.05]"
      >
        <Avatar user={user} className="size-8 text-xs" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
            {user.name || "未命名"}
          </p>
          <p className="truncate text-xs text-muted-foreground">{user.email}</p>
        </div>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-xl border border-white/40 bg-white/90 p-1 shadow-lg backdrop-blur-2xl dark:border-white/[0.08] dark:bg-zinc-900/90">
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100/70 dark:text-zinc-200 dark:hover:bg-white/[0.06]"
            >
              <Settings className="size-4" />
              个人设置
            </Link>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onLogout();
              }}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100/70 dark:text-zinc-200 dark:hover:bg-white/[0.06]"
            >
              <LogOut className="size-4" />
              退出登录
            </button>
          </div>
        </>
      )}
    </div>
  );
}
