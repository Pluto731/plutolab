import { Skeleton } from "@/components/ui/skeleton";

// Next.js App Router 路由级 loading state
// 路由 chunk 还没加载完时显示
export default function GlobalLoading() {
  return (
    <main className="relative flex min-h-screen items-center justify-center px-6 py-32">
      <div className="mx-auto flex max-w-2xl flex-col items-center text-center">
        {/* 🪐 占位 */}
        <Skeleton className="size-24 rounded-full" />

        {/* 标题占位 */}
        <Skeleton className="mt-8 h-14 w-72" />

        {/* 副标题占位 */}
        <Skeleton className="mt-4 h-6 w-56" />
        <Skeleton className="mt-2 h-5 w-80" />

        {/* 按钮占位 */}
        <div className="mt-10 flex gap-4">
          <Skeleton className="h-11 w-32" />
          <Skeleton className="h-11 w-28" />
        </div>
      </div>
    </main>
  );
}
