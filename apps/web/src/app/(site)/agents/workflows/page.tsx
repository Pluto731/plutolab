import type { Metadata } from 'next'
import { WorkflowEditor } from '@/components/workflows/workflow-editor'

export const metadata: Metadata = {
  title: 'Workflow 编辑器 · PlutoLab',
  description: '连接 Agent，保存有版本的协作流程',
}
export default function WorkflowsPage() {
  return <WorkflowEditor />
}
