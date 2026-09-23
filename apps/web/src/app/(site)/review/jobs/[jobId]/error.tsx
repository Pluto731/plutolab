'use client'

import { Button } from '@/components/ui/button'

export default function ReviewJobRouteError({
  unstable_retry,
}: {
  error: Error & { digest?: string }
  unstable_retry: () => void
}) {
  return (
    <main className="mx-auto max-w-3xl space-y-4 px-4 py-10">
      <div role="alert" className="rounded-xl border border-destructive/30 p-4">
        <h1 className="font-semibold">评审详情暂时无法显示</h1>
        <p className="mt-1 text-sm text-muted-foreground">请重试读取任务详情。</p>
      </div>
      <Button variant="outline" onClick={() => unstable_retry()}>
        重试
      </Button>
    </main>
  )
}
