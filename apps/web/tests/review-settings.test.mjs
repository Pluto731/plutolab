import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import vm from 'node:vm'
import { ruleDraft, validateRules, validRepositorySearch } from '../src/lib/review-rules.ts'
const require = createRequire(import.meta.url)
const ts = require('typescript')
const compiled = ts.transpileModule(
  readFileSync(new URL('../src/lib/review.ts', import.meta.url), 'utf8'),
  {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  },
).outputText
function client(fetch, token = 'fixture-site-token') {
  const sandbox = {
    exports: {},
    fetch,
    URL,
    URLSearchParams,
    Error,
    require(name) {
      if (name === '@/lib/api') return { API_URL: 'http://local.fixture' }
      if (name === '@/lib/auth') return { getAccessToken: () => token }
      throw new Error(`Unexpected dependency ${name}`)
    },
  }
  vm.runInNewContext(compiled, sandbox)
  return sandbox.exports
}
const rules = {
  installation_id: '301',
  repo_id: '9',
  repo_name: 'owner/repo',
  enabled: false,
  min_pr_lines: 1,
  max_pr_lines: null,
  skip_paths: [],
  focus_areas: ['security'],
  rules_version: 3,
}
const draft = () => ruleDraft(rules)

test('full replacement uses the loaded version and preserves nullable cap', () => {
  assert.deepEqual(validateRules(draft(), 3).value, {
    enabled: false,
    min_pr_lines: 1,
    max_pr_lines: null,
    skip_paths: [],
    focus_areas: ['security'],
    expected_rules_version: 3,
  })
  assert.deepEqual(validateRules({ ...draft(), max: '1' }, 3).value.max_pr_lines, 1)
})
for (const value of ['0', '-1', '1.2', '1e3', '2147483648', 'NaN', '', ' 1']) {
  test(`rejects invalid minimum ${JSON.stringify(value)}`, () =>
    assert.ok(validateRules({ ...draft(), min: value }, 3).error))
}
for (const value of ['0', '-1', '2147483648', '2.2']) {
  test(`rejects invalid maximum ${value}`, () =>
    assert.ok(validateRules({ ...draft(), max: value }, 3).error))
}
test('rejects max below min', () =>
  assert.ok(validateRules({ ...draft(), min: '3', max: '2' }, 3).error))
for (const paths of [
  '../secret',
  '/root',
  'src//a',
  'src/[a]',
  '.*(test)$',
  'src/**oops',
  'src/./a',
  ' a',
  'a\n',
  'a\na',
  'a\tb',
  'a\u00a0b',
  'a'.repeat(257),
]) {
  test(`rejects malformed path ${JSON.stringify(paths).slice(0, 32)}`, () =>
    assert.ok(validateRules({ ...draft(), paths }, 3).error))
}
test('bounded relative globs and unicode are accepted', () => {
  assert.deepEqual(
    validateRules({ ...draft(), paths: 'src/**\n*.lock\n文档/?.md' }, 3).value.skip_paths,
    ['src/**', '*.lock', '文档/?.md'],
  )
})
test('path count is bounded', () =>
  assert.ok(
    validateRules(
      { ...draft(), paths: Array.from({ length: 101 }, (_, i) => `a${i}`).join('\n') },
      3,
    ).error,
  ))
