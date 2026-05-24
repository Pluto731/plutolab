import { ApiStatusDot } from "@/components/api-status-dot";
import { BackgroundOrbs } from "@/components/background-orbs";
import { Features } from "@/components/features";
import { Footer } from "@/components/footer";
import { Hero } from "@/components/hero";
import { ScrollProgress } from "@/components/scroll-progress";
import { ThemeToggle } from "@/components/theme-toggle";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* 全局连贯背景 — 多层渐变 + 跟随鼠标的浮动光球 */}
      <BackgroundOrbs />

      {/* 顶部滚动进度条 (流光渐变, 跟随 scrollY) */}
      <ScrollProgress />

      {/* 右上角控制区: API 状态小胶囊 + 主题切换 (fixed 常驻) */}
      <div className="fixed right-6 top-6 z-50 flex items-center gap-3">
        <ApiStatusDot />
        <ThemeToggle />
      </div>

      {/* Hero (Phase 1.b.1) */}
      <Hero />

      {/* 功能卡片 (Phase 1.b.2) */}
      <Features />

      {/* Footer (Phase 1.b.3) */}
      <Footer />
    </main>
  );
}
