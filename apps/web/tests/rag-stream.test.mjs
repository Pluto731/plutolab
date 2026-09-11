import assert from 'node:assert/strict'
import test from 'node:test'
import { readRAGStream } from '../src/lib/rag-stream.ts'

function body(text, split = false) {
  const bytes = new TextEncoder().encode(text)
  return new ReadableStream({
    start(controller) {
      if (split) for (const byte of bytes) controller.enqueue(Uint8Array.of(byte))
      else controller.enqueue(bytes)
      controller.close()
    },
  })
}

test('preserves split UTF-8, CRLF and final terminator without newline', async () => {
  let answer = ''
  let done = 0
  await readRAGStream(body('data: {"delta":"你好🌙"}\r\n\r\ndata: [DONE]', true), {
    onDelta: (delta) => {
      answer += delta
    },
    onDone: () => {
      done++
    },
  })
  assert.equal(answer, '你好🌙')
  assert.equal(done, 1)
})

for (const [name, payload] of [
  ['truncated', 'data: {"delta":"partial"}\n\n'],
  ['malformed JSON', 'data: {invalid}\n\ndata: [DONE]\n'],
  ['invalid citation', 'data: {"citation":{"content":"x"}}\n\ndata: [DONE]\n'],
  ['provider failure', 'data: {"finish_reason":"error"}\n\ndata: [DONE]\n'],
  ['invalid delta', 'data: {"delta":42}\n\ndata: [DONE]\n'],
]) {
  test(`${name} never signals successful completion`, async () => {
    let done = false
    await assert.rejects(
      readRAGStream(body(payload), {
        onDone: () => {
          done = true
        },
      }),
    )
    assert.equal(done, false)
  })
}

test('delivers valid citation and releases the body reader', async () => {
  const citation = {
    document_id: 'doc',
    chunk_id: 'chunk',
    filename: 'note.md',
    content: '原文',
    chunk_index: 0,
    similarity: 0.4,
    metadata: { page: 1 },
  }
  const stream = body(`data: ${JSON.stringify({ citation })}\n\ndata: [DONE]\n`)
  let received
  await readRAGStream(stream, {
    onCitation: (value) => {
      received = value
    },
  })
  assert.deepEqual(received, citation)
  assert.equal(stream.locked, false)
})