test('focus must be nonempty, unique, and known', () => {
  for (const focus of [[], ['security', 'security'], ['unknown']])
    assert.ok(validateRules({ ...draft(), focus }, 3).error)
})
test('repository keyword validation matches API limits', () => {
  assert.equal(validRepositorySearch('owner/repo-1'), true)
  for (const q of ['%', '*', 'a'.repeat(101), '中文']) assert.equal(validRepositorySearch(q), false)
})
test('authenticated requests use fixed routes, encoded search, no-store and loaded version', async () => {
  const requests = []
  const { reviewApi } = client(async (url, init) => {
    requests.push({ url, init })
    return Response.json(rules)
  })
  await reviewApi.installations()
  await reviewApi.repositories('301', 'owner/repo x', 2)
  await reviewApi.rules('301', '9')
  await reviewApi.save('301', '9', validateRules(draft(), 3).value)
  assert.equal(requests[0].url, 'http://local.fixture/api/v1/review/installations')
  const search = new URL(requests[1].url).searchParams
  assert.equal(search.get('q'), 'owner/repo x')
  assert.equal(search.get('page'), '2')
  assert.equal(requests[3].init.method, 'PUT')
  assert.equal(JSON.parse(requests[3].init.body).expected_rules_version, 3)
  for (const { init } of requests) {
    assert.equal(init.headers.Authorization, 'Bearer fixture-site-token')
    assert.equal(init.cache, 'no-store')
    assert.equal(init.redirect, 'error')
  }
})
test('bind sends claims as authenticated JSON; revoke uses DELETE', async () => {
  const requests = []
  const { reviewApi } = client(async (url, init) => {
    requests.push({ url, init })
    return Response.json({})
  })
  await reviewApi.start()
  await reviewApi.bind('301', 's'.repeat(43))
  await reviewApi.revoke('301')
  assert.equal(requests[0].init.method, 'POST')
  assert.deepEqual(JSON.parse(requests[1].init.body), {
    installation_id: '301',
    state: 's'.repeat(43),
  })
  assert.equal(requests[2].init.method, 'DELETE')
  assert.equal(
    requests.some((r) => r.url.includes('state=')),
    false,
  )
})
test('missing auth and invalid IDs never reach transport', async () => {
  let calls = 0
  const mock = async () => {
    calls++
    return Response.json({})
  }
  await assert.rejects(client(mock, null).reviewApi.installations(), { status: 401 })
  assert.throws(() => client(mock).reviewApi.rules('../bad', '9'))
  assert.equal(calls, 0)
})
for (const status of [401, 403, 404, 409, 422, 429, 500]) {
  test(`HTTP ${status} is actionable without leaking raw secrets`, async () => {
    const { reviewApi } = client(async () => new Response('secret-state-and-token', { status }))
    await assert.rejects(
      reviewApi.installations(),
      (e) => e.status === status && !e.message.includes('secret'),
    )
  })
}
test('transport errors redact URL/state and retain abort behavior', async () => {
  const { reviewApi } = client(async () => {
    throw new Error('secret-url')
  })
  await assert.rejects(
    reviewApi.installations(),
    (e) => e.status === 0 && !e.message.includes('secret'),
  )
  const abort = new AbortController()
  abort.abort()
  await assert.rejects(reviewApi.installations(abort.signal), /secret-url/)
})
test('navigation accepts only the fixed GitHub App installation URL', () => {
  const { installationUrl } = client()
  const good = `https://github.com/apps/plutolab/installations/new?state=${'a'.repeat(43)}`
  assert.equal(installationUrl(good), good)
  for (const bad of [
    good.replace('github.com', 'evil.invalid'),
    good.replace('https:', 'http:'),
    good + '&next=https://evil.invalid',
    good + '#secret',
    good.replace('github.com', 'secret@github.com'),
    good + '&state=' + 'b'.repeat(43),
  ])
    assert.throws(() => installationUrl(bad))
})
test('callback validates unique claims and ignores query user identity', () => {
  const { installationCallback } = client()
  assert.equal(installationCallback(''), null)
  const claim = installationCallback(
    `?installation_id=301&state=${'a'.repeat(43)}&user_id=attacker`,
  )
  assert.equal(claim.installationId, '301')
  assert.equal(claim.user_id, undefined)
  for (const bad of [
    '?installation_id=301',
    '?state=bad',
    `?installation_id=301&state=${'a'.repeat(43)}&installation_id=302`,
  ])
    assert.throws(() => installationCallback(bad))
})
