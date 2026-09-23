import { API_URL } from '@/lib/api'
import { getAccessToken } from '@/lib/auth'
import type { JobStatus, ReviewJobDetail, ReviewJobPage } from './review-jobs'

export class ReviewJobsRequestError extends Error {
  readonly status: number

  constructor(status: number) {
    super(
      status === 404
        ? '评审任务读取接口尚不可用或任务已不存在。'
        : status === 401
          ? '登录已过期，请重新登录。'
          : '评审任务暂时无法读取，请重试。',
    )
    this.name = 'ReviewJobsRequestError'
    this.status = status
  }
}

function decimalId(value: string): string {
  if (!/^[1-9]\d{0,19}$/.test(value)) throw new Error('无效的 GitHub ID。')
  return value
}

function uuid(value: string): string {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) {
    throw new Error('无效的评审任务 ID。')
  }
  return value
}

async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const token = getAccessToken()
  if (!token) throw new ReviewJobsRequestError(401)
  let response: Response
  try {
    response = await fetch(`${API_URL}/api/v1/review${path}`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      cache: 'no-store',
      redirect: 'error',
      signal,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new ReviewJobsRequestError(0)
  }
  if (!response.ok) throw new ReviewJobsRequestError(response.status)
  try {
    return (await response.json()) as T
  } catch {
    throw new ReviewJobsRequestError(502)
  }
}

export const reviewJobsApi = {
  list(
    installationId: string,
    repoId: string,
    page: number,
    prNumber?: number,
    status?: JobStatus,
    signal?: AbortSignal,
  ): Promise<ReviewJobPage> {
    decimalId(installationId)
    decimalId(repoId)
    if (!Number.isSafeInteger(page) || page < 1 || page > 1000) {
      throw new Error('无效的任务分页。')
    }
    if (prNumber != null && (!Number.isSafeInteger(prNumber) || prNumber < 1)) {
      throw new Error('PR 编号必须为正整数。')
    }
    const query = new URLSearchParams({
      installation_id: installationId,
      repo_id: repoId,
      page: String(page),
      per_page: '20',
    })
    if (prNumber != null) query.set('pr_number', String(prNumber))
    if (status) query.set('status', status)
    return read(`/jobs?${query.toString()}`, signal)
  },

  detail(jobId: string, signal?: AbortSignal): Promise<ReviewJobDetail> {
    uuid(jobId)
    return read(`/jobs/${jobId}`, signal)
  },
}
