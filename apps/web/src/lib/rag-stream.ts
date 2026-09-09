import type { CitationItem, StreamCallbacks } from './rag'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isCitation(value: unknown): value is CitationItem {
  return (
    isRecord(value) &&
    ['document_id', 'chunk_id', 'filename', 'content'].every(
      (key) => typeof value[key] === 'string',
    ) &&
    typeof value.chunk_index === 'number' &&
    Number.isInteger(value.chunk_index) &&
    typeof value.similarity === 'number' &&
    Number.isFinite(value.similarity) &&
    isRecord(value.metadata)
  )
}

/** Retain UTF-8 and line fragments between reads; a truncated stream is an error. */
export async function readRAGStream(body: ReadableStream<Uint8Array>, callbacks: StreamCallbacks) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  const consume = (line: string) => {
    if (!line.startsWith('data:')) return
    const payload = line.slice(5).trim()
    if (payload === '[DONE]') {
      completed = true
      return
    }
    let chunk: unknown
    try {
      chunk = JSON.parse(payload)
    } catch {
      throw new Error('回答数据格式无效，请重试')
    }
    if (!isRecord(chunk)) throw new Error('回答数据格式无效，请重试')
    if (chunk.finish_reason === 'error') throw new Error('回答生成中断，请重试')
    if (chunk.citation != null) {
      if (!isCitation(chunk.citation)) throw new Error('引用数据格式无效，请重试')
      callbacks.onCitation?.(chunk.citation)
    }
    if (chunk.delta != null) {
      if (typeof chunk.delta !== 'string') throw new Error('回答数据格式无效，请重试')
      callbacks.onDelta?.(chunk.delta)
    }
  }
  try {
    while (!completed) {
      const { done, value } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        consume(line)
        if (completed) break
      }
      if (done) {
        if (!completed && buffer.trim()) consume(buffer)
        if (!completed) throw new Error('连接提前结束，回答可能不完整，请重试')
        break
      }
    }
    callbacks.onDone?.()
  } finally {
    try {
      await reader.cancel()
    } finally {
      reader.releaseLock()
    }
  }
}
