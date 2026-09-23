import type { Metadata } from 'next'
import Link from 'next/link'
import { ReviewJobs } from '@/components/review/review-jobs'

export const metadata: Metadata = {
  title: '评审任务 · PlutoLab',
  description: '查看仓库历史 AI 代码评审任务与结果',
}

export default function ReviewJobsPage() {
  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 px-4 py-8 sm:px-6">
      <header className="space-y-2">
        <nav aria-label="评审页面导航" className="text-sm text-muted-foreground">
          <Link href="/review/settings" className="underline">
            安装与仓库设置
          </Link>
        </nav>
        <h1 className="text-3xl font-semibold tracking-tight">评审任务</h1>
        <p className="text-muted-foreground">
          按仓库查看历史评审、分析覆盖和 GitHub 评论交付状态。
        </p>
      </header>
      <ReviewJobs />
    </main>
  )
}
