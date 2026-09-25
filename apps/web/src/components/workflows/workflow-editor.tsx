'use client'

import dynamic from 'next/dynamic'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Component, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Play, Plus, RefreshCw, Workflow } from 'lucide-react'
import { agentsApi, type AgentPublic } from '@/lib/agents'
import { Phase6Navigation } from '@/components/agents/phase6-navigation'
import { agentRunsApi, RunRequestError } from '@/lib/agent-runs'
import { connectNodes, graphIssue, removeNode } from '@/lib/workflow-graph'
import {
  workflowsApi,
  WorkflowRequestError,
  type WorkflowCreate,
  type WorkflowPublic,
} from '@/lib/workflows'

const Canvas = dynamic(() => import('./workflow-canvas'), {
  ssr: false,
  loading: () => <p>加载画布中，下面的表单可直接编辑。</p>,
})
class CanvasBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? (
      <p role="status">画布暂不可用，请使用下方表单继续编辑。</p>
    ) : (
      this.props.children
    )
  }
}
const empty = (): WorkflowCreate => ({
  name: '',
  description: '',
  graph: { nodes: [], edges: [] },
  layout: {},
})
const inputStyle =
  'rounded-xl border border-border/70 bg-background/80 px-3 py-2.5 text-sm shadow-sm outline-none transition focus:border-violet-500/60 focus:ring-4 focus:ring-violet-500/10'
