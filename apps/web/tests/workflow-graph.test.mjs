import test from 'node:test'
import assert from 'node:assert/strict'
import { graphIssue, removeNode, connectNodes } from '../src/lib/workflow-graph.ts'

const node = (id) => ({ id, agent_id: 'agent', agent_version: 1 })
const graph = (ids, pairs = []) => ({
  nodes: ids.map(node),
  edges: pairs.map(([source, target]) => ({ source, target })),
})

test('independent nodes, parallel roots and chains are valid', () => {
  for (const value of [
    graph(['a']),
    graph(
      ['a', 'b', 'c'],
      [
        ['a', 'c'],
        ['b', 'c'],
      ],
    ),
    graph(
      ['a', 'b', 'c'],
      [
        ['a', 'b'],
        ['b', 'c'],
      ],
    ),
  ])
    assert.equal(graphIssue(value), null)
})
test('cycle highlights affected nodes but not independent roots', () => {
  const issue = graphIssue(
    graph(
      ['a', 'b', 'z'],
      [
        ['a', 'b'],
        ['b', 'a'],
      ],
    ),
  )
  assert.match(issue.message, /环路/)
  assert.deepEqual(issue.nodes.sort(), ['a', 'b'])
})
test('empty, oversized, duplicate and invalid graphs are rejected', () => {
  for (const value of [
    graph([]),
    graph(Array.from({ length: 33 }, (_, i) => String(i))),
    graph(['a', 'a']),
    graph(['a'], [['a', 'a']]),
    graph(['a'], [['a', 'x']]),
    graph(
      ['a', 'b'],
      [
        ['a', 'b'],
        ['a', 'b'],
      ],
    ),
  ])
    assert.ok(graphIssue(value))
})
test('deleting a node removes incident edges and preserves the input', () => {
  const value = graph(
    ['a', 'b', 'c'],
    [
      ['a', 'b'],
      ['b', 'c'],
      ['a', 'c'],
    ],
  )
  assert.deepEqual(removeNode(value, 'b'), graph(['a', 'c'], [['a', 'c']]))
  assert.equal(value.nodes.length, 3)
})
test('connect is idempotent, rejects invalid refs, and exposes cycles', () => {
  const original = graph(['a', 'b'])
  const connected = connectNodes(original, 'a', 'b')
  assert.deepEqual(connected.edges, [{ source: 'a', target: 'b' }])
  assert.equal(connectNodes(connected, 'a', 'b'), connected)
  assert.equal(connectNodes(original, 'a', 'a'), original)
  assert.equal(connectNodes(original, 'a', 'missing'), original)
  assert.ok(graphIssue(connectNodes(connected, 'b', 'a')))
})
test('128 edges accepted, 129 rejected', () => {
  const ids = Array.from({ length: 32 }, (_, i) => String(i))
  const pairs = ids.flatMap((a, i) => ids.slice(i + 1).map((b) => [a, b]))
  assert.equal(graphIssue(graph(ids, pairs.slice(0, 128))), null)
  assert.match(graphIssue(graph(ids, pairs.slice(0, 129))).message, /128/)
})
