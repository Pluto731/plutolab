'use client'

import { useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type NodeChange,
  type EdgeChange,
  type Connection,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { WorkflowCreate } from '@/lib/workflows'

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
        position: draft.layout?.[node.id] ?? { x: index * 220, y: 80 },
        data: { label: `${node.label || node.id} · v${node.agent_version}` },
        style: marked.includes(node.id) ? { borderColor: '#dc2626', borderWidth: 2 } : undefined,
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
    <div className="h-[380px] rounded-xl border bg-slate-50" aria-label="Workflow 画布">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={changeNodes}
        onEdgesChange={changeEdges}
        onConnect={connect}
        nodesDraggable={!disabled}
        nodesConnectable={!disabled}
        elementsSelectable={false}
        fitView
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