export function WorkflowEditor() {
  const router = useRouter()
  const [draft, setDraft] = useState<WorkflowCreate>(empty)
  const [current, setCurrent] = useState<WorkflowPublic | null>(null)
  const [items, setItems] = useState<WorkflowPublic[]>([])
  const [templates, setTemplates] = useState<
    Awaited<ReturnType<typeof workflowsApi.templates>>['items']
  >([])
  const [templateId, setTemplateId] = useState('')
  const [templateLoading, setTemplateLoading] = useState(true)
  const [templateError, setTemplateError] = useState('')
  const [agents, setAgents] = useState<AgentPublic[]>([])
  const [agentId, setAgentId] = useState('')
  const [agentOffset, setAgentOffset] = useState(0)
  const [agentTotal, setAgentTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [refresh, setRefresh] = useState(0)
  const [loading, setLoading] = useState(true)
  const [agentsLoading, setAgentsLoading] = useState(true)
  const [agentError, setAgentError] = useState('')
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [showCanvas, setShowCanvas] = useState(true)
  const [source, setSource] = useState('')
  const [target, setTarget] = useState('')
  const [runInput, setRunInput] = useState('')
  const [runKey, setRunKey] = useState('')
  const [runBusy, setRunBusy] = useState(false)
  const [runError, setRunError] = useState('')
  useEffect(() => {
    setRunKey('')
  }, [current?.id, current?.version])
  const issue = graphIssue(draft.graph)
  const disabled = busy || conflict
  useEffect(() => {
    let live = true
    workflowsApi
      .templates()
      .then((page) => {
        if (!live) return
        setTemplates(page.items)
        setTemplateId(page.items[0] ? `${page.items[0].slug}:${page.items[0].version}` : '')
        setTemplateError('')
      })
      .catch(() => {
        if (live) setTemplateError('模板目录暂不可用。')
      })
      .finally(() => {
        if (live) setTemplateLoading(false)
      })
    return () => {
      live = false
    }
  }, [])
  useEffect(() => {
    let live = true
    setLoading(true)
    workflowsApi
      .list(offset)
      .then((page) => {
        if (live) {
          setItems(page.items)
          setTotal(page.total)
        }
      })
      .catch(() => {
        if (live) {
          setItems([])
          setError('流程列表读取失败，请刷新重试。')
        }
      })
      .finally(() => {
        if (live) setLoading(false)
      })
    return () => {
      live = false
    }
  }, [offset, refresh])
  useEffect(() => {
    let live = true
    setAgentsLoading(true)
    setAgentError('')
    agentsApi
      .list(agentOffset)
      .then((page) => {
        if (live) {
          setAgents(page.items)
          setAgentTotal(page.total)
          setAgentId(page.items[0]?.id ?? '')
        }
      })
      .catch(() => {
        if (live) {
          setAgents([])
          setAgentError('Agent 读取失败，请刷新重试。')
        }
      })
      .finally(() => {
        if (live) setAgentsLoading(false)
      })
    return () => {
      live = false
    }
  }, [agentOffset, refresh])
  useEffect(() => {
    if (!dirty) return
    const protect = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', protect)
    return () => window.removeEventListener('beforeunload', protect)
  }, [dirty])
  function load(value: WorkflowPublic | null) {
    if (dirty && !window.confirm('放弃未保存的流程草稿？')) return
    setCurrent(value)
    setDraft(
      value
        ? {
            name: value.name,
            description: value.description,
            graph: structuredClone(value.graph),
            layout: structuredClone(value.layout),
          }
        : empty(),
    )
    setDirty(false)
    setConflict(false)
    setError('')
    setMessage('')
    setSource('')
    setTarget('')
    setRunInput('')
    setRunKey('')
    setRunError('')
  }
  function edit(change: (old: WorkflowCreate) => WorkflowCreate) {
    if (disabled) return
    setDraft(change)
    setDirty(true)
    setMessage('')
  }
  function remove(id: string) {
    edit((old) => {
      const layout = { ...old.layout }
      delete layout[id]
      return { ...old, graph: removeNode(old.graph, id), layout }
    })
  }
  function disconnect(from: string, to: string) {
    edit((old) => ({
      ...old,
      graph: {
        ...old.graph,
        edges: (old.graph.edges ?? []).filter((edge) => edge.source !== from || edge.target !== to),
      },
    }))
  }
  function connect(from: string, to: string) {
    edit((old) => ({ ...old, graph: connectNodes(old.graph, from, to) }))
  }
  function add() {
    const agent = agents.find((a) => a.id === agentId)
    if (!agent || draft.graph.nodes.length >= 32) return
    edit((old) => {
      const id = `node_${crypto.randomUUID().replaceAll('-', '')}`
      return {
        ...old,
        graph: {
          ...old.graph,
          nodes: [
            ...old.graph.nodes,
            { id, agent_id: agent.id, agent_version: agent.version, label: agent.name },
          ],
        },
        layout: {
          ...old.layout,
          [id]: {
            x: (old.graph.nodes.length % 4) * 220,
            y: Math.floor(old.graph.nodes.length / 4) * 120,
          },
        },
      }
    })
  }
  async function save() {
    if (issue || !draft.name.trim()) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const saved = await workflowsApi.save(draft, current)
      setCurrent(saved)
      setDirty(false)
      setMessage('流程已保存。')
      setRefresh((v) => v + 1)
    } catch (err) {
      setError(err instanceof WorkflowRequestError ? err.message : '保存失败，草稿已保留。')
      if (err instanceof WorkflowRequestError && err.status === 409) setConflict(true)
    } finally {
      setBusy(false)
    }
  }
  async function reload() {
    if (!current || (dirty && !window.confirm('放弃草稿并加载服务器最新版本？'))) return
    setBusy(true)
    try {
      const value = await workflowsApi.get(current.id)
      setCurrent(value)
      setDraft({
        name: value.name,
        description: value.description,
        graph: value.graph,
        layout: value.layout,
      })
      setDirty(false)
      setConflict(false)
      setError('')
      setMessage('已重新加载。')
    } catch (err) {
      setError(err instanceof Error ? err.message : '重载失败。')
    } finally {
      setBusy(false)
    }
  }
  async function archive() {
    if (!current || !window.confirm('归档此流程？历史版本会保留，未保存草稿将被放弃。')) return
    setBusy(true)
    try {
      await workflowsApi.archive(current)
      setCurrent(null)
      setDraft(empty())
      setDirty(false)
      setError('')
      setConflict(false)
      setMessage('流程已归档。')
      setRefresh((v) => v + 1)
    } catch (err) {
      setError(err instanceof WorkflowRequestError ? err.message : '归档失败。')
      if (err instanceof WorkflowRequestError && err.status === 409) setConflict(true)
    } finally {
      setBusy(false)
    }
  }
  async function startRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!current || current.status !== 'ready' || dirty || !runInput.trim()) return
    setRunBusy(true)
    setRunError('')
    const key = runKey || crypto.randomUUID()
    setRunKey(key)
    try {
      const created = await agentRunsApi.create(
        current.id,
        { workflow_version: current.version, text: runInput.trim() },
        key,
      )
      setRunKey('')
      router.push(`/agents/runs/${created.id}`)
    } catch (cause) {
      if (cause instanceof RunRequestError && cause.status === 409) setRunKey('')
      setRunError(
        cause instanceof RunRequestError
          ? cause.message
          : '运行创建结果暂不确定；可安全重试，系统会使用相同幂等键。',
      )
    } finally {
      setRunBusy(false)
    }
  }
  async function importTemplate() {
    const [slug, versionText] = templateId.split(':')
    const template = templates.find(
      (item) => item.slug === slug && item.version === Number(versionText),
    )
    if (!template || (dirty && !window.confirm('放弃未保存草稿并导入私有模板副本？'))) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const value = await workflowsApi.importTemplate(template.slug, template.version)
      setCurrent(value)
      setDraft({
        name: value.name,
        description: value.description,
        graph: value.graph,
        layout: value.layout,
      })
      setDirty(false)
      setConflict(false)
      setRefresh((v) => v + 1)
      setMessage('模板已复制到你的私有 Workflow，可独立编辑。')
    } catch (cause) {
      setError(cause instanceof WorkflowRequestError ? cause.message : '模板导入失败。')
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-7 sm:px-6 md:py-10">
      <Phase6Navigation active="/agents/workflows" />
      <header className="flex flex-wrap items-end justify-between gap-6 border-b border-border/60 pb-6">
        <div>
          <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-violet-600 dark:text-violet-300">
            <Workflow className="size-3.5" /> Phase 06 · Workflow design
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">编排协作流程</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            将专注的 Agent 连接成可复用流程，在画布中整理执行顺序，再运行已保存版本。
          </p>
        </div>
        <p className="font-mono text-sm text-muted-foreground">
          <span className="text-2xl font-semibold text-foreground">{total}</span> 个流程
        </p>
      </header>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <section
        aria-label="内置 Workflow 模板"
        className="relative flex flex-wrap items-end gap-3 border-l-2 border-violet-500 bg-violet-500/[0.045] px-4 py-3"
      >
        <div className="min-w-60 flex-1">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <span className="grid size-7 place-items-center rounded-lg bg-violet-500/10 text-violet-600 dark:text-violet-300">
              <Workflow className="size-4" />
            </span>
            从模板快速开始
          </h2>
          <p className="ml-9 mt-0.5 text-xs text-muted-foreground">
            导入会复制 Agents 和 Workflow 到你的账户，之后可独立修改。
          </p>
        </div>
        {templateLoading ? (
          <p role="status" className="text-sm">
            加载模板…
          </p>
        ) : templates.length ? (
          <>
            <label className="text-sm">
              可用模板
              <select
                aria-label="Workflow 模板"
                className={`${inputStyle} ml-2`}
                value={templateId}
                onChange={(event) => setTemplateId(event.target.value)}
                disabled={busy}
              >
                <option value="" disabled>
                  请选择模板
                </option>
                {templates.map((item) => (
                  <option
                    key={`${item.slug}:${item.version}`}
                    value={`${item.slug}:${item.version}`}
                  >
                    {item.name} · v{item.version}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => void importTemplate()}
              disabled={busy || !templateId}
              className="rounded-full bg-violet-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-violet-500 disabled:opacity-50"
            >
              导入私有副本
            </button>
          </>
        ) : (
          <p role={templateError ? 'alert' : 'status'} className="text-sm text-muted-foreground">
            {templateError || '暂无内置模板。'}
          </p>
        )}
      </section>
      <div className="grid gap-6 lg:grid-cols-[230px_minmax(0,1fr)]">
        <aside className="space-y-4 lg:pt-1">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">我的流程</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">已保存的版本</p>
            </div>
            <button
              type="button"
              aria-label="新建流程"
              disabled={busy}
              className="grid size-9 place-items-center rounded-full bg-violet-600 text-white shadow-sm transition hover:bg-violet-500 disabled:opacity-50"
              onClick={() => load(null)}
            >
              <Plus className="size-4" />
            </button>
          </div>
          <button
            type="button"
            disabled={busy || loading}
            onClick={() => {
              setError('')
              setRefresh((v) => v + 1)
            }}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-50"
          >
            <RefreshCw className="size-3" /> 刷新列表
          </button>
          {loading ? (
            <p role="status">加载流程中…</p>
          ) : items.length === 0 ? (
            <p>暂无流程。</p>
          ) : (
            <ul className="space-y-1">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    disabled={busy}
                    onClick={() => load(item)}
                    className={`relative flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition ${current?.id === item.id ? 'bg-violet-500/10' : 'hover:bg-muted/60'}`}
                  >
                    {current?.id === item.id && (
                      <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-violet-500" />
                    )}
                    <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-violet-600 dark:text-violet-300">
                      <Workflow className="size-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">{item.name}</span>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        版本 {item.version}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex justify-between">
            <button
              disabled={loading || busy || offset === 0}
              onClick={() => setOffset((v) => v - 20)}
            >
              上一页流程
            </button>
            <button
              disabled={loading || busy || offset + 20 >= total || offset >= 10000}
              onClick={() => setOffset((v) => v + 20)}
            >
              下一页流程
            </button>
          </div>
        </aside>
        <section className="space-y-5">
          <div className="flex flex-wrap items-center gap-3 border-b border-border/60 pb-3">
            <h2 className="text-xl font-medium">
              {current ? `编辑流程 · v${current.version}` : '新流程'}
            </h2>
            <span className="text-sm text-muted-foreground">
              {dirty ? '● 有未保存修改' : '✓ 已同步'}
            </span>
            <button
              onClick={() => setShowCanvas((v) => !v)}
              className="ml-auto rounded-full px-3 py-2 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground"
            >
              {showCanvas ? '仅用表单编辑' : '显示画布'}
            </button>
          </div>
          {current?.status === 'ready' && (
            <form
              onSubmit={(event) => void startRun(event)}
              className="space-y-3 rounded-2xl bg-gradient-to-br from-violet-950 to-zinc-950 p-5 text-white shadow-lg shadow-violet-950/10 sm:p-6"
            >
              <div>
                <h3 className="font-semibold">运行已保存的版本</h3>
                <p className="text-sm text-zinc-300">
                  使用 v{current.version}；未保存的修改不会进入本次运行。Run 会先进入队列。
                </p>
              </div>
              <label className="block text-sm">
                任务输入
                <textarea
                  aria-label="运行任务输入"
                  required
                  maxLength={16000}
                  rows={4}
                  value={runInput}
                  onChange={(event) => {
                    setRunInput(event.target.value)
                    setRunKey('')
                  }}
                  className="mt-1 w-full rounded-xl border border-white/15 bg-white/[0.06] p-3 text-white outline-none placeholder:text-zinc-500 focus:border-violet-400/70 focus:ring-4 focus:ring-violet-500/15"
                  placeholder="描述这次 Workflow 要处理的内容"
                  disabled={runBusy}
                />
                <span className="text-xs text-muted-foreground">{runInput.length}/16000</span>
              </label>
              {dirty && <p className="text-sm">请先保存修改，再运行已保存版本。</p>}
              {runError && (
                <p role="alert" className="text-sm text-destructive">
                  {runError}
                </p>
              )}
              <button
                type="submit"
                disabled={runBusy || dirty || !runInput.trim()}
                className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2.5 text-sm font-medium text-zinc-950 transition hover:bg-violet-100 disabled:opacity-50"
              >
                <Play className="size-3.5" />
                {runBusy ? '正在创建…' : '创建 Run'}
              </button>
            </form>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block space-y-1.5 text-sm font-medium">
              流程名称
              <input
                disabled={disabled}
                required
                maxLength={100}
                className={`${inputStyle} mt-1 block w-full font-normal`}
                value={draft.name}
                onChange={(e) => edit((old) => ({ ...old, name: e.target.value }))}
              />
            </label>
            <label className="block space-y-1.5 text-sm font-medium">
              流程描述
              <textarea
                aria-label="流程描述"
                disabled={disabled}
                maxLength={2000}
                className={`${inputStyle} mt-1 block w-full font-normal`}
                value={draft.description}
                onChange={(e) => edit((old) => ({ ...old, description: e.target.value }))}
              />
            </label>
          </div>
          {issue && (
            <p role="alert" className="text-destructive">
              {issue.message}
            </p>
          )}
          {showCanvas && (
            <CanvasBoundary>
              <Canvas
                draft={draft}
                disabled={disabled}
                marked={issue?.nodes ?? []}
                onMove={(id, position) =>
                  edit((old) => ({ ...old, layout: { ...old.layout, [id]: position } }))
                }
                onRemoveNode={remove}
                onRemoveEdge={disconnect}
                onConnect={connect}
              />
            </CanvasBoundary>
          )}
          <fieldset
            disabled={disabled}
            className="space-y-4 border-t border-border/60 pt-5 disabled:opacity-60"
          >
            <legend className="px-2 font-medium">节点与连线表单</legend>
            {agentError && <p role="alert">{agentError}</p>}
            <div className="flex flex-wrap items-center gap-3">
              <label>
                选择 Agent
                <select
                  className={`${inputStyle} ml-2`}
                  disabled={agentsLoading}
                  aria-label="选择 Agent"
                  value={agentId}
                  onChange={(e) => setAgentId(e.target.value)}
                >
                  {agents.length ? (
                    agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name} · v{a.version}
                      </option>
                    ))
                  ) : (
                    <option value="">{agentsLoading ? '加载中…' : '请先创建 Agent'}</option>
                  )}
                </select>
              </label>
              <button
                onClick={add}
                disabled={agentsLoading || !agentId || draft.graph.nodes.length >= 32}
                className={inputStyle}
              >
                添加节点
              </button>
              <button
                disabled={agentsLoading || agentOffset === 0}
                onClick={() => setAgentOffset((v) => v - 20)}
              >
                上一页 Agent
              </button>
              <button
                disabled={agentsLoading || agentOffset + 20 >= agentTotal || agentOffset >= 10000}
                onClick={() => setAgentOffset((v) => v + 20)}
              >
                下一页 Agent
              </button>
              <button
                disabled={agentsLoading}
                onClick={() => setRefresh((v) => v + 1)}
                className="underline"
              >
                刷新 Agent
              </button>
            </div>
            <ul className="space-y-3">
              {draft.graph.nodes.map((node, index) => (
                <li
                  key={node.id}
                  className={`space-y-2 rounded border p-3 ${issue?.nodes.includes(node.id) ? 'border-destructive' : ''}`}
                >
                  <p className="text-sm">
                    节点 {index + 1} · {node.label || node.id} · v{node.agent_version}
                  </p>
                  <label>
                    节点 {index + 1} 名称
                    <input
                      maxLength={100}
                      className={`${inputStyle} ml-2`}
                      value={node.label ?? ''}
                      onChange={(e) =>
                        edit((old) => ({
                          ...old,
                          graph: {
                            ...old.graph,
                            nodes: old.graph.nodes.map((n) =>
                              n.id === node.id ? { ...n, label: e.target.value } : n,
                            ),
                          },
                        }))
                      }
                    />
                  </label>
                  <label className="block">
                    节点 {index + 1} Agent
                    <select
                      className={`${inputStyle} ml-2`}
                      aria-label={`节点 ${index + 1} Agent`}
                      value=""
                      onChange={(e) => {
                        const a = agents.find((item) => item.id === e.target.value)
                        if (a)
                          edit((old) => ({
                            ...old,
                            graph: {
                              ...old.graph,
                              nodes: old.graph.nodes.map((n) =>
                                n.id === node.id
                                  ? {
                                      ...n,
                                      agent_id: a.id,
                                      agent_version: a.version,
                                      label: a.name,
                                    }
                                  : n,
                              ),
                            },
                          }))
                      }}
                    >
                      <option value="">重新绑定为当前 Agent 版本</option>
                      {agents.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name} · v{a.version}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button className="text-destructive" onClick={() => remove(node.id)}>
                    删除节点 {index + 1}
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center gap-3">
              <label>
                起点
                <select
                  className={`${inputStyle} ml-2`}
                  aria-label="起点"
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                >
                  <option value="">选择节点</option>
                  {draft.graph.nodes.map((n, i) => (
                    <option key={n.id} value={n.id}>
                      {i + 1} · {n.label || n.id}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                终点
                <select
                  className={`${inputStyle} ml-2`}
                  aria-label="终点"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                >
                  <option value="">选择节点</option>
                  {draft.graph.nodes.map((n, i) => (
                    <option key={n.id} value={n.id}>
                      {i + 1} · {n.label || n.id}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className={inputStyle}
                disabled={
                  !source || !target || source === target || (draft.graph.edges?.length ?? 0) >= 128
                }
                onClick={() => connect(source, target)}
              >
                添加连线
              </button>
            </div>
            <ul>
              {(draft.graph.edges ?? []).map((edge) => (
                <li key={`${edge.source}:${edge.target}`} className="flex gap-4 py-2">
                  <span>
                    {draft.graph.nodes.find((n) => n.id === edge.source)?.label || edge.source} →{' '}
                    {draft.graph.nodes.find((n) => n.id === edge.target)?.label || edge.target}
                  </span>
                  <button
                    onClick={() => disconnect(edge.source, edge.target)}
                    className="text-destructive"
                    aria-label={`删除连线 ${edge.source} 到 ${edge.target}`}
                  >
                    删除连线
                  </button>
                </li>
              ))}
            </ul>
          </fieldset>
          <div className="flex gap-4">
            <button
              disabled={disabled || !!issue || !draft.name.trim()}
              onClick={() => void save()}
              className="rounded bg-primary px-4 py-2 text-primary-foreground"
            >
              {busy ? '处理中…' : '保存流程'}
            </button>
            {current && (
              <>
                <button disabled={busy} onClick={() => void reload()} className="underline">
                  重新加载流程
                </button>
                <button
                  disabled={disabled}
                  onClick={() => void archive()}
                  className="text-destructive"
                >
                  归档流程
                </button>
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  )
}
