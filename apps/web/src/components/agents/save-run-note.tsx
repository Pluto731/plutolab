'use client'

import Link from 'next/link'
import { useRef, useState } from 'react'
import { createNote } from '@/lib/notes'

/** Explicit user action only: the Agent never receives note-write permissions. */
export function SaveRunNote({ title, output }: { title: string; output: string }) {
  const inFlight = useRef(false)
  const [busy, setBusy] = useState(false)
  const [savedId, setSavedId] = useState('')
  const [error, setError] = useState('')

  async function save() {
    if (inFlight.current || savedId) return
    inFlight.current = true
    setBusy(true)
    setError('')
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 20_000)
    try {
      const note = await createNote(
        { title: title.slice(0, 200), content: output },
        controller.signal,
      )
      setSavedId(note.id)
    } catch {
      setError('未能确认保存结果，请先检查笔记列表，避免重复创建。')
    } finally {
      clearTimeout(timeout)
      inFlight.current = false
      setBusy(false)
    }
  }

  return (
    <div className="mt-3 space-y-2 text-xs">
      {savedId ? (
        <Link
          href={`/notes/${encodeURIComponent(savedId)}`}
          className="font-medium text-primary underline"
        >
          已保存，打开笔记
        </Link>
      ) : (
        <button
          type="button"
          onClick={() => void save()}
          disabled={busy}
          className="rounded-md border bg-background px-3 py-1.5 font-medium disabled:opacity-50"
        >
          {busy ? '正在保存…' : '保存为笔记'}
        </button>
      )}
      {error && (
        <p role="alert">
          {error}{' '}
          <Link href="/notes" className="underline">
            查看笔记列表
          </Link>
        </p>
      )}
    </div>
  )
}
