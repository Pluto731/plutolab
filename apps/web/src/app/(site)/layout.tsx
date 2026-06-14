import { BackgroundOrbs } from "@/components/background-orbs";
import { CommandPalette } from "@/components/command-palette";
import { Nav } from "@/components/nav";
import { PageTransition } from "@/components/page-transition";
import { ScrollProgress } from "@/components/scroll-progress";
import { Sidebar } from "@/components/sidebar";

/**
 * 路由布局: 主体两类页面
 * - 营销首页 `/`: 全宽展示, 顶部老 Nav (Sidebar 内部已用 pathname 判断在 `/` 不渲染)
 * - 应用页 `/dashboard /notes /settings ...`: 左侧 sidebar + 主内容区左 padding
 *
 * Nav 和 Sidebar 都挂着, 自行根据 pathname 决定显隐, 避免 layout 层做客户端切换闪屏.
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
      {/* 桌面端 sidebar 留 240px, 移动端 sidebar 是抽屉, 主体仍占满 */}
      <div className="md:pl-60">
        <PageTransition>{children}</PageTransition>
      </div>
    </>
  );
}
