'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { agentRunsApi, RunRequestError, streamRunEvents } from '@/lib/agent-runs'
import type { RunDetail, RunEvent, RunSummary } from '../../../../../packages/types/src/agent-run'
import type { RunState } from '../../../../../packages/types/src/agent'

const stateLabel: Record<RunState | 'skipped', string> = {
  pending: '等待派发',
  running: '运行中',
  succeeded: '成功',
  partial: '部分完成',
  failed: '失败',
  cancelled: '已取消',
  skipped: '已跳过',
}
const stateStyle: Record<RunState | 'skipped', string> = {
  pending: 'border-muted text-muted-foreground',
  running: 'border-blue-500/50 bg-blue-500/10 text-blue-700 dark:text-blue-300',
  succeeded: 'border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  partial: 'border-amber-500/50 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  failed: 'border-destructive/50 bg-destructive/10 text-destructive',
  cancelled: 'border-muted bg-muted/40 text-muted-foreground',
  skipped: 'border-muted bg-muted/40 text-muted-foreground',
}
const labels: Record<string, string> = {
  missing_key: '未配置模型密钥',
  invalid_key: '模型密钥不可用',
  unsupported_model: '模型不受支持',
  budget_exceeded: '运行预算不足',
  provider_timeout: '模型请求超时',
  provider_rate_limit: '模型请求频率受限',
  provider_unavailable: '模型服务暂不可用',
  provider_auth: '模型认证失败',
  provider_invalid: '模型返回无效结果',
  unsafe_output: '输出未通过安全检查',
  tool_failed: '只读工具执行失败',
  tool_limit: '工具调用次数已达上限',
  cancelled: '节点已取消',
  dependency_failed: '依赖节点未成功',
  internal_error: '内部执行失败',
}
const active = (state?: RunState) => state === 'pending' || state === 'running'

function layers(detail: RunDetail): string[][] {
  const nodes = detail.graph.nodes.map((node) => node.id)
  const degree = new Map(nodes.map((id) => [id, 0]))
  const children = new Map(nodes.map((id) => [id, [] as string[]]))
  for (const edge of detail.graph.edges ?? []) {
    if (!degree.has(edge.source) || !degree.has(edge.target)) continue
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1)
    children.get(edge.source)?.push(edge.target)
  }
  let ready = nodes.filter((id) => degree.get(id) === 0).sort()
  const result: string[][] = []
  let seen = 0
  while (ready.length) {
    result.push(ready)
    seen += ready.length
    const next: string[] = []
    for (const id of ready)
      for (const child of children.get(id) ?? []) {
        degree.set(child, (degree.get(child) ?? 1) - 1)
        if (degree.get(child) === 0) next.push(child)
      }
    ready = next.sort()
  }
  return seen === nodes.length ? result : nodes.map((id) => [id])
}

