import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = {
  title: "画作收藏 · PlutoLab",
  description: "Pixiv 风格画廊，AI 打标 + 以图搜图 + 风格分组",
};

export default function GalleryPage() {
  return (
    <ComingSoon
      emoji="🖼️"
      title="画作收藏"
      phase="Phase 7"
      description="你的私人灵感库 — 收藏喜欢的插画，AI 自动整理，下次找图秒搜。"
      features={[
        "拖拽 / 粘贴上传 — 支持本地图片、Pixiv 链接、画师作品集批量",
        "AI 自动打标签 — 人物 / 风格 / 配色 / 主题，省去手动 tag",
        "以图搜图 — 找出风格 / 构图 / 配色相似的收藏",
        "智能聚类 — 自动按 赛博朋克 / 二次元 / 水彩 等风格分组",
        "画师追踪 — 粘贴 Pixiv URL，自动抓取该画师所有作品",
        "瀑布流画廊 — Pinterest 式无限滚动，沉浸式浏览",
      ]}
    />
  );
}
