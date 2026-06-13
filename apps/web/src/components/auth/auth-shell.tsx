"use client";

import { Sparkles } from "lucide-react";
import Link from "next/link";

import { CharacterScene } from "@/components/auth/character-scene";

interface AuthShellProps {
  /** Forwarded to the character scene — email field focused. */
  typing?: boolean;
  /** Forwarded to the character scene — password field focused. */
  hidingEyes?: boolean;
  children: React.ReactNode;
}

export function AuthShell({ typing, hidingEyes, children }: AuthShellProps) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* 左栏：品牌 + 动画角色 (仅桌面) — 与全站品牌渐变一致 紫→品红→粉 */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-violet-600 via-fuchsia-500 to-pink-500 p-12 text-white lg:flex">
        <Link
          href="/"
          className="group relative z-20 flex w-fit items-center gap-2 text-lg font-semibold transition-opacity hover:opacity-80"
          aria-label="返回首页"
        >
          <span className="text-2xl transition-transform duration-300 group-hover:rotate-12 group-hover:scale-110">
            🪐
          </span>
          <span>PlutoLab</span>
        </Link>

        <div className="relative z-20 flex flex-1 items-end justify-center">
          <CharacterScene typing={typing} hidingEyes={hidingEyes} />
        </div>

        <div className="relative z-20 flex items-center gap-8 text-sm text-white/60">
          <a href="#" className="transition-colors hover:text-white">隐私政策</a>
          <a href="#" className="transition-colors hover:text-white">服务条款</a>
          <a href="#" className="transition-colors hover:text-white">联系我们</a>
        </div>

        {/* 装饰光斑 */}
        <div className="pointer-events-none absolute right-1/4 top-1/4 size-64 rounded-full bg-white/10 blur-3xl" />
        <div className="pointer-events-none absolute bottom-1/4 left-1/4 size-96 rounded-full bg-white/5 blur-3xl" />
      </div>

      {/* 右栏：表单 — 淡淡品牌色过渡, 和左栏同色系不割裂 */}
      <div className="flex items-center justify-center bg-gradient-to-br from-violet-50 via-background to-fuchsia-50/60 p-8 dark:from-violet-950/30 dark:via-background dark:to-fuchsia-950/20">
        <div className="w-full max-w-[420px]">
          {/* 移动端 logo — 可点击回主页 */}
          <Link
            href="/"
            className="group mb-12 flex items-center justify-center gap-2 text-lg font-semibold transition-opacity hover:opacity-80 lg:hidden"
            aria-label="返回首页"
          >
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 transition-transform group-hover:scale-105">
              <Sparkles className="size-4 text-primary" />
            </div>
            <span>PlutoLab</span>
          </Link>
          {children}
        </div>
      </div>
    </div>
  );
}
