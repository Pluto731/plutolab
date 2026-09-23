/** Phase 5 v1 wire-contract drafts. Runtime checks live in future service slices.
 * UUID, GitHub IDs, SHAs, timestamps and decimal USD amounts serialize as strings.
 * Numeric values are nonnegative/positive integers as constrained in review.py.
 */
export type GitHubId = string
export type HeadSha = string
export type MoneyUSD = string // Fixed six decimal places; never a JS float.
export type Focus = 'security' | 'performance' | 'quality'
export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
export type AnalysisStatus =
  | 'draft' | 'queued' | 'processing' | 'analyzed' | 'partial'
  | 'failed' | 'skipped' | 'superseded' | 'cancelled'
export type PublicationStatus =
  | 'not_requested' | 'preview_ready' | 'publishing' | 'published'
  | 'partially_published' | 'publish_unknown' | 'failed' | 'blocked'
export type ErrorCode =
  | 'validation_failed' | 'access_denied' | 'installation_revoked' | 'stale_head'
  | 'budget_exceeded' | 'diff_unavailable' | 'provider_failed' | 'invalid_findings'
  | 'rate_limited' | 'persistence_failed' | 'publication_failed' | 'publication_unknown'
  | 'cancelled' | 'not_applicable'

export const ANALYSIS_TRANSITIONS = {
  draft: ['queued', 'cancelled'],
  queued: ['processing', 'skipped', 'superseded', 'cancelled'],
  processing: ['queued', 'analyzed', 'partial', 'failed', 'superseded', 'cancelled'],
  analyzed: ['superseded'], partial: ['superseded'],
  failed: [], skipped: [], superseded: [], cancelled: [],
} as const satisfies Record<AnalysisStatus, readonly AnalysisStatus[]>

export const PUBLICATION_TRANSITIONS = {
  not_requested: ['preview_ready', 'blocked'],
  preview_ready: ['publishing', 'blocked'],
  publishing: ['published', 'partially_published', 'publish_unknown', 'failed', 'blocked'],
  published: [],
  partially_published: ['publishing', 'publish_unknown', 'blocked'],
  publish_unknown: ['published', 'partially_published', 'preview_ready', 'blocked'],
  failed: ['preview_ready', 'blocked'], blocked: [],
} as const satisfies Record<PublicationStatus, readonly PublicationStatus[]>

export interface ReviewOwner { user_id: string; installation_id: GitHubId }
export interface ReviewRepository { id: GitHubId; owner_login: string; name: string }
export interface ReviewBudgets {
  max_files: number
  min_changed_lines: number
  max_changed_lines: number
  max_context_lines_per_file: number
  max_chunks: number
  context_window_tokens: number
  max_request_input_tokens: number
  reserved_output_tokens: number
  max_total_input_tokens: number
  max_total_output_tokens: number
  max_findings: number
  max_comments: number
  max_cost_usd: MoneyUSD
  max_owner_daily_cost_usd: MoneyUSD
  token_count_mode: 'provider_exact' | 'conservative_estimate'
}
export interface ReviewPolicy {
  rules_version: number
  enabled: boolean
  focus: Focus[]
  skip_paths: string[]
  provider: 'anthropic'
  model: string
  budgets: ReviewBudgets
  publication_mode: 'preview_only' | 'comment'
}
export interface ReviewIdentity {
  contract_version: '1'
  review_id: string
  owner: ReviewOwner
  repo: ReviewRepository
  pr_number: number
  head_sha: HeadSha
  policy: ReviewPolicy
}
export interface FindingLocation { path: string; line: number; side: 'LEFT' | 'RIGHT' }
export interface ReviewFinding {
  id: string
  fingerprint: string
  focus: Focus
  severity: Severity
  location: FindingLocation
  description: string
  suggestion: string
  evidence: string
}
export interface ReviewError {
  code: ErrorCode
  message: string
  retryable: boolean
  request_id: string
  retry_after_seconds: number | null
}
export interface ReviewHTTPError { detail: ReviewError }
export interface ReviewCoverage {
  files_total: number
  files_reviewed: number
  changed_lines_total: number
  changed_lines_reviewed: number
  gaps: string[]
}
export interface ReviewUsage {
  input_tokens: number
  output_tokens: number
  cost_usd: MoneyUSD
  token_count_mode: 'provider_exact' | 'conservative_estimate'
}
export interface AnalysisDraft { status: 'draft' | 'queued' | 'processing' }
export interface AnalysisResult {
  status: 'analyzed' | 'partial'
  summary: string
  findings: ReviewFinding[]
  coverage: ReviewCoverage
  usage: ReviewUsage
}
export interface AnalysisStopped {
  status: 'failed' | 'skipped' | 'superseded' | 'cancelled'
  error: ReviewError
}
export type Analysis = AnalysisDraft | AnalysisResult | AnalysisStopped
export interface PublicationDraft { status: 'not_requested' | 'preview_ready' }
export interface PublicationAttempt {
  status: 'publishing'
  attempt_id: string
  head_sha: HeadSha
  event: 'COMMENT'
}
export interface PublicationReceipt {
  status: 'published' | 'partially_published'
  attempt_id: string
  head_sha: HeadSha
  event: 'COMMENT'
  github_review_ids: GitHubId[]
  confirmed_at: string
}
export interface PublicationUnknown {
  status: 'publish_unknown'
  attempt_id: string
  head_sha: HeadSha
  error: ReviewError
}
export interface PublicationStopped { status: 'failed' | 'blocked'; error: ReviewError }
export type Publication =
  | PublicationDraft | PublicationAttempt | PublicationReceipt
  | PublicationUnknown | PublicationStopped
export interface ReviewRecord extends ReviewIdentity {
  analysis: Analysis
  publication: Publication
}
