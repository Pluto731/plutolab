'use client'

import { useEffect, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ErrorNotice } from '@/components/ui/error-notice'
import { Skeleton } from '@/components/ui/skeleton'
import { reviewJobsApi } from '@/lib/review-jobs-api'
import {
  categoryLabel,
  groupFindings,
  jobStatus,
  processingLatency,
  publicationNotice,
  formatCoverage,
  type ReviewJobDetail as ReviewJob,
} from '@/lib/review-jobs'

const severitySections = [
  { key: 'critical', title: 'CRITICAL', label: '严重与高风险' },
  { key: 'warning', title: 'WARNING', label: '中风险' },
  { key: 'info', title: 'INFO', label: '低风险' },
] as const

const jobStatusText = {
  QUEUED: '排队中',
  ANALYZED: '已分析',
  PUBLISHED: '已发布',
  PARTIAL: '部分完成',
  FAILED: '失败',
} as const

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border p-4">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words font-medium">{value}</dd>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div aria-label="正在加载评审详情" className="space-y-5">
      <Skeleton className="h-24 w-full" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-20 w-full" />
        ))}
      </div>
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

export function ReviewJobDetail({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<ReviewJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setJob(null)
    setError(null)
    reviewJobsApi
      .detail(jobId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setJob(value)
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message)
      })
    return () => controller.abort()
  }, [jobId, retry])

  if (error) {
    return (
      <section aria-label="评审详情错误" className="space-y-3">
        <ErrorNotice message={error} />
        <Button variant="outline" onClick={() => setRetry((value) => value + 1)}>
          重试评审详情
        </Button>
      </section>
    )
  }
  if (!job) return <DetailSkeleton />

  const findings = groupFindings(job.findings)
  const status = jobStatus(job)
  const notice = publicationNotice(job)
  const coverage = job.coverage
  const cost = job.usage?.cost_usd ? `US$ ${job.usage.cost_usd}` : '未提供'
  const tokens =
    job.usage?.input_tokens != null || job.usage?.output_tokens != null
      ? `${formatTokens(job.usage?.input_tokens)} 输入 / ${formatTokens(job.usage?.output_tokens)} 输出`
      : '未提供'

  return (
    <article aria-label={`PR #${job.pr_number} 评审详情`} className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4 rounded-xl border bg-card p-5">
        <div className="min-w-0 space-y-2">
          <p className="text-sm text-muted-foreground">Pull Request</p>
          <h1 className="text-2xl font-semibold">PR #{job.pr_number} 评审结果</h1>
          <p className="break-all font-mono text-xs text-muted-foreground">Head: {job.head_sha}</p>
        </div>
        <Badge
          variant={status === 'FAILED' ? 'destructive' : 'outline'}
          className={status === 'PARTIAL' ? 'border-amber-500 text-amber-700' : ''}
        >
          {jobStatusText[status]}
        </Badge>
      </header>

      <section aria-label="任务指标">
        <h2 className="mb-3 text-lg font-semibold">处理概况</h2>
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="处理耗时" value={processingLatency(job)} />
          <Metric label="Token 估算" value={tokens} />
          <Metric label="费用估算" value={cost} />
          <Metric label="评审覆盖" value={formatCoverage(job.coverage)} />
        </dl>
        {(coverage?.truncated || (coverage?.gaps?.length ?? 0) > 0) && (
          <div className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-sm">
            <p className="font-medium">{coverage?.truncated ? '评审内容已截断' : '存在覆盖缺口'}</p>
            {coverage?.truncation_reason && <p className="mt-1">{coverage.truncation_reason}</p>}
            {!!coverage?.gaps?.length && (
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {coverage.gaps.map((gap, index) => (
                  <li key={`${index}:${gap}`}>{gap}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {notice && (
        <section
          aria-label="GitHub 评论发布状态"
          className={`rounded-xl border p-4 text-sm ${
            status === 'PARTIAL' ? 'border-amber-500/40 bg-amber-500/5' : 'bg-card'
          }`}
        >
          <h2 className="font-semibold">GitHub 评论发布</h2>
          <p className="mt-1">{notice}</p>
          {job.publication?.github_review_ids?.length ? (
            <p className="mt-2 text-xs text-muted-foreground">
              已确认评论记录：{job.publication.github_review_ids.join(', ')}
            </p>
          ) : null}
        </section>
      )}

      {job.summary && (
        <section className="rounded-xl border bg-card p-5">
          <h2 className="text-lg font-semibold">评审摘要</h2>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{job.summary}</p>
        </section>
      )}

      <section aria-label="结构化发现" className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">结构化发现</h2>
          <p className="text-sm text-muted-foreground">每条发现按风险级别与评审类别分组。</p>
        </div>
        {severitySections.map(({ key, title, label }) => {
          const items = findings[key]
          return (
            <section key={key} aria-label={label} className="rounded-xl border bg-card p-5">
              <h3 className="font-semibold">
                {title} <span className="text-muted-foreground">({items.length})</span>
              </h3>
              {items.length === 0 ? (
                <p className="mt-3 text-sm text-muted-foreground">此级别没有发现。</p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {items.map((finding) => (
                    <li key={finding.id} className="rounded-lg border p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{categoryLabel(finding.focus)}</Badge>
                        <Badge
                          variant={finding.severity === 'CRITICAL' ? 'destructive' : 'secondary'}
                        >
                          {finding.severity}
                        </Badge>
                        <span className="break-all font-mono text-xs text-muted-foreground">
                          {finding.location.path}:{finding.location.line} · {finding.location.side}
                          {finding.verified_diff?.position != null
                            ? ` · 已验证 diff position ${finding.verified_diff.position}`
                            : ' · diff 映射未确认'}
                        </span>
                      </div>
                      <p className="mt-3 text-sm leading-6">{finding.description}</p>
                      {finding.evidence && (
                        <p className="mt-2 text-sm text-muted-foreground">
                          依据：{finding.evidence}
                        </p>
                      )}
                      {finding.suggestion && (
                        <pre className="mt-3 overflow-x-auto rounded-md bg-muted p-3 text-xs">
                          <code>{finding.suggestion}</code>
                        </pre>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )
        })}
      </section>
    </article>
  )
}

function formatTokens(value: number | null | undefined): string {
  return value == null ? '—' : new Intl.NumberFormat('en-US').format(value)
}
