import { cn } from "@/lib/utils";

// 通用骨架屏 - 苹果毛玻璃风, pulse 动画
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "animate-pulse rounded-md border border-white/30 bg-white/40 backdrop-blur-md dark:border-white/[0.04] dark:bg-white/[0.05]",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };
