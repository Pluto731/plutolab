import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = {
  title: "笔记 · PlutoLab",
  description: "Markdown 编辑器 + 标签 + 全文搜索 + AI 总结",
};

export default function NotesPage() {
  return (
    <ComingSoon
      emoji="📝"
      title="智能笔记"
      phase="Phase 3"
      description="一个为 AI 时代设计的笔记工具：写作时 AI 是助手，回顾时 AI 是索引。"
      features={[
        "Markdown 编辑器 — 实时预览 / 双栏 / 全屏三种模式自由切换",
        "标签系统 — 多标签、颜色分类、树状嵌套，告别文件夹焦虑",
        "PostgreSQL 全文搜索 — 中文分词 + 模糊匹配，毫秒级找回",
        "AI 助手 — 选中段落右键 → 总结 / 改写 / 翻译 / 配图",
        "每日笔记 — 自动生成今日入口，类 Roam/Logseq 体验",
        "双向链接 — [[wikilink]] 语法 + 反向引用，构建知识网",
      ]}
    />
  );
}
