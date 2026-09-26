/** Phase 6 wire contracts. UUID/time values are strings; budgets are integers.
 * Runtime validation and size limits live in schemas/agent.py.
 * Execution/Workflow contracts do not imply those services are implemented.
 */
export type AgentState = 'active' | 'archived'
export type WorkflowState = 'draft' | 'ready' | 'archived'
export type RunState = 'pending' | 'running' | 'succeeded' | 'partial' | 'failed' | 'cancelled'
export type NodeState = 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped' | 'cancelled'

export interface AgentCreate {
  name: string
  description?: string
  role_prompt: string
  provider?: 'openai'
  model: 'gpt-4o-mini'
  tools?: ('search_notes' | 'search_github')[]
}

export interface AgentReplace extends AgentCreate {
  expected_version: number
}

export interface AgentPublic extends Required<AgentCreate> {
  id: string
  version: number
  status: AgentState
  created_at: string
  updated_at: string
}

export interface AgentPage {
  items: AgentPublic[]
  total: number
}

export interface WorkflowNode {
  id: string
  agent_id: string
  agent_version: number
  label?: string
}

export interface WorkflowGraph {
  nodes: WorkflowNode[]
  edges?: { source: string; target: string }[]
}

export interface ExecutionBudget {
  parallelism: number
  node_timeout_seconds: number
  run_timeout_seconds: number
  max_tokens: number
  max_cost_microusd: number
  retries: number
}

export interface NodeOutput {
  node_id: string
  text: string
}

export interface NodeInput {
  text: string
  upstream?: NodeOutput[]
}

export interface ExecutionPolicy {
  failure_policy: 'fail_fast'
  rerun_policy: 'original_snapshot'
  budget: ExecutionBudget
}

export interface ExecutionStatus {
  workflow: WorkflowState
  run: RunState
  node: NodeState
}
