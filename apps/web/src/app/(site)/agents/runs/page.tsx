import type { Metadata } from 'next'
import { RunMonitor } from '@/components/agents/run-monitor'

export const metadata: Metadata = {
  title: '运行监控 · PlutoLab',
  description: '查看 Agent Workflow 运行进度、事件和安全输出摘要',
}

export default function RunsPage() {
  return <RunMonitor />
}
