import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = {
  title: "RAG 文档问答 · PlutoLab",
  description: "上传 PDF / Markdown / Word，AI 回答含原文引用",
};

export default function RagPage() {
  return (
    <ComingSoon
      emoji="🔍"
      title="RAG 文档问答"
      phase="Phase 4"
      description="把你的文档变成可以对话的知识库 — 上传后用自然语言提问，AI 回答附带原文引用。"
      features={[
        "拖拽上传 — PDF / Markdown / Word / Excel / 网页 URL",
        "自动切块 + 向量化 — pgvector 存储，毫秒级语义检索",
        "回答含引用 — 每句标注来源页码 / 段落，点击跳到原文",
        "跨文档提问 — 在多个文档间联合检索",
        "知识库管理 — 项目分组、文档版本、自动重建索引",
        "对话历史 + 分支 — 像 ChatGPT 一样的多轮 + Git 式分支对话",
      ]}
    />
  );
}
