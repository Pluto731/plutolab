import { API_URL } from '@/lib/api'
import { getAccessToken } from '@/lib/auth'
import type { AgentCreate, AgentPage, AgentPublic } from '../../../../packages/types/src/agent'

export type { AgentCreate, AgentPublic }
export class AgentRequestError extends Error {
  constructor(readonly status: number) {
    super(
      status === 409
        ? '配置已被修改，请重新加载后再编辑。'
        : status === 401
          ? '请先登录。'
          : status === 404
            ? 'Agent 已不存在，请刷新列表。'
            : '操作失败，请重试。',
    )
  }
}
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const token = getAccessToken()
  if (!token) throw new AgentRequestError(401)
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/v1/agents${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      cache: 'no-store',
      redirect: 'error',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new AgentRequestError(0)
  }
  if (!response.ok) throw new AgentRequestError(response.status)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
export const agentsApi = {
  list: (offset: number) => request<AgentPage>(`?limit=20&offset=${offset}`),
  save: (body: AgentCreate, current: AgentPublic | null) =>
    current
      ? request<AgentPublic>(`/${current.id}`, 'PUT', {
          ...body,
          expected_version: current.version,
        })
      : request<AgentPublic>('', 'POST', body),
  archive: (current: AgentPublic) =>
    request<void>(`/${current.id}?expected_version=${current.version}`, 'DELETE'),
}
