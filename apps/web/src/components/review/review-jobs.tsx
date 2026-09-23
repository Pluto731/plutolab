'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { ErrorNotice } from '@/components/ui/error-notice'
import { Skeleton } from '@/components/ui/skeleton'
import { reviewApi, type Installations, type RepositoryPage } from '@/lib/review'
import { reviewJobsApi } from '@/lib/review-jobs-api'
import {
  filterJobsByPullRequest,
  jobStatus,
  parsePullRequestFilter,
  type JobStatus,
  type ReviewJobPage,
} from '@/lib/review-jobs'

const statusLabel = {
  QUEUED: '排队中',
  ANALYZED: '已分析',
  PUBLISHED: '已发布',
  PARTIAL: '部分完成',
  FAILED: '失败',
} as const

const statusStyle = {
  QUEUED: 'border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-300',
  ANALYZED: 'border-violet-500/40 bg-violet-500/10 text-violet-700 dark:text-violet-300',
  PUBLISHED: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  PARTIAL: 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  FAILED: 'border-destructive/40 bg-destructive/10 text-destructive',
} as const

function LoadingRows() {
  return (
    <div aria-label="正在加载评审任务" className="space-y-3">
      {Array.from({ length: 4 }, (_, index) => (
        <Skeleton key={index} className="h-20 w-full" />
      ))}
    </div>
  )
}

