"use client";

import { Sparkles } from "lucide-react";

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
      {/* 左栏：品牌 + 动画角色 (仅桌面) */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-violet-600 via-fuchsia-600 to-purple-700 p-12 text-white lg:flex">
        <div className="relative z-20 flex items-center gap-2 text-lg font-semibold">
          <span className="text-2xl">🪐</span>
          <span>PlutoLab</span>
        </div>

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

      {/* 右栏：表单 */}
      <div className="flex items-center justify-center bg-background p-8">
        <div className="w-full max-w-[420px]">
          {/* 移动端 logo */}
          <div className="mb-12 flex items-center justify-center gap-2 text-lg font-semibold lg:hidden">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10">
              <Sparkles className="size-4 text-primary" />
            </div>
            <span>PlutoLab</span>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
