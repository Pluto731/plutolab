export type AnalysisState =
  | 'draft'
  | 'queued'
  | 'processing'
  | 'analyzed'
  | 'partial'
  | 'failed'
  | 'skipped'
  | 'superseded'
  | 'cancelled'
export type PublicationState =
  | 'not_requested'
  | 'preview_ready'
  | 'publishing'
  | 'published'
  | 'partially_published'
  | 'publish_unknown'
  | 'failed'
  | 'blocked'
export type JobStatus = 'QUEUED' | 'ANALYZED' | 'PUBLISHED' | 'PARTIAL' | 'FAILED'
export type FindingSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
export type FindingFocus = 'security' | 'performance' | 'quality'

export interface VerifiedDiffPosition {
  path: string
  line: number
  side: 'LEFT' | 'RIGHT'
  position: number
  comment_context: string
}

export interface ReviewJobSummary {
  id: string
  installation_id: string
  repo_id: string
  pr_number: number
  head_sha: string
  analysis_status: AnalysisState
  publication_status: PublicationState
  publication_fallback_reason?: 'diff_position_mismatch' | null
  created_at?: string | null
  processing_started_at?: string | null
  completed_at?: string | null
}

export interface ReviewFindingView {
  id: string
  severity: FindingSeverity
  focus: FindingFocus
  location: { path: string; line: number; side: 'LEFT' | 'RIGHT' }
  verified_diff: VerifiedDiffPosition | null
  description: string
  suggestion?: string | null
  evidence?: string | null
}

export interface ReviewJobDetail extends ReviewJobSummary {
  summary?: string | null
  coverage?: {
    files_total?: number | null
    files_reviewed?: number | null
    changed_lines_total?: number | null
    changed_lines_reviewed?: number | null
    gaps?: string[] | null
    truncated?: boolean | null
    truncation_reason?: string | null
  } | null
  usage?: {
    input_tokens?: number | null
    output_tokens?: number | null
    cost_usd?: string | null
  } | null
  findings?: ReviewFindingView[] | null
  publication?: {
    status?: PublicationState | null
    github_review_ids?: string[] | null
  } | null
}

export interface ReviewJobPage {
  jobs: ReviewJobSummary[]
  total_count: number
  page: number
  per_page: number
}

export interface GroupedFindings {
  critical: ReviewFindingView[]
  warning: ReviewFindingView[]
  info: ReviewFindingView[]
}

export function jobStatus(
  job: Pick<ReviewJobSummary, 'analysis_status' | 'publication_status'>,
): JobStatus {
  if (job.analysis_status === 'failed' || job.publication_status === 'failed') return 'FAILED'
  if (
    job.analysis_status === 'partial' ||
    job.publication_status === 'partially_published' ||
    job.publication_status === 'publish_unknown'
  ) {
    return 'PARTIAL'
  }
  if (job.publication_status === 'published') return 'PUBLISHED'
  if (job.analysis_status === 'analyzed') return 'ANALYZED'
  return 'QUEUED'
}

export function filterJobsByPullRequest(
  jobs: readonly ReviewJobSummary[],
  input: string,
): ReviewJobSummary[] {
  const query = input.trim()
  if (!query) return [...jobs]
  if (!/^[1-9]\d{0,9}$/.test(query)) return []
  const prNumber = Number(query)
  return jobs.filter((job) => job.pr_number === prNumber)
}

export function parsePullRequestFilter(input: string): { value: string; error: string | null } {
  const value = input.trim()
  if (!value) return { value: '', error: null }
  return /^[1-9]\d{0,9}$/.test(value) && Number.isSafeInteger(Number(value))
    ? { value, error: null }
    : { value: '', error: 'PR 编号必须为正整数。' }
}

export function groupFindings(
  findings: readonly ReviewFindingView[] | null | undefined,
): GroupedFindings {
  const groups: GroupedFindings = { critical: [], warning: [], info: [] }
  for (const finding of findings ?? []) {
    if (finding.severity === 'CRITICAL' || finding.severity === 'HIGH') {
      groups.critical.push(finding)
    } else if (finding.severity === 'MEDIUM') {
      groups.warning.push(finding)
    } else {
      groups.info.push(finding)
    }
  }
  return groups
}

export function categoryLabel(focus: FindingFocus): string {
  return { security: 'SECURITY', performance: 'PERFORMANCE', quality: 'QUALITY' }[focus]
}

export function processingLatency(job: ReviewJobSummary, now = Date.now()): string {
  const start = Date.parse(job.processing_started_at ?? job.created_at ?? '')
  if (!Number.isFinite(start)) return '未提供'
  const end = Date.parse(job.completed_at ?? '')
  const elapsedMs = Math.max(0, (Number.isFinite(end) ? end : now) - start)
  if (elapsedMs < 1000) return `${elapsedMs} 毫秒`
  if (elapsedMs < 60_000) return `${(elapsedMs / 1000).toFixed(1)} 秒`
  return `${Math.floor(elapsedMs / 60_000)} 分 ${Math.floor((elapsedMs % 60_000) / 1000)} 秒`
}

export function publicationNotice(job: ReviewJobDetail): string | null {
  const status = job.publication?.status ?? job.publication_status
  if (status === 'partially_published') {
    if (job.publication_fallback_reason === 'diff_position_mismatch') {
      return 'GitHub 拒绝了部分 diff 行内位置（422）；已回退发布顶层摘要。'
    }
    return '评审结果仅部分发布，请查看摘要中的未交付说明。'
  }
  if (status === 'publish_unknown') return 'GitHub 发布结果尚未确认，正在等待安全核对。'
  if (status === 'published') return 'GitHub 评审评论已确认发布。'
  if (status === 'failed') return 'GitHub 评论发布失败；评审分析结果仍可查看。'
  if (status === 'publishing') return '评审评论正在提交到 GitHub。'
  if (status === 'blocked') return '当前任务未获准发布 GitHub 评论。'
  return '评审结果尚未发布为 GitHub 评论。'
}

export function formatCoverage(value: ReviewJobDetail['coverage']): string {
  if (!value) return '暂无覆盖率数据'
  const reviewed = value.changed_lines_reviewed
  const total = value.changed_lines_total
  const lines = reviewed != null && total != null ? `${reviewed} / ${total} 行` : '行数未提供'
  const files =
    value.files_reviewed != null && value.files_total != null
      ? `${value.files_reviewed} / ${value.files_total} 个文件`
      : '文件数未提供'
  return `${lines} · ${files}`
}
