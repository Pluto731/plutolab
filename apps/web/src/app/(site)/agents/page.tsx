import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";

export const metadata: Metadata = {
  title: "多 Agent 协作 · PlutoLab",
  description: "可视化编排 AI 工作流：研究员 + 文案 + 分析师协同作业",
};

export default function AgentsPage() {
  return (
    <ComingSoon
      emoji="🌊"
      title="多 Agent 协作"
      phase="Phase 6"
      description="把复杂任务拆给多个 Agent — 研究员收集信息 → 写手生产内容 → 分析师做评估。"
      features={[
        "可视化 DAG 编辑器 — 拖线串起 Agent，所见即所得",
        "Agent 模板库 — 研究员 / 文案 / 数据分析师 / 翻译官 等预设",
        "工具调用 — 网络搜索 / 数据库查询 / 文件读写 / API 调用",
        "实时日志流 — SSE 推送每个 Agent 的思考过程",
        "并行执行 — 拓扑排序后无依赖节点并发跑",
        "历史回放 + 重跑 — 任意节点重新执行，调试更快",
      ]}
    />
  );
}
