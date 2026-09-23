'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ErrorNotice } from '@/components/ui/error-notice'
import { Skeleton } from '@/components/ui/skeleton'
import { reviewApi, ReviewRequestError } from '@/lib/review'
import {
  focusAreas,
  ruleDraft,
  validateRules,
  type RepositoryRules,
  type RuleDraft,
} from '@/lib/review-rules'

export function RuleEditor({
  installationId,
  repoId,
  onClose,
  onSaved,
}: {
  installationId: string
  repoId: string
  onClose: () => void
  onSaved: () => void
}) {
  const [rules, setRules] = useState<RepositoryRules | null>(null)
  const [draft, setDraft] = useState<RuleDraft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [latest, setLatest] = useState<RepositoryRules | null>(null)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError(null)
    reviewApi
      .rules(installationId, repoId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        setRules(value)
        setDraft(ruleDraft(value))
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setError(e.message)
      })
    return () => controller.abort()
  }, [installationId, repoId, retry])

  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!draft || !rules || busy || conflict) return
    const result = validateRules(draft, rules.rules_version)
    if (result.error) {
      setError(result.error)
      return
    }
    setError(null)
    setBusy(true)
    try {
      const value = await reviewApi.save(installationId, repoId, result.value!)
      setRules(value)
      setDraft(ruleDraft(value))
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败，请重试。')
      if (e instanceof ReviewRequestError && e.status === 409) setConflict(true)
    } finally {
      setBusy(false)
    }
  }

  async function readLatest() {
    setBusy(true)
    try {
      setLatest(await reviewApi.rules(installationId, repoId))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取失败，请重试。')
    } finally {
      setBusy(false)
    }
  }

  const update = (value: Partial<RuleDraft>) => setDraft((d) => d && { ...d, ...value })
  return (
    <section aria-label="仓库评审规则" className="space-y-5 rounded-xl border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold">{rules?.repo_name ?? '仓库评审规则'}</h2>
        <Button variant="ghost" onClick={onClose} disabled={busy}>
          关闭规则
        </Button>
      </div>
      <ErrorNotice message={error} />
      {!rules || !draft ? (
        error ? (
          <Button variant="outline" onClick={() => setRetry((v) => v + 1)}>
            重试读取规则
          </Button>
        ) : (
          <Skeleton aria-label="正在加载规则" className="h-48 w-full" />
        )
      ) : (
        <form onSubmit={save} noValidate className="space-y-5">
          <p className="text-sm text-muted-foreground">
            当前规则版本 v{rules.rules_version}；保存时会检查版本。
          </p>
          <fieldset disabled={busy} className="space-y-5">
            <legend className="sr-only">评审规则</legend>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={(e) => update({ enabled: e.target.checked })}
              />
              启用此仓库的自动评审
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="review-min">最小 PR 行数</Label>
                <Input
                  id="review-min"
                  inputMode="numeric"
                  value={draft.min}
                  onChange={(e) => update({ min: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="review-max">最大 PR 行数（留空不限）</Label>
                <Input
                  id="review-max"
                  inputMode="numeric"
                  value={draft.max}
                  onChange={(e) => update({ max: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="review-paths">忽略路径（每行一条）</Label>
              <textarea
                id="review-paths"
                rows={4}
                value={draft.paths}
                onChange={(e) => update({ paths: e.target.value })}
                aria-describedby="review-path-help"
                className="w-full rounded-md border bg-background p-3 text-sm focus-visible:ring-2 focus-visible:ring-ring"
              />
              <p id="review-path-help" className="text-sm text-muted-foreground">
                例如 docs/** 或 *.lock。最多 100 条相对 glob，每条 256 字符；不支持正则。
              </p>
            </div>
            <fieldset className="space-y-2">
              <legend className="mb-2 text-sm font-medium">评审方向（至少一项）</legend>
              <div className="flex flex-wrap gap-5">
                {focusAreas.map((focus) => (
                  <label key={focus} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={draft.focus.includes(focus)}
                      onChange={(e) =>
                        update({
                          focus: e.target.checked
                            ? [...draft.focus, focus]
                            : draft.focus.filter((f) => f !== focus),
                        })
                      }
                    />
                    {{ security: '安全', performance: '性能', quality: '质量' }[focus]}
                  </label>
                ))}
              </div>
            </fieldset>
          </fieldset>
          {conflict && (
            <div className="space-y-3 rounded-md border p-3" role="status">
              <p>版本冲突：草稿仍保留。请读取最新规则并比较后选择；不会自动覆盖。</p>
              {!latest ? (
                <Button type="button" variant="outline" disabled={busy} onClick={readLatest}>
                  读取最新版本
                </Button>
              ) : (
                <>
                  <p>
                    最新 v{latest.rules_version}：{latest.enabled ? '启用' : '停用'}，行数{' '}
                    {latest.min_pr_lines}–{latest.max_pr_lines ?? '不限'}，方向{' '}
                    {latest.focus_areas.join('、')}
                  </p>
                  <pre className="max-h-32 overflow-auto whitespace-pre-wrap text-sm">
                    忽略路径：{latest.skip_paths.join('\n') || '无'}
                  </pre>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setRules(latest)
                        setDraft(ruleDraft(latest))
                        setConflict(false)
                        setLatest(null)
                        setError(null)
                      }}
                    >
                      采用服务器规则
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setRules(latest)
                        setConflict(false)
                        setLatest(null)
                        setError(null)
                      }}
                    >
                      保留草稿，按新版本再保存
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}
          <Button type="submit" disabled={busy || conflict}>
            {busy ? '处理中…' : '保存规则'}
          </Button>
        </form>
      )}
    </section>
  )
}
