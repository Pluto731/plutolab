import { ApiStatus } from "@/components/api-status";
import { ThemeToggle } from "@/components/theme-toggle";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-br from-zinc-50 via-zinc-50 to-violet-50 dark:from-black dark:via-zinc-950 dark:to-violet-950/40">
      <div className="pointer-events-none absolute -right-32 -top-32 size-96 rounded-full bg-violet-400/20 blur-3xl dark:bg-violet-600/30" />
      <div className="pointer-events-none absolute -bottom-32 -left-32 size-96 rounded-full bg-fuchsia-400/15 blur-3xl dark:bg-fuchsia-600/20" />

      <div className="absolute right-6 top-6 z-10">
        <ThemeToggle />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-4xl flex-col items-center justify-center px-6 py-24">
        <div className="animate-breathe text-7xl drop-shadow-lg select-none">🪐</div>

        {/* 流光 + hover 放大 + 多色循环渐变, 让字体活过来 */}
        <h1
          className="group mt-6 cursor-pointer select-none bg-[length:200%_auto] bg-clip-text text-7xl font-bold tracking-tight text-transparent transition-all duration-500 ease-out hover:scale-110 hover:tracking-wider hover:drop-shadow-[0_0_40px_rgba(236,72,153,0.6)]
                     bg-gradient-to-r from-violet-600 via-fuchsia-500 via-pink-500 via-fuchsia-500 to-violet-600 animate-shine
                     dark:from-violet-400 dark:via-fuchsia-400 dark:via-pink-400 dark:via-fuchsia-400 dark:to-violet-400"
        >
          PlutoLab
        </h1>

        <p className="mt-4 text-center text-xl text-zinc-600 dark:text-zinc-400">
          Your AI Workshop
        </p>

        <p className="mt-2 text-center text-sm text-zinc-500 dark:text-zinc-500">
          一站式 AI 工作台 · 搭建中 ✨
        </p>

        <div className="mt-12 w-full max-w-md">
          <ApiStatus />
        </div>

        <div className="mt-16 text-center text-xs text-zinc-500 dark:text-zinc-600">
          <p className="font-mono">Phase 0.4 — Frontend skeleton</p>
          <p className="mt-1.5">Next.js 16 · React 19 · Tailwind v4 · TS 5</p>
        </div>
      </div>
    </main>
  );
}
