import { ApiStatus } from "@/components/api-status";
import { BackgroundOrbs } from "@/components/background-orbs";
import { Features } from "@/components/features";
import { Hero } from "@/components/hero";
import { ThemeToggle } from "@/components/theme-toggle";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* 全局连贯背景 — 多层渐变 + 跟随鼠标的浮动光球, 整个页面共用一套 */}
      <BackgroundOrbs />

      {/* 右上角主题切换 (fixed, 滚动常驻) */}
      <div className="fixed right-6 top-6 z-50">
        <ThemeToggle />
      </div>

      {/* Hero (Phase 1.b.1) */}
      <Hero />

      {/* 功能卡片 (Phase 1.b.2) */}
      <Features />

      {/* API 状态 + 收尾 — 不要 border-t, 让背景延续 */}
      <section className="relative px-6 pb-24 pt-8">
        <div className="mx-auto max-w-md">
          <ApiStatus />
        </div>
        <p className="mx-auto mt-10 max-w-2xl text-center font-mono text-xs text-zinc-400 dark:text-zinc-600">
          Phase 1.b.2 — Features + 背景连贯 + 苹果毛玻璃 · Next.js 16 · Framer Motion 12
        </p>
      </section>
    </main>
  );
}
