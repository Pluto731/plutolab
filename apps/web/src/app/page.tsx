import { ApiStatus } from "@/components/api-status";
import { Hero } from "@/components/hero";
import { ThemeToggle } from "@/components/theme-toggle";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-br from-zinc-50 via-zinc-50 to-violet-50 dark:from-black dark:via-zinc-950 dark:to-violet-950/40">
      {/* 右上角主题切换 */}
      <div className="fixed right-6 top-6 z-50">
        <ThemeToggle />
      </div>

      {/* Hero 区 (Phase 1.b.1) */}
      <Hero />

      {/* 功能展示区 — 占位, Phase 1.b.2 实现 */}
      <section
        id="features"
        className="relative border-t border-zinc-200/50 px-6 py-24 dark:border-zinc-800/50"
      >
        <div className="mx-auto max-w-md">
          <ApiStatus />
        </div>
        <div className="mx-auto mt-16 max-w-2xl text-center">
          <p className="text-sm text-zinc-500 dark:text-zinc-500">
            🚧 功能卡片即将上线 · Phase 1.b.2
          </p>
          <p className="mt-3 font-mono text-xs text-zinc-400 dark:text-zinc-600">
            Phase 1.b.1 — Hero 已重做 · Next.js 16 · React 19 · Tailwind v4 · Framer Motion 12
          </p>
        </div>
      </section>
    </main>
  );
}
