const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ts = require('typescript')

// Execute the real client with only authentication and transport replaced.
// TypeScript is already a project dependency; no test framework is required.
const source = fs.readFileSync(path.join(__dirname, '../src/lib/rag.ts'), 'utf8')
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText

function client(fetch) {
  const sandbox = {
    exports: {}, fetch, TextDecoder, DOMException, Error,
    require(id) {
      if (id === '@/lib/api') return { API_URL: 'https://fixture.invalid' }
      if (id === '@/lib/auth') return { getAccessToken: () => null }
      throw new Error(`Unexpected dependency: ${id}`)
    },
  }
  vm.runInNewContext(compiled, sandbox)
  return sandbox.exports
}

function response(parts) {
  return new Response(new ReadableStream({
    start(controller) {
      for (const part of parts) controller.enqueue(part)
      controller.close()
    },
  }))
}

function callbacks() {
  const state = { done: 0, errors: [], text: '', citations: [] }
  return { state, handlers: {
    onDone: () => state.done++,
    onError: (error) => state.errors.push(error.message),
    onDelta: (delta) => { state.text += delta },
    onCitation: (citation) => state.citations.push(citation),
  } }
}

test('fragmented UTF-8, CRLF, citations, and DONE complete once', async () => {
  const citation = { chunk_id: 'fixture', content: '中文' }
  const bytes = new TextEncoder().encode(
    `data: ${JSON.stringify({ citation })}\r\n\r\n` +
    'data: {"delta":"中文🙂"}\r\n\r\n' +
    'data: {"finish_reason":"stop"}\r\n\r\ndata: [DONE]',
  )
  const api = client(async () => response(Array.from(bytes, (byte) => Uint8Array.of(byte))))
  const { state, handlers } = callbacks()
  await api.streamRAGMessage('fixture', { content: 'question' }, handlers)
  assert.equal(state.done, 1)
  assert.deepEqual(state.errors, [])
  assert.equal(state.text, '中文🙂')
  assert.equal(state.citations[0].chunk_id, 'fixture')
})

for (const [name, text] of [
  ['unexpected EOF', 'data: {"delta":"partial"}\n\n'],
  ['empty stream', ''],
  ['stop without DONE', 'data: {"finish_reason":"stop"}\n\n'],
  ['malformed event', 'data: {bad-json}\n\ndata: [DONE]\n\n'],
  ['generation failure', 'data: {"error":{"code":"generation_failed","message":"Please retry"}}\n\n'],
  ['persistence failure followed by DONE', 'data: {"error":{"code":"persistence_failed","message":"Not saved"}}\n\ndata: [DONE]\n\n'],
]) {
  test(`${name} reports one error and never completes`, async () => {
    const api = client(async () => new Response(text))
    const { state, handlers } = callbacks()
    await assert.rejects(api.streamRAGMessage('fixture', { content: 'question' }, handlers))
    assert.equal(state.done, 0)
    assert.equal(state.errors.length, 1)
  })
}

test('network failure reports one error', async () => {
  const api = client(async () => { throw new Error('Offline') })
  const { state, handlers } = callbacks()
  await assert.rejects(api.streamRAGMessage('fixture', { content: 'question' }, handlers), /Offline/)
  assert.deepEqual(state.errors, ['Offline'])
  assert.equal(state.done, 0)
})

test('HTTP failure reports one error', async () => {
  const api = client(async () => new Response('{"detail":"Forbidden"}', { status: 403 }))
  const { state, handlers } = callbacks()
  await assert.rejects(api.streamRAGMessage('fixture', { content: 'question' }, handlers), /Forbidden/)
  assert.deepEqual(state.errors, ['Forbidden'])
  assert.equal(state.done, 0)
})

test('explicit cancellation is neither success nor failure', async () => {
  const controller = new AbortController()
  controller.abort()
  const api = client(async () => { throw new DOMException('Cancelled', 'AbortError') })
  const { state, handlers } = callbacks()
  await api.streamRAGMessage('fixture', { content: 'question' }, handlers, controller.signal)
  assert.equal(state.done, 0)
  assert.deepEqual(state.errors, [])
})