export function RunMonitor({ initialRunId }: { initialRunId?: string }) {
  const router = useRouter()
  const [items, setItems] = useState<RunSummary[]>([])
  const [selectedId, setSelectedId] = useState(initialRunId ?? '')
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [events, setEvents] = useState<RunEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [streamState, setStreamState] = useState<
    'connecting' | 'connected' | 'retrying' | 'closed'
  >('closed')
  const [busy, setBusy] = useState(false)
  const sequence = useRef(0)
  const detailRequest = useRef(0)
  const orderedLayers = useMemo(() => (detail ? layers(detail) : []), [detail])

  const loadList = useCallback(async () => {
    setLoading(true)
    try {
      const page = await agentRunsApi.list(0)
      setItems(page.items)
      setError('')
    } catch (cause) {
      setError(cause instanceof RunRequestError ? cause.message : '运行列表读取失败。')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (id: string) => {
    const requestId = ++detailRequest.current
    setDetailLoading(true)
    try {
      const next = await agentRunsApi.get(id)
      if (requestId !== detailRequest.current) return
      const page = await agentRunsApi.events(id, Math.max(0, next.event_sequence - 128))
      if (requestId !== detailRequest.current) return
      setDetail(next)
      setEvents(page.items)
      sequence.current = page.latest_sequence
      setError('')
      setItems((current) => [next, ...current.filter((item) => item.id !== next.id)])
    } catch (cause) {
      if (requestId !== detailRequest.current) return
      setDetail(null)
      setError(cause instanceof RunRequestError ? cause.message : '运行详情读取失败。')
    } finally {
      if (requestId === detailRequest.current) setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadList()
  }, [loadList])
  useEffect(() => {
    setSelectedId(initialRunId ?? '')
  }, [initialRunId])
  useEffect(() => {
    if (selectedId) void loadDetail(selectedId)
    else {
      setDetail(null)
      setEvents([])
      sequence.current = 0
    }
  }, [selectedId, loadDetail])

  useEffect(() => {
    if (!selectedId || !active(detail?.state)) {
      setStreamState('closed')
      return
    }
    const controller = new AbortController()
    let refreshTimer: ReturnType<typeof setTimeout> | undefined
    setStreamState('connecting')
    void streamRunEvents(
      selectedId,
      controller.signal,
      sequence.current,
      (event) => {
        if (event.sequence <= sequence.current) return
        sequence.current = event.sequence
        setEvents((current) => [...current, event].slice(-128))
        if (refreshTimer) clearTimeout(refreshTimer)
        refreshTimer = setTimeout(() => {
          void loadDetail(selectedId)
        }, 120)
      },
      (status) => setStreamState(status),
    ).catch((cause) => {
      if (!controller.signal.aborted) {
        setStreamState('retrying')
        setError(
          cause instanceof RunRequestError ? cause.message : '事件流暂时中断，正在尝试续传。',
        )
      }
    })
    return () => {
      controller.abort()
      if (refreshTimer) clearTimeout(refreshTimer)
    }
  }, [selectedId, detail?.state, loadDetail])

  async function cancel() {
    if (!detail) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const updated = await agentRunsApi.cancel(detail.id)
      setDetail(updated)
      setMessage(
        updated.state === 'running' ? '已请求取消；当前节点完成后会停止后续节点。' : '运行已取消。',
      )
      await loadList()
    } catch (cause) {
      setError(cause instanceof RunRequestError ? cause.message : '取消请求失败。')
    } finally {
      setBusy(false)
    }
  }

  async function rerun(mode: 'snapshot' | 'latest') {
    if (!detail) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const created = await agentRunsApi.rerun(detail.id, { mode })
      await loadList()
      router.push(`/agents/runs/${created.id}`)
    } catch (cause) {
      setError(cause instanceof RunRequestError ? cause.message : '重跑创建失败。')
    } finally {
      setBusy(false)
    }
  }

  function selectRun(id: string) {
    setSelectedId(id)
    router.push(`/agents/runs/${id}`)
  }

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-5 py-8 md:px-8 md:py-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/agents" className="text-sm underline">
            ← Agent 工作台
          </Link>
          <p className="mt-3 text-sm text-muted-foreground">Phase 6 · 运行历史</p>
          <h1 className="text-3xl font-semibold">协作运行监控</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            查看节点进度与安全摘要；事件可从断线位置续传，节点输出仅对运行所有者可见。
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            void loadList()
            if (selectedId) void loadDetail(selectedId)
          }}
          disabled={loading || detailLoading}
          className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50"
        >
          刷新
        </button>
      </header>
      {error && (
        <p
          role="alert"
          className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
        >
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="rounded-lg border border-emerald-500/40 p-3 text-sm">
          {message}
        </p>
      )}
      <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside aria-label="运行历史" className="space-y-3 rounded-2xl border p-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">最近运行</h2>
            <span className="text-xs text-muted-foreground">{items.length}</span>
          </div>
          {loading ? (
            <p role="status" className="text-sm text-muted-foreground">
              正在加载运行…
            </p>
          ) : items.length === 0 ? (
            <div className="rounded-lg bg-muted/40 p-4 text-sm text-muted-foreground">
              <p>还没有运行记录。</p>
              <Link href="/agents/workflows" className="mt-3 inline-block underline">
                前往 Workflow 工作台 →
              </Link>
            </div>
          ) : (
            <ul className="space-y-2">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => selectRun(item.id)}
                    aria-current={selectedId === item.id ? 'true' : undefined}
                    className={`w-full rounded-xl border p-3 text-left transition-colors ${selectedId === item.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/40'}`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium">{item.id.slice(0, 8)}</span>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-xs ${stateStyle[item.state]}`}
                      >
                        {stateLabel[item.state]}
                      </span>
                    </span>
                    <span className="mt-2 block text-xs text-muted-foreground">
                      Workflow v{item.workflow_version} ·{' '}
                      {new Date(item.created_at).toLocaleString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section aria-label="运行详情" className="min-w-0 space-y-5 rounded-2xl border p-4 md:p-6">
          {!selectedId ? (
            <div className="grid min-h-64 place-items-center text-center">
              <div>
                <h2 className="font-semibold">选择一条运行记录</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  运行进度、节点输出和事件会显示在这里。
                </p>
              </div>
            </div>
          ) : detailLoading && !detail ? (
            <p role="status">正在加载运行详情…</p>
          ) : !detail ? (
            <div className="space-y-3">
              <p>运行详情暂不可用。</p>
              <button
                type="button"
                onClick={() => void loadDetail(selectedId)}
                className="rounded border px-3 py-2"
              >
                重试
              </button>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-mono text-xs text-muted-foreground">{detail.id}</p>
                  <h2 className="mt-1 text-xl font-semibold">
                    Workflow v{detail.workflow_version}
                  </h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {new Date(detail.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span aria-live="polite" className="text-xs text-muted-foreground">
                    {streamState === 'connected'
                      ? '实时连接中'
                      : streamState === 'retrying'
                        ? '断线，正在续传'
                        : streamState === 'connecting'
                          ? '正在连接事件流'
                          : '事件流已关闭'}
                  </span>
                  <span
                    className={`rounded-full border px-3 py-1 text-sm ${stateStyle[detail.state]}`}
                  >
                    {stateLabel[detail.state]}
                  </span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {active(detail.state) && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void cancel()}
                    className="rounded-lg border border-destructive/40 px-3 py-2 text-sm text-destructive disabled:opacity-50"
                  >
                    {detail.state === 'running' ? '请求取消' : '取消运行'}
                  </button>
                )}
                {!active(detail.state) && (
                  <>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void rerun('snapshot')}
                      className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50"
                    >
                      按原快照重跑
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void rerun('latest')}
                      className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50"
                    >
                      按最新 Workflow 重跑
                    </button>
                  </>
                )}
                {detail.cancel_requested && active(detail.state) && (
                  <span
                    role="status"
                    className="self-center text-sm text-amber-700 dark:text-amber-300"
                  >
                    取消已登记，等待当前节点结束
                  </span>
                )}
              </div>

              <section aria-label="节点拓扑" className="space-y-3 rounded-xl bg-muted/30 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-semibold">节点拓扑</h3>
                  <span className="text-xs text-muted-foreground">
                    {detail.charged_tokens.toLocaleString()} tokens · $
                    {(detail.charged_cost_microusd / 1_000_000).toFixed(4)}
                  </span>
                </div>
                <div className="flex flex-wrap items-stretch gap-3">
                  {orderedLayers.map((layer, index) => (
                    <div
                      key={index}
                      className="flex min-w-[150px] flex-1 flex-col gap-2 rounded-lg border border-dashed p-2"
                    >
                      <span className="text-xs text-muted-foreground">阶段 {index + 1}</span>
                      {layer.map((nodeId) => {
                        const node = detail.nodes.find((item) => item.node_id === nodeId)
                        const definition = detail.graph.nodes.find((item) => item.id === nodeId)
                        const nodeState = node?.state ?? 'pending'
                        return (
                          <div
                            key={nodeId}
                            className={`rounded-lg border p-3 ${stateStyle[nodeState]}`}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="break-all text-sm font-medium">
                                {definition?.label || nodeId}
                              </span>
                              <span className="text-xs">{stateLabel[nodeState]}</span>
                            </div>
                            {node?.error_code && (
                              <p className="mt-2 text-xs">
                                {labels[node.error_code] ?? '节点执行失败'}
                              </p>
                            )}
                            {node?.output && (
                              <details className="mt-2">
                                <summary className="cursor-pointer text-xs underline">
                                  查看节点输出
                                </summary>
                                <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-background/70 p-2 text-xs">
                                  {node.output}
                                </pre>
                              </details>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  ))}
                </div>
                {(detail.graph.edges ?? []).length > 0 && (
                  <p className="break-words text-xs text-muted-foreground">
                    依赖：
                    {detail.graph.edges
                      ?.map((edge) => `${edge.source} → ${edge.target}`)
                      .join('；')}
                  </p>
                )}
              </section>

              <section aria-label="运行事件" className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">事件记录</h3>
                  <span className="text-xs text-muted-foreground">最近 {events.length} 条</span>
                </div>
                {events.length === 0 ? (
                  <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                    等待运行事件…
                  </p>
                ) : (
                  <ol className="max-h-72 space-y-2 overflow-auto" aria-live="polite">
                    {events.map((event) => (
                      <li
                        key={event.sequence}
                        className="flex flex-wrap gap-x-3 gap-y-1 rounded-lg border px-3 py-2 text-xs"
                      >
                        <span className="font-mono text-muted-foreground">#{event.sequence}</span>
                        <span className="font-medium">
                          {event.node_id ? `${event.node_id} · ` : ''}
                          {event.event_type === 'run_finished'
                            ? '运行结束'
                            : event.event_type === 'run_started'
                              ? '运行开始'
                              : event.event_type === 'run_cancel_requested'
                                ? '收到取消请求'
                                : event.event_type === 'node_started'
                                  ? '节点开始'
                                  : event.event_type === 'node_finished'
                                    ? '节点结束'
                                    : '节点跳过'}
                        </span>
                        <span>{stateLabel[event.state]}</span>
                        {event.summary && (
                          <span className="text-muted-foreground">
                            {labels[event.summary] ?? event.summary}
                          </span>
                        )}
                        <time className="ml-auto text-muted-foreground">
                          {new Date(event.created_at).toLocaleTimeString()}
                        </time>
                      </li>
                    ))}
                  </ol>
                )}
              </section>
            </>
          )}
        </section>
      </div>
    </main>
  )
}
