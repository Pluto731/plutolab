'use client'

import { useMemo } from 'react'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  type Node,
  type NodeChange,
  type EdgeChange,
  type Connection,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { WorkflowCreate } from '@/lib/workflows'
import { Bot, CircleAlert, Sparkles } from 'lucide-react'

type AgentNodeData = { label: string; version: number; invalid: boolean }

function AgentFlowNode({ data, isConnectable }: NodeProps<Node<AgentNodeData>>) {
  return (
    <div
      className={`relative w-56 rounded-2xl bg-background shadow-xl shadow-violet-950/10 ring-1 ${
        data.invalid ? 'ring-destructive' : 'ring-border/80'
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        isConnectable={isConnectable}
        className="!size-3 !border-2 !border-background !bg-violet-500"
      />
      <div className="flex items-center justify-between rounded-t-2xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-3.5 py-2.5 text-white">
        <span className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-white/80">
          <Sparkles className="size-3" /> Agent step
        </span>
        <span className="rounded-full bg-white/15 px-2 py-0.5 font-mono text-[10px]">
          v{data.version}
        </span>
      </div>
      <div className="flex items-start gap-3 p-3.5">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-violet-500/10 text-violet-600 dark:text-violet-300">
          <Bot className="size-4" />
        </span>
        <div className="min-w-0 pt-0.5">
          <p className="truncate text-sm font-semibold">{data.label}</p>
          <p className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            {data.invalid ? (
              <CircleAlert className="size-3 text-destructive" />
            ) : (
              <span className="size-1.5 rounded-full bg-emerald-500" />
            )}
            {data.invalid ? '需要检查连接' : '只读工具与模型步骤'}
          </p>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        isConnectable={isConnectable}
        className="!size-3 !border-2 !border-background !bg-fuchsia-500"
      />
    </div>
  )
}

const nodeTypes = { agent: AgentFlowNode }

type Props = {
  draft: WorkflowCreate
  disabled: boolean
  marked: string[]
  onMove: (id: string, position: { x: number; y: number }) => void
  onRemoveNode: (id: string) => void
  onRemoveEdge: (source: string, target: string) => void
  onConnect: (source: string, target: string) => void
}
export default function WorkflowCanvas({
  draft,
  disabled,
  marked,
  onMove,
  onRemoveNode,
  onRemoveEdge,
  onConnect,
}: Props) {
  const nodes: Node[] = useMemo(
    () =>
      draft.graph.nodes.map((node, index) => ({
        id: node.id,
        type: 'agent',
        position: draft.layout?.[node.id] ?? { x: index * 300, y: 80 },
        data: {
          label: node.label || node.id,
          version: node.agent_version,
          invalid: marked.includes(node.id),
        },
      })),
    [draft, marked],
  )
  const edges = useMemo(
    () =>
      (draft.graph.edges ?? []).map((edge) => ({ ...edge, id: `${edge.source}:${edge.target}` })),
    [draft.graph.edges],
  )
  function changeNodes(changes: NodeChange[]) {
    if (disabled) return
    for (const change of changes) {
      if (change.type === 'position' && change.position)
        onMove(change.id, {
          x: Math.max(-10000, Math.min(10000, change.position.x)),
          y: Math.max(-10000, Math.min(10000, change.position.y)),
        })
      if (change.type === 'remove') onRemoveNode(change.id)
    }
  }
  function changeEdges(changes: EdgeChange[]) {
    if (disabled) return
    for (const change of changes)
      if (change.type === 'remove') {
        const edge = edges.find((e) => e.id === change.id)
        if (edge) onRemoveEdge(edge.source, edge.target)
      }
  }
  function connect(connection: Connection) {
    if (!disabled) onConnect(connection.source, connection.target)
  }
  return (
    <div
      className="h-[430px] overflow-hidden rounded-[1.5rem] bg-gradient-to-br from-violet-500/[0.035] via-background to-fuchsia-500/[0.04] shadow-inner ring-1 ring-border/60 sm:h-[520px]"
      aria-label="Workflow 画布"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={changeNodes}
        onEdgesChange={changeEdges}
        onConnect={connect}
        nodesDraggable={!disabled}
        nodesConnectable={!disabled}
        elementsSelectable={false}
        fitView
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border)" />
        <Controls
          showInteractive={false}
          className="!overflow-hidden !rounded-xl !border-border/70 !bg-background !shadow-lg"
        />
      </ReactFlow>
    </div>
  )
}
