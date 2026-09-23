import type { Metadata } from 'next'
import Link from 'next/link'
import { ReviewJobDetail } from '@/components/review/review-job-detail'

export const metadata: Metadata = {
  title: '评审任务详情 · PlutoLab',
  description: '查看代码评审任务的分析、覆盖和发布状态',
}

export default async function ReviewJobDetailPage({
  params,
}: {
  params: Promise<{ jobId: string }>
}) {
  const { jobId } = await params
  return (
    <main className="mx-auto w-full max-w-5xl space-y-6 px-4 py-8 sm:px-6">
      <nav aria-label="评审任务导航" className="text-sm text-muted-foreground">
        <Link href="/review/jobs" className="underline">
          返回评审任务
        </Link>
      </nav>
      <ReviewJobDetail jobId={jobId} />
    </main>
  )
}
