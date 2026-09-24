'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { useAuthUser } from '@/components/auth/use-auth'
import { Button } from '@/components/ui/button'
import { ErrorNotice } from '@/components/ui/error-notice'
import { Skeleton } from '@/components/ui/skeleton'
import { installationCallback, installationUrl, reviewApi, type Installations } from '@/lib/review'
import { RepositoryBrowser } from './repository-browser'

export function ReviewSettings() {
  const { user, loading } = useAuthUser()
  if (loading) return <Skeleton aria-label="正在验证登录" className="h-64 w-full" />
  if (!user)
    return (
      <section className="space-y-4 rounded-xl border p-6">
        <h2 className="text-xl font-semibold">登录后管理评审设置</h2>
        <p className="text-muted-foreground">请使用已关联个人 GitHub 账号的 PlutoLab 账户登录。</p>
        <Button asChild>
          <Link href="/login">前往登录</Link>
        </Button>
      </section>
    )
  return <InstallationSettings key={user.id} accountName={user.name ?? user.email} />
}

function InstallationSettings({ accountName }: { accountName: string }) {
  const [data, setData] = useState<Installations | null>(null)
  const [selected, setSelected] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [revision, setRevision] = useState(0)
  const [confirmRevoke, setConfirmRevoke] = useState(false)
  const [callback, setCallback] = useState<ReturnType<typeof installationCallback>>(null)
  const callbackRead = useRef(false)
  // State remains in memory only. Explicit confirmation avoids duplicate POSTs
  // from React Strict Mode and prevents mutation on a navigation GET.
  useEffect(() => {
    if (callbackRead.current) return
    callbackRead.current = true
    const search = window.location.search
    try {
      setCallback(installationCallback(search))
    } catch {
      setError('安装回调无效，请重新发起安装。')
    } finally {
      if (search) window.history.replaceState(null, '', window.location.pathname)
    }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    setLoadError(null)
    setData(null)
    reviewApi
      .installations(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        setData(value)
        setSelected((old) =>
          value.installations.some((i) => i.active && i.installation_id === old)
            ? old
            : (value.installations.find((i) => i.active)?.installation_id ?? ''),
        )
      })
      .catch((e: Error) => {
        if (!controller.signal.aborted) setLoadError(e.message)
      })
    return () => controller.abort()
  }, [revision])

  async function start() {
    setBusy(true)
    setError(null)
    try {
      const result = await reviewApi.start()
      window.location.assign(installationUrl(result.installation_url))
    } catch (e) {
      setError(e instanceof Error ? e.message : '发起安装失败，请重试。')
    } finally {
      setBusy(false)
    }
  }
  async function bind() {
    if (!callback || busy) return
    setBusy(true)
    setError(null)
    const claim = callback
    setCallback(null)
    try {
      await reviewApi.bind(claim.installationId, claim.state)
      setNotice('个人 GitHub 安装已验证并绑定。')
    } catch {
      setError(
        '绑定未完成。请刷新查看绑定状态；若仍未绑定，请重新发起安装。一次性验证可能已过期或已使用。',
      )
    } finally {
      setBusy(false)
      setRevision((n) => n + 1)
    }
  }
  async function revoke() {
    if (!selected || busy) return
    setBusy(true)
    setError(null)
    try {
      await reviewApi.revoke(selected)
      setSelected('')
      setConfirmRevoke(false)
      setNotice('安装已解绑，已停止新的评审调度与发布。')
      setRevision((n) => n + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : '解绑失败，请重试。')
    } finally {
      setBusy(false)
    }
  }
  const active = data?.installations.filter((i) => i.active) ?? []
  return (
    <div className="space-y-8">
      {notice && (
        <div
          role="status"
          className="fixed bottom-6 right-4 z-50 flex max-w-[calc(100vw-2rem)] items-center justify-between gap-3 rounded-lg border bg-card p-4 text-sm shadow-lg sm:right-6"
        >
          <span>{notice}</span>
          <Button variant="ghost" size="sm" onClick={() => setNotice(null)}>
            关闭通知
          </Button>
        </div>
      )}
      <section className="space-y-4 rounded-xl border bg-card p-5" aria-label="GitHub App 安装">
        <h2 className="text-xl font-semibold">GitHub App 安装</h2>
        <p className="text-sm text-muted-foreground">
          当前账户：{accountName}。仅支持本人个人 GitHub 安装；暂不支持组织。
        </p>
        <ErrorNotice message={error} />
        {callback && (
          <div className="space-y-3 rounded-lg border p-4">
            <p>
              确认将安装 #{callback.installationId} 绑定到当前账户？服务器将核验 GitHub 账号归属。
            </p>
            <div className="flex gap-2">
              <Button disabled={busy} onClick={bind}>
                确认绑定
              </Button>
              <Button variant="outline" onClick={() => setCallback(null)}>
                取消绑定
              </Button>
            </div>
          </div>
        )}
        <ErrorNotice message={loadError} />
        {loadError ? (
          <Button variant="outline" disabled={busy} onClick={() => setRevision((n) => n + 1)}>
            重试安装状态
          </Button>
        ) : !data ? (
          <Skeleton aria-label="正在加载安装" className="h-20 w-full" />
        ) : (
          <>
            <p className="text-sm">GitHub 账号 ID：{data.github_account_id ?? '未关联'}</p>
            {active.length === 0 ? (
              <div className="space-y-3">
                <p>
                  {data.installations.length
                    ? '安装已停用。历史规则仍保留，新的评审与发布已停止。'
                    : '尚未绑定 GitHub App。绑定后可选择仓库并配置规则。'}
                </p>
                <Button disabled={busy || !data.github_account_id || !!callback} onClick={start}>
                  {busy ? '处理中…' : '安装并绑定 GitHub App'}
                </Button>
                {!data.github_account_id && (
                  <p className="text-sm text-muted-foreground">
                    请先在{' '}
                    <Link href="/settings" className="font-medium text-primary underline">
                      账号设置
                    </Link>{' '}
                    中关联 GitHub 账号。
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                <label className="flex flex-wrap items-center gap-3">
                  已绑定的个人安装
                  <select
                    aria-label="选择安装"
                    className="rounded-md border bg-background p-2"
                    value={selected}
                    disabled={busy}
                    onChange={(e) => {
                      setSelected(e.target.value)
                      setConfirmRevoke(false)
                    }}
                  >
                    {active.map((i) => (
                      <option key={i.installation_id} value={i.installation_id}>
                        #{i.installation_id} · 已启用
                      </option>
                    ))}
                  </select>
                </label>
                {confirmRevoke ? (
                  <div
                    className="space-y-3 rounded-md border border-destructive/30 p-4"
                    role="group"
                    aria-label="确认解绑安装"
                  >
                    <p>
                      解绑后将停止此安装的新评审与发布，并停用仓库规则；不会从 GitHub 卸载 App。
                    </p>
                    <Button variant="destructive" disabled={busy} onClick={revoke}>
                      确认解绑
                    </Button>{' '}
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() => setConfirmRevoke(false)}
                    >
                      取消
                    </Button>
                  </div>
                ) : (
                  <Button variant="outline" disabled={busy} onClick={() => setConfirmRevoke(true)}>
                    解绑安装
                  </Button>
                )}
              </div>
            )}
            <Button variant="ghost" disabled={busy} onClick={() => setRevision((n) => n + 1)}>
              刷新安装状态
            </Button>
          </>
        )}
      </section>
      {data && selected && active.some((i) => i.installation_id === selected) && !busy && (
        <RepositoryBrowser key={selected} installationId={selected} notify={setNotice} />
      )}
    </div>
  )
}