export function ReviewJobs() {
  const [installations, setInstallations] = useState<Installations | null>(null)
  const [installationId, setInstallationId] = useState('')
  const [installationError, setInstallationError] = useState<string | null>(null)
  const [installationRetry, setInstallationRetry] = useState(0)
  const [repositories, setRepositories] = useState<RepositoryPage | null>(null)
  const [repositoryError, setRepositoryError] = useState<string | null>(null)
  const [repositoryRetry, setRepositoryRetry] = useState(0)
  const [repositoryQuery, setRepositoryQuery] = useState('')
  const [repositorySearch, setRepositorySearch] = useState('')
  const [repositoryId, setRepositoryId] = useState('')
  const [prDraft, setPrDraft] = useState('')
  const [prFilter, setPrFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<JobStatus | ''>('')
  const [filterError, setFilterError] = useState<string | null>(null)
  const [jobPage, setJobPage] = useState<ReviewJobPage | null>(null)
  const [jobError, setJobError] = useState<string | null>(null)
  const [jobRetry, setJobRetry] = useState(0)
  const [page, setPage] = useState(1)

  useEffect(() => {
    const controller = new AbortController()
    setInstallations(null)
    setInstallationError(null)
    reviewApi
      .installations(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        setInstallations(value)
        const first = value.installations.find((item) => item.active)
        if (first && !value.installations.some((item) => item.installation_id === installationId)) {
          setInstallationId(first.installation_id)
        }
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setInstallationError(error.message)
      })
    return () => controller.abort()
  }, [installationId, installationRetry])

  useEffect(() => {
    if (!installationId) {
      setRepositories(null)
      setRepositoryId('')
      return
    }
    const controller = new AbortController()
    setRepositories(null)
    setRepositoryError(null)
    setRepositoryId('')
    reviewApi
      .repositories(installationId, repositorySearch, 1, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        setRepositories(value)
        if (value.repositories.length === 1) setRepositoryId(value.repositories[0].repo_id)
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setRepositoryError(error.message)
      })
    return () => controller.abort()
  }, [installationId, repositorySearch, repositoryRetry])

  useEffect(() => {
    if (!installationId || !repositoryId) {
      setJobPage(null)
      setJobError(null)
      return
    }
    const controller = new AbortController()
    setJobPage(null)
    setJobError(null)
    const prNumber = prFilter ? Number(prFilter) : undefined
    reviewJobsApi
      .list(
        installationId,
        repositoryId,
        page,
        prNumber,
        statusFilter || undefined,
        controller.signal,
      )
      .then((value) => {
        if (!controller.signal.aborted) setJobPage(value)
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setJobError(error.message)
      })
    return () => controller.abort()
  }, [installationId, repositoryId, page, prFilter, statusFilter, jobRetry])

  const visibleJobs = useMemo(
    () => filterJobsByPullRequest(jobPage?.jobs ?? [], prFilter),
    [jobPage, prFilter],
  )
  const activeInstallations = installations?.installations.filter((item) => item.active) ?? []

  return (
    <section aria-label="评审任务" className="space-y-6">
      <div className="grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-2">
        <label className="grid gap-2 text-sm font-medium">
          GitHub App 安装
          <select
            aria-label="GitHub App 安装"
            className="h-10 rounded-md border bg-background px-3 font-normal"
            disabled={activeInstallations.length === 0}
            value={installationId}
            onChange={(event) => {
              setInstallationId(event.target.value)
              setPage(1)
              setPrFilter('')
            }}
          >
            <option value="">选择安装</option>
            {activeInstallations.map((item) => (
              <option key={item.installation_id} value={item.installation_id}>
                安装 {item.installation_id}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-2 text-sm font-medium">
          仓库
          <select
            aria-label="评审仓库"
            className="h-10 rounded-md border bg-background px-3 font-normal"
            disabled={!repositories?.repositories.length}
            value={repositoryId}
            onChange={(event) => {
              setRepositoryId(event.target.value)
              setPage(1)
            }}
          >
            <option value="">选择仓库</option>
            {repositories?.repositories.map((repo) => (
              <option key={repo.repo_id} value={repo.repo_id}>
                {repo.repo_name}
              </option>
            ))}
          </select>
        </label>
        <form
          className="flex items-end gap-2 sm:col-span-2"
          onSubmit={(event) => {
            event.preventDefault()
            setRepositoryId('')
            setRepositorySearch(repositoryQuery.trim())
            setPage(1)
          }}
        >
          <label className="grid min-w-0 flex-1 gap-2 text-sm font-medium">
            仓库关键词
            <input
              aria-label="搜索仓库"
              className="h-10 rounded-md border bg-background px-3 font-normal"
              maxLength={100}
              value={repositoryQuery}
              onChange={(event) => setRepositoryQuery(event.target.value)}
            />
          </label>
          <Button type="submit" variant="outline">
            搜索仓库
          </Button>
        </form>
        <form
          className="flex flex-wrap gap-2 sm:col-span-2"
          onSubmit={(event) => {
            event.preventDefault()
            const parsed = parsePullRequestFilter(prDraft)
            if (parsed.error) {
              setFilterError(parsed.error)
              return
            }
            setFilterError(null)
            setPrFilter(parsed.value)
            setPage(1)
          }}
        >
          <input
            aria-label="按 PR 编号筛选"
            className="h-10 min-w-0 flex-1 rounded-md border bg-background px-3 text-sm"
            inputMode="numeric"
            maxLength={10}
            placeholder="按 PR 编号筛选（可选）"
            value={prDraft}
            onChange={(event) => setPrDraft(event.target.value)}
          />
          <select
            aria-label="按状态筛选"
            className="h-10 rounded-md border bg-background px-3 text-sm"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value as JobStatus | '')
              setPage(1)
            }}
          >
            <option value="">全部状态</option>
            <option value="QUEUED">排队中</option>
            <option value="ANALYZED">已分析</option>
            <option value="PUBLISHED">已发布</option>
            <option value="PARTIAL">部分完成</option>
            <option value="FAILED">失败</option>
          </select>
          <Button type="submit" variant="outline">
            筛选
          </Button>
          {prFilter && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setPrDraft('')
                setPrFilter('')
                setPage(1)
              }}
            >
              清除
            </Button>
          )}
        </form>
      </div>

      <ErrorNotice message={filterError} />
      {installationError ? (
        <div className="space-y-3">
          <ErrorNotice message={installationError} />
          <Button variant="outline" onClick={() => setInstallationRetry((value) => value + 1)}>
            重试安装列表
          </Button>
        </div>
      ) : !installations ? (
        <LoadingRows />
      ) : activeInstallations.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center">
          <p className="font-medium">尚未绑定有效的 GitHub App 安装</p>
          <Link className="mt-3 inline-block text-primary underline" href="/review/settings">
            前往安装与仓库设置
          </Link>
        </div>
      ) : repositoryError ? (
        <div className="space-y-3">
          <ErrorNotice message={repositoryError} />
          <Button variant="outline" onClick={() => setRepositoryRetry((value) => value + 1)}>
            重试仓库列表
          </Button>
        </div>
      ) : !repositories ? (
        <LoadingRows />
      ) : repositories.repositories.length === 0 ? (
        <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
          没有匹配的仓库。调整仓库筛选或前往评审设置检查授权。
        </p>
      ) : !repositoryId ? (
        <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
          请选择仓库以查看历史评审任务。
        </p>
      ) : jobError ? (
        <div className="space-y-3">
          <ErrorNotice message={jobError} />
          <Button variant="outline" onClick={() => setJobRetry((value) => value + 1)}>
            重试任务列表
          </Button>
        </div>
      ) : !jobPage ? (
        <LoadingRows />
      ) : visibleJobs.length === 0 ? (
        <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
          {prFilter ? `没有 PR #${prFilter} 的评审任务。` : '此仓库还没有历史评审任务。'}
        </p>
      ) : (
        <>
          <ul aria-label="评审任务列表" className="divide-y rounded-xl border bg-card">
            {visibleJobs.map((job) => {
              const status = jobStatus(job)
              return (
                <li key={job.id}>
                  <Link
                    className="flex flex-wrap items-center justify-between gap-3 p-4 transition-colors hover:bg-muted/50"
                    href={`/review/jobs/${encodeURIComponent(job.id)}`}
                  >
                    <span className="min-w-0">
                      <span className="block font-medium">PR #{job.pr_number}</span>
                      <span className="block truncate font-mono text-xs text-muted-foreground">
                        {job.head_sha}
                      </span>
                    </span>
                    <span className="flex items-center gap-3">
                      <span
                        className={`rounded-md border px-2 py-1 text-xs ${statusStyle[status]}`}
                      >
                        {statusLabel[status]}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {job.created_at ? new Date(job.created_at).toLocaleString() : '时间未提供'}
                      </span>
                    </span>
                  </Link>
                </li>
              )
            })}
          </ul>
          <nav aria-label="评审任务分页" className="flex items-center justify-between gap-3">
            <Button
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage((current) => current - 1)}
            >
              上一页
            </Button>
            <span className="text-sm text-muted-foreground">
              第 {jobPage.page} 页 · 共 {jobPage.total_count} 个任务
            </span>
            <Button
              variant="outline"
              disabled={page * jobPage.per_page >= jobPage.total_count}
              onClick={() => setPage((current) => current + 1)}
            >
              下一页
            </Button>
          </nav>
        </>
      )}
    </section>
  )
}
