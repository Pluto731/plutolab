import type { WorkflowGraph } from './agent'

export interface WorkflowCreate {
  name: string
  description?: string
  graph: WorkflowGraph
  layout?: Record<string, { x: number; y: number }>
}
export interface WorkflowReplace extends WorkflowCreate {
  expected_version: number
}
export interface WorkflowPublic extends Required<WorkflowCreate> {
  id: string
  version: number
  status: 'ready' | 'archived'
  created_at: string
  updated_at: string
}
export interface WorkflowPage {
  items: WorkflowPublic[]
  total: number
}

export interface WorkflowTemplateSummary {
  slug: string
  version: number
  name: string
  description: string
  required_tools: string[]
}

export interface WorkflowTemplatePage {
  items: WorkflowTemplateSummary[]
}
