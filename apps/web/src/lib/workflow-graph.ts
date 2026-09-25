import type { WorkflowGraph } from '../../../../packages/types/src/agent'

export type GraphIssue = { message: string; nodes: string[] }
export function graphIssue(graph: WorkflowGraph): GraphIssue | null {
  const ids = graph.nodes.map((node) => node.id)
  if (ids.length === 0) return { message: '至少添加一个 Agent 节点。', nodes: [] }
  if (ids.length > 32 || (graph.edges?.length ?? 0) > 128)
    return { message: '最多 32 个节点和 128 条连线。', nodes: [] }
  if (new Set(ids).size !== ids.length) return { message: '节点 ID 重复。', nodes: ids }
  const degree = new Map(ids.map((id) => [id, 0]))
  const children = new Map(ids.map((id) => [id, [] as string[]]))
  const pairs = new Set<string>()
  for (const edge of graph.edges ?? []) {
    const key = JSON.stringify([edge.source, edge.target])
    if (
      !degree.has(edge.source) ||
      !degree.has(edge.target) ||
      edge.source === edge.target ||
      pairs.has(key)
    )
      return {
        message: `无效连线：${edge.source} → ${edge.target}。`,
        nodes: [edge.source, edge.target],
      }
    pairs.add(key)
    degree.set(edge.target, degree.get(edge.target)! + 1)
    children.get(edge.source)!.push(edge.target)
  }
  const ready = ids.filter((id) => degree.get(id) === 0)
  let seen = 0
  while (ready.length) {
    const id = ready.shift()!
    seen++
    for (const child of children.get(id)!) {
      degree.set(child, degree.get(child)! - 1)
      if (degree.get(child) === 0) ready.push(child)
    }
  }
  if (seen !== ids.length)
    return {
      message: '存在环路，标记节点涉及环路或受其阻塞，请删除连线。',
      nodes: ids.filter((id) => degree.get(id)! > 0),
    }
  return null
}
export function removeNode(graph: WorkflowGraph, id: string): WorkflowGraph {
  return {
    nodes: graph.nodes.filter((node) => node.id !== id),
    edges: (graph.edges ?? []).filter((edge) => edge.source !== id && edge.target !== id),
  }
}
export function connectNodes(graph: WorkflowGraph, source: string, target: string): WorkflowGraph {
  if (
    source === target ||
    !graph.nodes.some((n) => n.id === source) ||
    !graph.nodes.some((n) => n.id === target) ||
    (graph.edges ?? []).some((e) => e.source === source && e.target === target)
  )
    return graph
  return { ...graph, edges: [...(graph.edges ?? []), { source, target }] }
}
