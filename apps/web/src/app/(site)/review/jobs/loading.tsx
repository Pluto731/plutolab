import { Skeleton } from '@/components/ui/skeleton'

export default function LoadingReviewJobs() {
  return (
    <main aria-label="正在加载评审任务" className="mx-auto w-full max-w-5xl space-y-5 px-4 py-8">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-16 w-full" />
      {Array.from({ length: 4 }, (_, index) => (
        <Skeleton key={index} className="h-20 w-full" />
      ))}
    </main>
  )
}
