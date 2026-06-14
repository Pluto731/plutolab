"use client";

import { usePathname } from "next/navigation";

/**
 * 应用页主内容容器 — 按路由决定是否给 sidebar 留 padding.
 * 营销首页 `/` 不留, hero 全宽展示;
 * 其他应用页留 md:pl-60 给左侧 240px sidebar.
 */
export function SiteShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isMarketing = pathname === "/";
  return <div className={isMarketing ? "" : "md:pl-60"}>{children}</div>;
}
