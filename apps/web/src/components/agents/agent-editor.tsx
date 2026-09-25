'use client'

import { useEffect, useState } from 'react'
import { Bot, Plus, RefreshCw, Sparkles } from 'lucide-react'
import { AgentRequestError, agentsApi, type AgentCreate, type AgentPublic } from '@/lib/agents'
import { Phase6Navigation } from './phase6-navigation'

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
    <main className="mx-auto max-w-6xl space-y-6 px-4 py-7 sm:px-6 md:py-10">
      <Phase6Navigation active="/agents" />
      <header className="relative isolate overflow-hidden rounded-[2rem] bg-zinc-950 px-6 py-7 text-white shadow-xl shadow-violet-950/10 sm:px-9 sm:py-9">
        <div
          aria-hidden
          className="absolute -right-16 -top-36 -z-10 size-96 rounded-full bg-violet-600/40 blur-3xl"
        />
        <div
          aria-hidden
          className="absolute -bottom-40 right-1/3 -z-10 size-72 rounded-full bg-fuchsia-600/25 blur-3xl"
        />
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl">
            <p className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-200">
              <Sparkles className="size-3.5" /> Phase 06 <span className="text-white/35">/</span>{' '}
              Agent Studio
            </p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">定义你的协作成员</h1>
            <p className="mt-3 text-sm leading-6 text-zinc-300 sm:text-base">
              为每个 Agent 配置清晰角色、模型与只读工具，再把它们组合成可运行的工作流。
            </p>
          </div>
          <div className="flex items-center gap-3 border-l border-white/15 pl-4 sm:pl-6">
            <span className="grid size-11 place-items-center rounded-2xl bg-white/10 text-violet-200">
              <Bot className="size-5" />
            </span>
            <div>
              <p className="font-mono text-2xl font-semibold tabular-nums">{total}</p>
              <p className="text-xs text-zinc-400">可用成员</p>
            </div>
          </div>
        </div>
      </header>
      {error && (
        <p role="alert" className="text-destructive">
          {error}
        </p>
      )}
      {message && (
        <p
          role="status"
          className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-300"
        >
          <span className="size-1.5 rounded-full bg-emerald-500" /> {message}
        </p>
      )}
      <div className="grid gap-6 md:grid-cols-[260px_1fr]">
        <aside className="space-y-4 md:pt-1">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">你的成员</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">角色与版本</p>
            </div>
            <button
              disabled={busy}
              onClick={() => select(null)}
              className="inline-flex items-center gap-1.5 rounded-full bg-violet-600 px-3 py-2 text-xs font-medium text-white shadow-md shadow-violet-600/20 transition hover:bg-violet-500 disabled:opacity-50"
            >
              <Plus className="size-3.5" /> 新建
            </button>
          </div>
          <button
            type="button"
            aria-label="刷新 Agent 列表"
            disabled={busy || loading}
            onClick={() => setRevision((v) => v + 1)}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-50"
          >
            <RefreshCw className="size-3" /> 刷新列表
          </button>
          {loading ? (
            <p role="status">加载中…</p>
          ) : items.length === 0 ? (
            <p>暂无 Agent。</p>
          ) : (
            <ul className="space-y-1">
              {items.map((agent) => (
                <li key={agent.id}>
                  <button
                    disabled={busy}
                    onClick={() => select(agent)}
                    className={`group relative flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition ${current?.id === agent.id ? 'bg-violet-500/10 text-foreground' : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'}`}
                  >
                    {current?.id === agent.id && (
                      <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-violet-500" />
                    )}
                    <span
                      className={`grid size-9 shrink-0 place-items-center rounded-xl ${current?.id === agent.id ? 'bg-violet-500 text-white' : 'bg-muted text-muted-foreground group-hover:bg-background'}`}
                    >
                      <Bot className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{agent.name}</span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">
                        版本 {agent.version}
                      </span>
                    </span>
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
          className="space-y-6 rounded-[1.75rem] bg-card/75 p-5 shadow-lg shadow-black/[0.035] ring-1 ring-border/50 backdrop-blur-sm sm:p-7"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-600 dark:text-violet-300">
                身份与行为
              </p>
              <h2 className="mt-1 text-xl font-semibold tracking-tight">
                {current ? '编辑 Agent' : '新建 Agent'}
              </h2>
            </div>
            {current && (
              <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                已保存 · v{current.version}
              </span>
            )}
          </div>
          <fieldset
            disabled={busy || conflict}
            className="grid gap-x-5 gap-y-4 sm:grid-cols-2 disabled:opacity-60"
          >
            <label className="block space-y-1.5 text-sm font-medium">
              名称
              <input
                required
                maxLength={100}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                className="block w-full rounded-xl border border-border/70 bg-background/70 px-3 py-2.5 font-normal outline-none transition focus:border-violet-500/60 focus:ring-4 focus:ring-violet-500/10"
              />
            </label>
            <label className="block space-y-1.5 text-sm font-medium">
              描述
              <textarea
                maxLength={2000}
                value={draft.description}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                className="block w-full rounded-xl border border-border/70 bg-background/70 px-3 py-2.5 font-normal outline-none transition focus:border-violet-500/60 focus:ring-4 focus:ring-violet-500/10"
              />
            </label>
            <label className="block space-y-1.5 text-sm font-medium">
              模型
              <select
                value={draft.model}
                onChange={() => {}}
                className="block w-full rounded-xl border border-border/70 bg-background/70 px-3 py-2.5 font-normal outline-none transition focus:border-violet-500/60 focus:ring-4 focus:ring-violet-500/10"
              >
                <option value="gpt-4o-mini">OpenAI · gpt-4o-mini</option>
              </select>
            </label>
            <label className="flex items-center gap-3 rounded-xl bg-sky-500/[0.06] px-4 py-3 text-sm sm:col-span-2">
              <input
                type="checkbox"
                checked={draft.tools?.includes('search_notes') ?? false}
                onChange={(e) =>
                  setDraft({ ...draft, tools: e.target.checked ? ['search_notes'] : [] })
                }
              />
              <span>
                <span className="block font-medium">搜索本人笔记</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  只读工具，不会修改或删除内容
                </span>
              </span>
            </label>
            <label className="block space-y-1.5 text-sm font-medium sm:col-span-2">
              角色指令
              <textarea
                required
                rows={7}
                maxLength={16000}
                value={draft.role_prompt}
                onChange={(e) => setDraft({ ...draft, role_prompt: e.target.value })}
                className="block w-full resize-y rounded-xl border border-border/70 bg-background/70 px-3 py-3 font-mono text-[13px] font-normal leading-6 outline-none transition focus:border-violet-500/60 focus:ring-4 focus:ring-violet-500/10"
              />
            </label>
            <div className="flex flex-wrap items-center gap-3 border-t border-border/60 pt-4 sm:col-span-2">
              <button
                disabled={!draft.name.trim() || !draft.role_prompt.trim() || busy}
                className="rounded-full bg-violet-600 px-5 py-2.5 text-sm font-medium text-white shadow-md shadow-violet-600/20 transition hover:bg-violet-500 disabled:opacity-50"
              >
                {busy ? '正在保存…' : '保存 Agent'}
              </button>
              {current && (
                <button
                  type="button"
                  className="rounded-full px-4 py-2.5 text-sm text-destructive transition hover:bg-destructive/10"
                  onClick={() => {
                    if (window.confirm('归档此 Agent？归档后将从列表移除。')) void mutate(true)
                  }}
                >
                  归档
                </button>
              )}
              {conflict && (
                <span className="text-sm text-amber-700 dark:text-amber-300">
                  版本冲突，请重新加载后再保存。
                </span>
              )}
            </div>
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
          <section className="overflow-hidden rounded-2xl bg-zinc-950 text-zinc-100">
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
              <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-zinc-300">
                <Sparkles className="size-3.5 text-violet-300" /> Prompt 预览
              </h3>
              <span className="font-mono text-[10px] text-zinc-500">LIVE PREVIEW</span>
            </div>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words px-4 py-4 font-mono text-xs leading-6 text-zinc-300">
              {draft.role_prompt || '输入角色指令以预览。'}
            </pre>
          </section>
        </form>
      </div>
    </main>
  )
}
