import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import vm from 'node:vm'

const ts = createRequire(import.meta.url)('typescript')
const source = readFileSync(
  new URL('../src/components/agents/save-run-note.tsx', import.meta.url),
  'utf8',
)
const file = ts.createSourceFile(
  'component.tsx',
  source,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
)
let handler
function visit(node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === 'save') handler = node.getText(file)
  ts.forEachChild(node, visit)
}
visit(file)
assert.ok(handler)

function harness(createNote) {
  const busy = []
  const errors = []
  let expire
  let cleared = false
  const sandbox = {
    exports: {},
    inFlight: { current: false },
    savedId: '',
    title: 't'.repeat(250),
    output: '# Markdown\nbody',
    createNote,
    AbortController,
    setBusy: (value) => busy.push(value),
    setError: (value) => errors.push(value),
    setSavedId: (value) => {
      sandbox.savedId = value
    },
    setTimeout: (fn) => {
      expire = fn
      return 1
    },
    clearTimeout: () => {
      cleared = true
    },
  }
  vm.runInNewContext(
    ts.transpileModule(`${handler}\nexports.save = save`, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText,
    sandbox,
  )
  return {
    save: sandbox.exports.save,
    busy,
    errors,
    expire: () => expire(),
    cleared: () => cleared,
    saved: () => sandbox.savedId,
  }
}

test('saving is explicit, preserves Markdown, and blocks concurrent or completed duplicate clicks', async () => {
  let finish
  let calls = 0
  const h = harness((body, signal) => {
    calls++
    assert.equal(body.title.length, 200)
    assert.equal(body.content, '# Markdown\nbody')
    assert.equal(signal.aborted, false)
    return new Promise((resolve) => {
      finish = resolve
    })
  })
  assert.equal(calls, 0)
  const pending = h.save()
  await h.save()
  assert.equal(calls, 1)
  finish({ id: 'note-id' })
  await pending
  await h.save()
  assert.equal(calls, 1)
  assert.equal(h.saved(), 'note-id')
  assert.deepEqual(h.busy, [true, false])
  assert.equal(h.cleared(), true)
})

test('timeout releases busy state and warns about uncertain writes without retrying automatically', async () => {
  let calls = 0
  const h = harness((_body, signal) => {
    calls++
    return new Promise((_resolve, reject) =>
      signal.addEventListener('abort', () => reject(new Error('private response'))),
    )
  })
  const pending = h.save()
  h.expire()
  await pending
  assert.equal(calls, 1)
  assert.deepEqual(h.busy, [true, false])
  assert.match(h.errors.at(-1), /检查笔记列表/)
  assert.doesNotMatch(h.errors.at(-1), /private response/)
  assert.equal(h.saved(), '')
  assert.equal(h.cleared(), true)
})

test('note client sends Markdown with authentication and forwards cancellation to fetch', async () => {
  const controller = new AbortController()
  let sent
  const sandbox = {
    exports: {},
    require: (name) => {
      if (name === '@/lib/api') return { API_URL: 'http://example.test' }
      if (name === '@/lib/auth') return { getAccessToken: () => 'fixture' }
      throw new Error(`Unexpected dependency: ${name}`)
    },
    fetch: async (url, init) => {
      sent = { url, init }
      return Response.json({ id: 'saved-note' })
    },
  }
  const code = readFileSync(new URL('../src/lib/notes.ts', import.meta.url), 'utf8')
  vm.runInNewContext(
    ts.transpileModule(code, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText,
    sandbox,
  )
  const note = await sandbox.exports.createNote(
    { title: 'Report', content: '# Source\nbody' },
    controller.signal,
  )
  assert.equal(note.id, 'saved-note')
  assert.equal(sent.url, 'http://example.test/api/v1/notes')
  assert.equal(sent.init.headers.Authorization, 'Bearer fixture')
  assert.equal(sent.init.signal, controller.signal)
  assert.equal(JSON.parse(sent.init.body).content, '# Source\nbody')
})
