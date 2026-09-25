import type { Metadata } from 'next'
import { AgentEditor } from '@/components/agents/agent-editor'

export const metadata: Metadata = {
  title: 'Agent 工作台 · PlutoLab',
  description: '管理 Agent 角色、模型和只读工具配置',
}
export default function AgentsPage() {
  return <AgentEditor />
}
