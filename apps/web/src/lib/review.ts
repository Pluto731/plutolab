import { API_URL } from '@/lib/api'
import { getAccessToken } from '@/lib/auth'
import type { RepositoryRules, RulesUpdate } from './review-rules'

export interface Installation {
  installation_id: string
  active: boolean
  revoked_at: string | null
}
export interface Installations {
  installations: Installation[]
  github_account_id: string | null
}
export interface Repository {
  repo_id: string
  repo_name: string
  private: boolean
  default_branch: string
  enabled: boolean
  rules_version: number
}
export interface RepositoryPage {
  repositories: Repository[]
  total_count: number
  page: number
  per_page: number
}

export class ReviewRequestError extends Error {
  readonly status: number
  constructor(status: number) {
    const messages: Record<number, string> = {
      401: '登录已过期，请重新登录。',
      403: '无权访问或安装已停用，请刷新安装状态。',
      404: '未找到安装或仓库，请刷新列表。',
      409: '规则已被其他页面修改。你的输入已保留，请读取最新版本后确认再保存。',
      422: '请求未通过验证。请检查输入；搜索范围也可能超过服务上限。',
      429: '请求过于频繁，请稍后重试。',
    }
    super(messages[status] ?? '请求失败，请稍后重试。')
    this.name = 'ReviewRequestError'
    this.status = status
  }
}

const prefix = '/api/v1/review/installations'
function id(value: string): string {
  if (!/^[1-9][0-9]{0,19}$/.test(value)) throw new Error('无效的 GitHub ID。')
  return value
}
async function request<T>(
  path: string,
  method = 'GET',
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const token = getAccessToken()
  if (!token) throw new ReviewRequestError(401)
  let response: Response
  try {
    response = await fetch(`${API_URL}${prefix}${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      cache: 'no-store',
      redirect: 'error',
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    // Do not surface fetch URLs, callback state, or server response bodies.
    throw new ReviewRequestError(0)
  }
  if (!response.ok) throw new ReviewRequestError(response.status)
  return response.json() as Promise<T>
}

export const reviewApi = {
  installations: (signal?: AbortSignal) => request<Installations>('', 'GET', undefined, signal),
  start: () => request<{ installation_url: string }>('/start', 'POST'),
  bind: (installationId: string, state: string) =>
    request<Installation>('/callback', 'POST', { installation_id: id(installationId), state }),
  revoke: (installationId: string) => request<Installation>(`/${id(installationId)}`, 'DELETE'),
  repositories: (installationId: string, query: string, page: number, signal?: AbortSignal) =>
    request<RepositoryPage>(
      `/${id(installationId)}/repositories?${new URLSearchParams({ q: query, page: String(page), per_page: '10' })}`,
      'GET',
      undefined,
      signal,
    ),
  rules: (installationId: string, repoId: string, signal?: AbortSignal) =>
    request<RepositoryRules>(
      `/${id(installationId)}/repositories/${id(repoId)}/settings`,
      'GET',
      undefined,
      signal,
    ),
  save: (installationId: string, repoId: string, body: RulesUpdate) =>
    request<RepositoryRules>(
      `/${id(installationId)}/repositories/${id(repoId)}/settings`,
      'PUT',
      body,
    ),
}

export function installationUrl(value: string): string {
  const url = new URL(value)
  if (
    url.origin !== 'https://github.com' ||
    url.username ||
    url.password ||
    !/^\/apps\/[a-zA-Z0-9-]+\/installations\/new$/.test(url.pathname) ||
    !/^[A-Za-z0-9_-]{43}$/.test(url.searchParams.get('state') ?? '') ||
    [...url.searchParams.keys()].some((key) => key !== 'state') ||
    url.searchParams.getAll('state').length !== 1 ||
    url.hash
  ) {
    throw new Error('安装链接无效，请重新发起安装。')
  }
  return url.href
}

export function installationCallback(
  search: string,
): { installationId: string; state: string } | null {
  const params = new URLSearchParams(search)
  if (!params.has('state') && !params.has('installation_id')) return null
  if (
    params.getAll('state').length !== 1 ||
    params.getAll('installation_id').length !== 1 ||
    !/^[A-Za-z0-9_-]{43}$/.test(params.get('state') ?? '')
  ) {
    throw new Error('安装回调无效，请重新发起安装。')
  }
  return { installationId: id(params.get('installation_id') ?? ''), state: params.get('state')! }
}
