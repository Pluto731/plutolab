import { Skeleton } from '@/components/ui/skeleton'

export default function LoadingReviewJob() {
  return (
    <main aria-label="正在加载评审详情" className="mx-auto w-full max-w-5xl space-y-5 px-4 py-8">
      <Skeleton className="h-24 w-full" />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-20 w-full" />
        ))}
      </div>
      <Skeleton className="h-64 w-full" />
    </main>
  )
}
