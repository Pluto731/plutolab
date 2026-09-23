import type { Metadata } from 'next'
import { ReviewSettings } from '@/components/review/review-settings'

export const metadata: Metadata = {
  title: '评审设置 · PlutoLab',
  description: '管理个人 GitHub App 安装、仓库与评审规则',
  referrer: 'no-referrer',
}

export default function ReviewSettingsPage() {
  return (
    <main className="mx-auto w-full max-w-4xl space-y-8 px-4 py-8 sm:px-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">评审设置</h1>
        <p className="text-muted-foreground">连接个人 GitHub 账户，为每个仓库设定评审范围。</p>
      </header>
      <ReviewSettings />
    </main>
  )
}
