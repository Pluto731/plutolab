/** Owner-scoped Run wire contracts. Inputs are not included in list/event views. */
import type { NodeState, RunState, WorkflowGraph } from './agent'

export interface RunSummary {
  id: string
  workflow_id: string
  workflow_version: number
  state: RunState
  created_at: string
  finished_at: string | null
}

export interface RunRerun {
  mode: 'snapshot' | 'latest'
}

export interface RunCreate {
  workflow_version: number
  text: string
}

export interface RunPage {
  items: RunSummary[]
  total: number
}

export interface RunNodeView {
  node_id: string
  state: NodeState
  error_code: string | null
  output: string | null
  attempts: number
  retries: number
}

export interface RunDetail extends RunSummary {
  cancel_requested: boolean
  event_sequence: number
  checkpoint: { completed_node_ids: string[] }
  charged_tokens: number
  charged_cost_microusd: number
  graph: WorkflowGraph
  nodes: RunNodeView[]
}

export type RunEventType =
  | 'run_started'
  | 'run_cancel_requested'
  | 'run_finished'
  | 'node_started'
  | 'node_finished'
  | 'node_skipped'

export interface RunEvent {
  sequence: number
  event_type: RunEventType
  node_id: string | null
  state: RunState | NodeState
  summary: string | null
  created_at: string
}

export interface RunEventPage {
  items: RunEvent[]
  oldest_sequence: number
  latest_sequence: number
}
