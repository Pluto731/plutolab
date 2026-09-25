import { API_URL } from '@/lib/api'
import { getAccessToken } from '@/lib/auth'
import type {
  WorkflowCreate,
  WorkflowPublic,
  WorkflowPage,
  WorkflowTemplatePage,
} from '../../../../packages/types/src/workflow'

export type { WorkflowCreate, WorkflowPublic }
export class WorkflowRequestError extends Error {
  constructor(readonly status: number) {
    super(
      status === 409
        ? '流程已被修改，请重载最新版本。'
        : status === 422
          ? '图配置或 Agent 引用无效，请检查连线并重新绑定最新 Agent。'
          : status === 401
            ? '请先登录。'
            : status === 404
              ? '流程已归档或不存在。'
              : '流程操作失败，草稿已保留，请重试。',
    )
  }
}
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const token = getAccessToken()
  if (!token) throw new WorkflowRequestError(401)
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/v1/workflows${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      cache: 'no-store',
      redirect: 'error',
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new WorkflowRequestError(0)
  }
  if (!response.ok) throw new WorkflowRequestError(response.status)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
export const workflowsApi = {
  list: (offset: number) => request<WorkflowPage>(`?limit=20&offset=${offset}`),
  templates: () => request<WorkflowTemplatePage>('/templates'),
  importTemplate: (slug: string, version: number) =>
    request<WorkflowPublic>(
      `/templates/${encodeURIComponent(slug)}/versions/${version}/import`,
      'POST',
      {},
    ),
  get: (id: string) => request<WorkflowPublic>(`/${encodeURIComponent(id)}`),
  save: (body: WorkflowCreate, current: WorkflowPublic | null) =>
    current
      ? request<WorkflowPublic>(`/${current.id}`, 'PUT', {
          ...body,
          expected_version: current.version,
        })
      : request<WorkflowPublic>('', 'POST', body),
  archive: (current: WorkflowPublic) =>
    request<void>(`/${current.id}?expected_version=${current.version}`, 'DELETE'),
}
