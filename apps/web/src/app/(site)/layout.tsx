import { BackgroundOrbs } from "@/components/background-orbs";
import { CommandPalette } from "@/components/command-palette";
import { Nav } from "@/components/nav";
import { PageTransition } from "@/components/page-transition";
import { ScrollProgress } from "@/components/scroll-progress";
import { Sidebar } from "@/components/sidebar";
import { SiteShell } from "@/components/site-shell";

/**
 * 路由布局: 主体两类页面
 * - 营销首页 `/`: 全宽展示, 顶部老 Nav (Sidebar/SiteShell 都按 pathname 判断在 `/` 不缩进)
 * - 应用页 `/dashboard /notes /settings ...`: 左侧 sidebar + 主内容区左 padding
 *
 * Nav / Sidebar / SiteShell 都挂着, 各自根据 pathname 决定显隐 / 缩进, 避免 layout 层 client 切换闪屏.
 */
export default function SiteLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <BackgroundOrbs />
      <ScrollProgress />
      <Nav />
      <Sidebar />
      <CommandPalette />
      <SiteShell>
        <PageTransition>{children}</PageTransition>
      </SiteShell>
    </>
  );
}
