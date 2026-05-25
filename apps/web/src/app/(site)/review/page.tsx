import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = {
  title: "AI 代码评审 · PlutoLab",
  description: "GitHub PR 自动 Claude 评审，安全 / 性能 / 风格三维度",
};

export default function ReviewPage() {
  return (
    <ComingSoon
      emoji="🔀"
      title="AI 代码评审"
      phase="Phase 5"
      description="把 Claude 4.7 当你的全职 reviewer — 提了 PR 自动审，行内评论直接写到 GitHub。"
      features={[
        "GitHub App 一键安装 — OAuth 授权后自动监听 PR",
        "三维度审查 — 🐛 正确性 / 🔒 安全 / ⚡ 性能 分别打分",
        "行内评论 — 评审结果以行注释形式回写到 PR",
        "大 PR 智能分块 — 不爆 token 限制，按文件 / 模块切片审",
        "评审历史 — 仓库 / 时间 / 严重程度 多维筛选",
        "自定义规则 — 团队风格指南 / 安全策略 / 业务约定",
      ]}
    />
  );
}
