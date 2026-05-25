import { Features } from "@/components/features";
import { Footer } from "@/components/footer";
import { Hero } from "@/components/hero";

// 全站共用元素 (BackgroundOrbs / ScrollProgress / Nav) 已上提到 layout.tsx
export default function Home() {
  return (
    <main className="relative">
      {/* Hero (Phase 1.b.1) */}
      <Hero />

      {/* 功能卡片 (Phase 1.b.2) */}
      <Features />

      {/* Footer (Phase 1.b.3) */}
      <Footer />
    </main>
  );
}
