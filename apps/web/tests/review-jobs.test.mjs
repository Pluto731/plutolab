import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import vm from 'node:vm'
import {
  filterJobsByPullRequest,
  formatCoverage,
  groupFindings,
  jobStatus,
  parsePullRequestFilter,
  processingLatency,
  publicationNotice,
} from '../src/lib/review-jobs.ts'

const require = createRequire(import.meta.url)
const typescript = require('typescript')

const jobs = [
  { id: 'a', pr_number: 7, analysis_status: 'queued', publication_status: 'not_requested' },
  { id: 'b', pr_number: 8, analysis_status: 'analyzed', publication_status: 'preview_ready' },
  { id: 'c', pr_number: 9, analysis_status: 'analyzed', publication_status: 'published' },
  { id: 'd', pr_number: 10, analysis_status: 'partial', publication_status: 'partially_published' },
  { id: 'e', pr_number: 11, analysis_status: 'failed', publication_status: 'failed' },
]

test('PR filter submits valid numbers and safely rejects malformed input', () => {
  assert.deepEqual(parsePullRequestFilter(' 42 '), { value: '42', error: null })
  assert.deepEqual(parsePullRequestFilter(''), { value: '', error: null })
  for (const input of ['0', '-1', '1.5', '1e3', '99999999999', 'abc']) {
    assert.ok(parsePullRequestFilter(input).error)
  }
  assert.deepEqual(
    filterJobsByPullRequest(jobs, '9').map((job) => job.id),
    ['c'],
  )
  assert.deepEqual(filterJobsByPullRequest(jobs, ''), jobs)
  assert.deepEqual(filterJobsByPullRequest(jobs, 'invalid'), [])
})

test('job badges reflect analysis and publication outcomes', () => {
  assert.deepEqual(jobs.map(jobStatus), ['QUEUED', 'ANALYZED', 'PUBLISHED', 'PARTIAL', 'FAILED'])
})

test('findings group by risk and retain category names with null-safe input', () => {
  const finding = (id, severity, focus) => ({ id, severity, focus })
  const grouped = groupFindings([
    finding('s', 'CRITICAL', 'security'),
    finding('p', 'HIGH', 'performance'),
    finding('w', 'MEDIUM', 'quality'),
    finding('i', 'LOW', 'security'),
  ])
  assert.deepEqual(
    grouped.critical.map((item) => item.id),
    ['s', 'p'],
  )
  assert.deepEqual(
    grouped.warning.map((item) => item.id),
    ['w'],
  )
  assert.deepEqual(
    grouped.info.map((item) => item.id),
    ['i'],
  )
  assert.deepEqual(groupFindings(null), { critical: [], warning: [], info: [] })
})

test('detail metrics tolerate absent fields and show measured latency and coverage', () => {
  const job = {
    created_at: '2026-09-23T12:00:00.000Z',
    processing_started_at: '2026-09-23T12:00:01.000Z',
    completed_at: '2026-09-23T12:00:11.250Z',
  }
  assert.equal(processingLatency(job), '10.3 秒')
  assert.equal(processingLatency({}), '未提供')
  assert.equal(formatCoverage(null), '暂无覆盖率数据')
  assert.equal(
    formatCoverage({
      changed_lines_reviewed: 12,
      changed_lines_total: 20,
      files_reviewed: 2,
      files_total: 3,
    }),
    '12 / 20 行 · 2 / 3 个文件',
  )
})

test('publication status distinguishes partial delivery and explicit 422 fallback', () => {
  assert.match(publicationNotice({ publication_status: 'partially_published' }), /部分发布/)
  assert.match(
    publicationNotice({
      publication_status: 'partially_published',
      publication_fallback_reason: 'diff_position_mismatch',
    }),
    /422/,
  )
  assert.match(publicationNotice({ publication_status: 'preview_ready' }), /尚未发布/)
})

function apiClient(fetch, token = 'fixture-token') {
  const source = readFileSync(new URL('../src/lib/review-jobs-api.ts', import.meta.url), 'utf8')
  const output = typescript.transpileModule(source, {
    compilerOptions: {
      module: typescript.ModuleKind.CommonJS,
      target: typescript.ScriptTarget.ES2022,
    },
  }).outputText
  const sandbox = {
    exports: {},
    URLSearchParams,
    fetch,
    require(name) {
      if (name === '@/lib/api') return { API_URL: 'http://local.fixture' }
      if (name === '@/lib/auth') return { getAccessToken: () => token }
      throw new Error(`Unexpected dependency ${name}`)
    },
  }
  vm.runInNewContext(output, sandbox)
  return sandbox.exports
}

