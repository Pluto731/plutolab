'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { AgentRequestError, agentsApi, type AgentCreate, type AgentPublic } from '@/lib/agents'

const empty = (): AgentCreate => ({
  name: '',
  description: '',
  role_prompt: '',
  provider: 'openai',
  model: 'gpt-4o-mini',
  tools: [],
})
export function AgentEditor() {
  const [items, setItems] = useState<AgentPublic[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [current, setCurrent] = useState<AgentPublic | null>(null)
  const [draft, setDraft] = useState<AgentCreate>(empty)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [conflict, setConflict] = useState(false)
  const [message, setMessage] = useState('')
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    let live = true
    setLoading(true)
    setError('')
    agentsApi
      .list(offset)
      .then((page) => {
        if (live) {
          setItems(page.items)
          setTotal(page.total)
        }
      })
      .catch((err) => {
        if (live) {
          setItems([])
          setError(err instanceof AgentRequestError ? err.message : '读取失败，请重试。')
        }
      })
      .finally(() => {
        if (live) setLoading(false)
      })
    return () => {
      live = false
    }
  }, [offset, revision])
  function select(agent: AgentPublic | null) {
    setCurrent(agent)
    setDraft(
      agent
        ? {
            name: agent.name,
            description: agent.description,
            role_prompt: agent.role_prompt,
            provider: agent.provider,
            model: agent.model,
            tools: [...agent.tools],
          }
        : empty(),
    )
    setConflict(false)
    setError('')
    setMessage('')
  }
  async function mutate(archive: boolean) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      if (archive && current) {
        await agentsApi.archive(current)
        select(null)
      } else {
        const saved = await agentsApi.save(draft, current)
        select(saved)
      }
      setMessage(archive ? '已归档。' : '已保存。')
      setRevision((value) => value + 1)
    } catch (err) {
      setError(err instanceof AgentRequestError ? err.message : '操作失败，请重试。')
      if (err instanceof AgentRequestError && err.status === 409) setConflict(true)
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-12">
      <header>
        <Link href="/agents/workflows" className="text-sm underline">
          编排 Workflow →
        </Link>
        <Link href="/agents/runs" className="ml-4 text-sm underline">
          查看运行历史 →
        </Link>
        <p className="text-sm text-muted-foreground">Agent 工作台</p>
        <h1 className="text-3xl font-semibold">定义你的协作成员</h1>
        <p className="mt-2 text-muted-foreground">配置角色、模型与只读工具，预览角色指令并保存。</p>
      </header>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      {message && <p role="status">{message}</p>}
      <div className="grid gap-6 md:grid-cols-[260px_1fr]">
        <aside className="space-y-3 rounded-xl border p-4">
          <button disabled={busy} onClick={() => select(null)} className="rounded border px-3 py-2">
            新建 Agent
          </button>
          <button
            disabled={busy || loading}
            onClick={() => setRevision((v) => v + 1)}
            className="ml-2 underline"
          >
            刷新列表
          </button>
          {loading ? (
            <p role="status">加载中…</p>
          ) : items.length === 0 ? (
            <p>暂无 Agent。</p>
          ) : (
            <ul className="space-y-2">
              {items.map((agent) => (
                <li key={agent.id}>
                  <button
                    disabled={busy}
                    onClick={() => select(agent)}
                    className={`w-full rounded border p-3 text-left ${current?.id === agent.id ? 'bg-muted' : ''}`}
                  >
                    <span className="block font-medium">{agent.name}</span>
                    <span className="text-xs text-muted-foreground">版本 {agent.version}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex justify-between">
            <button
              disabled={busy || loading || offset === 0}
              onClick={() => setOffset((v) => v - 20)}
            >
              上一页
            </button>
            <button
              disabled={busy || loading || offset + 20 >= total || offset >= 10000}
              onClick={() => setOffset((v) => v + 20)}
            >
              下一页
            </button>
          </div>
        </aside>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void mutate(false)
          }}
          className="space-y-4 rounded-xl border p-6"
        >
          <h2 className="text-xl font-medium">{current ? '编辑 Agent' : '新建 Agent'}</h2>
          <fieldset disabled={busy || conflict} className="space-y-4 disabled:opacity-60">
            <label className="block">
              名称
              <input
                required
                maxLength={100}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                className="mt-1 block w-full rounded border bg-background p-2"
              />
            </label>
            <label className="block">
              描述
              <textarea
                maxLength={2000}
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                className="mt-1 block w-full rounded border bg-background p-2"
              />
            </label>
            <label className="block">
              模型
              <select
                value={draft.model}
                onChange={() => {}}
                className="ml-3 rounded border bg-background p-2"
              >
                <option value="gpt-4o-mini">OpenAI · gpt-4o-mini</option>
              </select>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={draft.tools?.includes('search_notes') ?? false}
                onChange={(e) =>
                  setDraft({ ...draft, tools: e.target.checked ? ['search_notes'] : [] })
                }
              />
              搜索本人笔记（只读）
            </label>
            <label className="block">
              角色指令
              <textarea
                required
                rows={7}
                maxLength={16000}
                value={draft.role_prompt}
                onChange={(e) => setDraft({ ...draft, role_prompt: e.target.value })}
                className="mt-1 block w-full rounded border bg-background p-2"
              />
            </label>
            <button
              disabled={!draft.name.trim() || !draft.role_prompt.trim()}
              className="rounded bg-primary px-4 py-2 text-primary-foreground"
            >
              {busy ? '处理中…' : '保存配置'}
            </button>
            {current && (
              <button
                type="button"
                className="ml-4 text-destructive"
                onClick={() => {
                  if (window.confirm('归档此 Agent？归档后将从列表移除。')) void mutate(true)
                }}
              >
                归档 Agent
              </button>
            )}
          </fieldset>
          {conflict && (
            <button
              type="button"
              className="underline"
              onClick={() => {
                select(null)
                setRevision((v) => v + 1)
              }}
            >
              放弃草稿并重新加载
            </button>
          )}
          <section className="rounded bg-muted p-4">
            <h3 className="font-medium">Prompt 预览</h3>
            <pre className="mt-2 whitespace-pre-wrap break-words font-sans">
              {draft.role_prompt || '输入角色指令以预览。'}
            </pre>
          </section>
        </form>
      </div>
    </main>
  )
}
