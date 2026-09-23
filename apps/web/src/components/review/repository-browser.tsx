'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ErrorNotice } from '@/components/ui/error-notice'
import { Skeleton } from '@/components/ui/skeleton'
import { reviewApi, type RepositoryPage } from '@/lib/review'
import { validRepositorySearch } from '@/lib/review-rules'
import { RuleEditor } from './rule-editor'

export function RepositoryBrowser({
  installationId,
  notify,
}: {
  installationId: string
  notify: (message: string) => void
}) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState<RepositoryPage | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    setData(null)
    setError(null)
    reviewApi
      .repositories(installationId, filter, page, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setData(value)
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setError(e.message)
      })
    return () => controller.abort()
  }, [installationId, filter, page, revision])
  return (
    <section className="space-y-5" aria-label="可访问仓库">
      <div>
        <h2 className="text-xl font-semibold">仓库与评审规则</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          仅列出此安装可访问的仓库。新增仓库默认不启用评审。
        </p>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (!validRepositorySearch(query)) {
            setSearchError('搜索最多 100 字符，仅支持英文字母、数字、空格及 _ . / -。')
            return
          }
          setSearchError(null)
          setFilter(query)
          setPage(1)
          setRevision((n) => n + 1)
        }}
      >
        <Input
          aria-label="搜索仓库"
          placeholder="搜索 owner/repository"
          maxLength={100}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Button type="submit" variant="outline">
          搜索
        </Button>
      </form>
      <ErrorNotice message={searchError} />
      <ErrorNotice message={error} />
      {error ? (
        <Button variant="outline" onClick={() => setRevision((n) => n + 1)}>
          重试仓库列表
        </Button>
      ) : !data ? (
        <div aria-label="正在加载仓库" className="space-y-3">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : (
        <>
          {data.repositories.length === 0 ? (
            <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">
              {filter
                ? '没有匹配的仓库，请调整关键词。'
                : '此安装暂无可访问仓库，请检查 GitHub App 的仓库授权。'}
            </p>
          ) : (
            <ul className="divide-y rounded-xl border bg-card">
              {data.repositories.map((repo) => (
                <li
                  key={repo.repo_id}
                  className="flex flex-wrap items-center justify-between gap-3 p-4"
                >
                  <div className="min-w-0">
                    <p className="break-all font-medium">{repo.repo_name}</p>
                    <p className="text-sm text-muted-foreground">
                      {repo.private ? '私有' : '公开'} ·{' '}
                      {repo.enabled ? '评审已启用' : '评审已停用'} · v{repo.rules_version}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    aria-label={`配置 ${repo.repo_name}`}
                    onClick={() => setSelected(repo.repo_id)}
                  >
                    配置规则
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <nav aria-label="仓库分页" className="flex flex-wrap items-center gap-3">
            <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              上一页
            </Button>
            <span className="text-sm">
              第 {page} 页 · 共 {data.total_count} 个仓库
            </span>
            <Button
              variant="outline"
              disabled={page * data.per_page >= data.total_count}
              onClick={() => setPage((p) => p + 1)}
            >
              下一页
            </Button>
          </nav>
        </>
      )}
      {selected && (
        <RuleEditor
          key={`${installationId}:${selected}`}
          installationId={installationId}
          repoId={selected}
          onClose={() => setSelected(null)}
          onSaved={() => {
            notify('规则已保存。')
            setRevision((n) => n + 1)
          }}
        />
      )}
    </section>
  )
}
