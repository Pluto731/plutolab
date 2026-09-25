import { API_URL } from '@/lib/api'
import { getAccessToken } from '@/lib/auth'
import type {
  RunDetail,
  RunCreate,
  RunEvent,
  RunEventPage,
  RunPage,
  RunRerun,
  RunSummary,
} from '../../../../packages/types/src/agent-run'

export class RunRequestError extends Error {
  constructor(readonly status: number) {
    super(
      status === 0
        ? '请求超时或连接中断，创建结果暂不确定。请先查看运行历史，或使用原请求重试。'
        : status === 401
          ? '请先登录。'
          : status === 404
            ? '运行不存在或已过期。'
            : status === 409
              ? '幂等键冲突，请刷新后重试。'
              : status === 410
                ? '事件游标已过期，请刷新运行详情。'
                : '运行请求失败，请重试。',
    )
  }
}

/** getRandomValues also works on HTTP origins; this key is an opaque request identifier. */
export function createRunKey(): string {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

async function request<T>(
  path: string,
  method = 'GET',
  body?: unknown,
  idempotencyKey?: string,
): Promise<T> {
  const token = getAccessToken()
  if (!token) throw new RunRequestError(401)
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 20000)
  try {
    const response = await fetch(`${API_URL}/api/v1${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
      },
      cache: 'no-store',
      redirect: 'error',
      signal: controller.signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) throw new RunRequestError(response.status)
    return (await response.json()) as T
  } catch (cause) {
    if (cause instanceof RunRequestError) throw cause
    throw new RunRequestError(0)
  } finally {
    clearTimeout(timeout)
  }
}

export const agentRunsApi = {
  create: (workflowId: string, body: RunCreate, idempotencyKey: string) =>
    request<RunSummary>(
      `/workflows/${encodeURIComponent(workflowId)}/runs`,
      'POST',
      body,
      idempotencyKey,
    ),
  list: (offset = 0) => request<RunPage>(`/runs?limit=20&offset=${offset}`),
  get: (id: string) => request<RunDetail>(`/runs/${encodeURIComponent(id)}`),
  events: (id: string, after = 0) =>
    request<RunEventPage>(`/runs/${encodeURIComponent(id)}/events?after=${after}&limit=128`),
  cancel: (id: string) => request<RunDetail>(`/runs/${encodeURIComponent(id)}/cancel`, 'POST'),
  rerun: (id: string, body: RunRerun) =>
    request<RunSummary>(`/runs/${encodeURIComponent(id)}/rerun`, 'POST', body, createRunKey()),
}

const pause = (milliseconds: number, signal: AbortSignal) =>
  new Promise<void>((resolve) => {
    const done = () => {
      clearTimeout(timer)
      signal.removeEventListener('abort', done)
      resolve()
    }
    const timer = setTimeout(done, milliseconds)
    signal.addEventListener('abort', done, { once: true })
  })

/** Fetch-based SSE is used so the authenticated bearer token never enters a URL. */
export async function streamRunEvents(
  id: string,
  signal: AbortSignal,
  initialCursor: number,
  onEvent: (event: RunEvent) => void,
  onStatus: (status: 'connected' | 'retrying') => void,
): Promise<void> {
  const token = getAccessToken()
  if (!token) throw new RunRequestError(401)
  let cursor = initialCursor
  let retry = 500
  while (!signal.aborted) {
    try {
      const response = await fetch(
        `${API_URL}/api/v1/runs/${encodeURIComponent(id)}/events/stream`,
        {
          headers: { Authorization: `Bearer ${token}`, 'Last-Event-ID': String(cursor) },
          cache: 'no-store',
          redirect: 'error',
          signal,
        },
      )
      if (!response.ok || !response.body) throw new RunRequestError(response.status)
      onStatus('connected')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let terminal = false
      while (!signal.aborted) {
        const chunk = await reader.read()
        if (chunk.done) break
        buffer += decoder.decode(chunk.value, { stream: true }).replaceAll('\r\n', '\n')
        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() ?? ''
        for (const block of blocks) {
          let eventType = 'message'
          let eventId = ''
          const data: string[] = []
          for (const line of block.split('\n')) {
            if (line.startsWith(':')) continue
            const colon = line.indexOf(':')
            const field = colon < 0 ? line : line.slice(0, colon)
            const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '')
            if (field === 'event') eventType = value
            if (field === 'id') eventId = value
            if (field === 'data') data.push(value)
          }
          if (eventId && /^\d+$/.test(eventId)) cursor = Number(eventId)
          if (eventType === 'run_expired') return
          if (eventType === 'run_finished') terminal = true
          if (
            eventType === 'node_started' ||
            eventType === 'node_finished' ||
            eventType === 'node_skipped' ||
            eventType === 'run_started' ||
            eventType === 'run_cancel_requested' ||
            eventType === 'run_finished'
          ) {
            try {
              onEvent(JSON.parse(data.join('\n')) as RunEvent)
            } catch {
              /* ignore malformed event payload */
            }
          }
        }
      }
      if (terminal || signal.aborted) return
    } catch (error) {
      if (signal.aborted) return
      if (error instanceof RunRequestError && error.status !== 0) throw error
      onStatus('retrying')
    }
    await pause(retry, signal)
    retry = Math.min(8000, retry * 2)
  }
}
