import assert from 'node:assert/strict'
import { webcrypto } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import vm from 'node:vm'

const ts = createRequire(import.meta.url)('typescript')
const transpile = (source) =>
  ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText

function client(fetch) {
  let timeout
  let cleared = false
  const sandbox = {
    exports: {},
    crypto: { getRandomValues: (bytes) => webcrypto.getRandomValues(bytes) },
    AbortController,
    setTimeout: (fn) => {
      timeout = fn
      return 1
    },
    clearTimeout: () => {
      cleared = true
    },
    fetch: (url, init) => fetch(url, init, () => timeout()),
    require: (name) => {
      if (name === '@/lib/api') return { API_URL: 'http://example.test' }
      if (name === '@/lib/auth') return { getAccessToken: () => 'fixture' }
      throw new Error(`Unexpected dependency: ${name}`)
    },
  }
  vm.runInNewContext(
    transpile(readFileSync(new URL('../src/lib/agent-runs.ts', import.meta.url), 'utf8')),
    sandbox,
  )
  return { ...sandbox.exports, cleared: () => cleared }
}

test('HTTP crypto without randomUUID can create and rerun with random request keys', async () => {
  const calls = []
  const api = client(async (url, init) => {
    calls.push({ url, init })
    return Response.json({ id: 'run' })
  })
  const key = api.createRunKey()
  assert.match(key, /^[a-f0-9]{32}$/)
  assert.notEqual(key, api.createRunKey())
  await api.agentRunsApi.create('flow', { text: 'test', workflow_version: 1 }, key)
  await api.agentRunsApi.rerun('run', { mode: 'snapshot' })
  assert.equal(calls[0].init.headers['Idempotency-Key'], key)
  assert.match(calls[1].init.headers['Idempotency-Key'], /^[a-f0-9]{32}$/)
  assert.equal(api.cleared(), true)
})

test('stalled request aborts, reports uncertainty and reuses caller key on retry', async () => {
  const keys = []
  const api = client((_url, init, expire) => {
    keys.push(init.headers['Idempotency-Key'])
    if (keys.length > 1) return Promise.resolve(Response.json({ id: 'run' }))
    return new Promise((_resolve, reject) => {
      init.signal.addEventListener('abort', () => reject(new Error('private transport details')))
      expire()
    })
  })
  const key = api.createRunKey()
  await assert.rejects(api.agentRunsApi.create('flow', {}, key), (error) => {
    assert.equal(error.status, 0)
    assert.match(error.message, /暂不确定/)
    assert.doesNotMatch(error.message, /private/)
    return true
  })
  assert.equal(api.cleared(), true)
  await api.agentRunsApi.create('flow', {}, key)
  assert.deepEqual(keys, [key, key])
})

test('HTTP status errors are retained and request timer is cleared', async () => {
  const api = client(async () => new Response('', { status: 401 }))
  await assert.rejects(api.agentRunsApi.list(), (error) => error.status === 401)
  assert.equal(api.cleared(), true)
})

test('key generation failure restores the create button without sending a request', async () => {
  const source = readFileSync(
    new URL('../src/components/workflows/workflow-editor.tsx', import.meta.url),
    'utf8',
  )
  const file = ts.createSourceFile(
    'editor.tsx',
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  )
  let handler
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.text === 'startRun')
      handler = node.getText(file)
    ts.forEachChild(node, visit)
  }
  visit(file)
  assert.ok(handler)
  const busy = []
  const errors = []
  const sandbox = {
    exports: {},
    current: { id: 'flow', version: 1, status: 'ready' },
    dirty: false,
    runInput: 'test',
    runKey: '',
    setRunBusy: (value) => busy.push(value),
    setRunError: (value) => errors.push(value),
    setRunKey: () => {},
    createRunKey: () => {
      throw new Error('unavailable crypto')
    },
    RunRequestError: client(() => {}).RunRequestError,
    agentRunsApi: { create: () => assert.fail('request must not be sent') },
  }
  vm.runInNewContext(transpile(`${handler}\nexports.startRun = startRun`), sandbox)
  await sandbox.exports.startRun({ preventDefault() {} })
  assert.deepEqual(busy, [true, false])
  assert.ok(errors.at(-1))
})