test('job API builds authenticated read-only list and detail requests; failures are safe', async () => {
  const requests = []
  const api = apiClient(async (url, init) => {
    requests.push({ url, init })
    return Response.json({ jobs: [], total_count: 0, page: 1, per_page: 20 })
  })
  await api.reviewJobsApi.list('301', '401', 1, 42, 'PARTIAL')
  await api.reviewJobsApi.detail('550e8400-e29b-41d4-a716-446655440000')
  assert.match(
    requests[0].url,
    /\/api\/v1\/review\/jobs\?installation_id=301&repo_id=401&page=1&per_page=20&pr_number=42&status=PARTIAL$/,
  )
  assert.match(requests[1].url, /\/api\/v1\/review\/jobs\/550e8400-e29b-41d4-a716-446655440000$/)
  for (const request of requests) {
    assert.equal(request.init.method, undefined)
    assert.equal(request.init.cache, 'no-store')
    assert.equal(request.init.headers.Authorization, 'Bearer fixture-token')
  }
  const missing = apiClient(async () => new Response(null, { status: 404 }))
  await assert.rejects(missing.reviewJobsApi.list('301', '401', 1), { status: 404 })
  assert.throws(() => api.reviewJobsApi.detail('not-a-uuid'))
})

test('detail component renders metrics, grouped findings, diff references and fallback badge', () => {
  const React = require('react')
  const ReactDOMServer = require('react-dom/server')
  const source = readFileSync(
    new URL('../src/components/review/review-job-detail.tsx', import.meta.url),
    'utf8',
  )
  const output = typescript.transpileModule(source, {
    compilerOptions: {
      module: typescript.ModuleKind.CommonJS,
      target: typescript.ScriptTarget.ES2022,
      jsx: typescript.JsxEmit.ReactJSX,
    },
  }).outputText
  const job = {
    id: '550e8400-e29b-41d4-a716-446655440000',
    pr_number: 42,
    head_sha: 'a'.repeat(40),
    analysis_status: 'partial',
    publication_status: 'partially_published',
    processing_started_at: '2026-09-23T12:00:00.000Z',
    completed_at: '2026-09-23T12:00:02.000Z',
    summary: 'Found one unsafe path.',
    coverage: {
      changed_lines_reviewed: 12,
      changed_lines_total: 20,
      files_reviewed: 2,
      files_total: 3,
      truncated: true,
      truncation_reason: 'Token budget reached',
      gaps: ['2 lines skipped by budget'],
    },
    usage: { input_tokens: 1000, output_tokens: 120, cost_usd: '0.004200' },
    publication: {
      status: 'partially_published',
      github_review_ids: ['9001'],
    },
    publication_fallback_reason: 'diff_position_mismatch',
    findings: [
      {
        id: 'finding-1',
        severity: 'CRITICAL',
        focus: 'security',
        location: { path: 'src/app.py', line: 12, side: 'RIGHT' },
        verified_diff: {
          path: 'src/app.py',
          line: 12,
          side: 'RIGHT',
          position: 8,
          comment_context: '@@ -11 +12 @@\\n+unsafe(value)',
        },
        description: 'Validate untrusted input.',
        suggestion: 'validate(value)',
        evidence: 'The value reaches a parser.',
      },
      {
        id: 'finding-2',
        severity: 'LOW',
        focus: 'quality',
        location: { path: 'src/other.py', line: 4, side: 'LEFT' },
        verified_diff: null,
        description: 'No verified line mapping was retained.',
      },
    ],
  }
  let stateIndex = 0
  const fakeReact = {
    useEffect() {},
    useState() {
      const values = [job, null, 0]
      return [values[stateIndex++], () => {}]
    },
  }
  const jsxRuntime = require('react/jsx-runtime')
  const passthrough =
    (tag) =>
    ({ children, ...props }) =>
      React.createElement(tag, props, children)
  const sandbox = {
    exports: {},
    require(name) {
      if (name === 'react') return fakeReact
      if (name === 'react/jsx-runtime') return jsxRuntime
      if (name === '@/components/ui/badge') return { Badge: passthrough('span') }
      if (name === '@/components/ui/button') return { Button: passthrough('button') }
      if (name === '@/components/ui/error-notice') return { ErrorNotice: () => null }
      if (name === '@/components/ui/skeleton') return { Skeleton: passthrough('div') }
      if (name === '@/lib/review-jobs-api') return { reviewJobsApi: {} }
      if (name === '@/lib/review-jobs')
        return {
          categoryLabel: (focus) => focus.toUpperCase(),
          groupFindings,
          jobStatus,
          processingLatency,
          publicationNotice,
          formatCoverage,
        }
      throw new Error(`Unexpected dependency ${name}`)
    },
  }
  vm.runInNewContext(output, sandbox)
  const html = ReactDOMServer.renderToStaticMarkup(
    React.createElement(sandbox.exports.ReviewJobDetail, { jobId: job.id }),
  )
  for (const expected of [
    '12 / 20 行',
    '1,000 输入 / 120 输出',
    'US$ 0.004200',
    'CRITICAL',
    'SECURITY',
    'src/app.py:12 · RIGHT · 已验证 diff position 8',
    'src/other.py:4 · LEFT · diff 映射未确认',
    '422',
    'Token budget reached',
  ]) {
    assert.ok(html.includes(expected), `detail markup includes ${expected}`)
  }
})
