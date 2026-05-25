"use client";

import { LogOut, Settings } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import type { AuthUser } from "@/lib/auth";

export function UserMenu({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const display = user.name || user.email;
  const initial = display.charAt(0).toUpperCase();

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 items-center gap-2 rounded-full border border-white/40 bg-white/30 pl-1 pr-3 backdrop-blur-xl transition-colors hover:bg-white/50 dark:border-white/[0.08] dark:bg-white/[0.04] dark:hover:bg-white/[0.08]"
        aria-label="用户菜单"
      >
        <span className="flex size-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 text-xs font-semibold text-white">
          {initial}
        </span>
        <span className="hidden max-w-[8rem] truncate text-sm font-medium text-zinc-700 sm:inline dark:text-zinc-200">
          {display}
        </span>
      </button>

      {open && (
        <>
          {/* 点击外部关闭 */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            className="absolute right-0 top-full z-50 mt-2 w-60 overflow-hidden rounded-2xl border border-white/40 bg-white/80 p-1.5 backdrop-blur-2xl shadow-lg
                       dark:border-white/[0.08] dark:bg-zinc-900/85"
          >
            <div className="px-3 py-2">
              <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
                {user.name || "未命名"}
              </p>
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            </div>
            <div className="my-1 h-px bg-zinc-200/70 dark:bg-white/10" />
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100/70 dark:text-zinc-200 dark:hover:bg-white/[0.06]"
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
