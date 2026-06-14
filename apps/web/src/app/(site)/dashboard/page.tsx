"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Bot, FileText, ImageIcon, Loader2, ScrollText } from "lucide-react";

import { useAuthUser } from "@/components/auth/use-auth";
import { ActivitiesCard } from "@/components/dashboard/activities-card";
import { HeroCard } from "@/components/dashboard/hero-card";
import { StatCard } from "@/components/dashboard/stat-card";
import { TasksCard } from "@/components/dashboard/tasks-card";
import { TokensCard } from "@/components/dashboard/tokens-card";
import { type DashboardSummary, fetchDashboard } from "@/lib/dashboard";

const STAGGER = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
};
const STAGGER_TRANSITION = (i: number) => ({
  duration: 0.5,
  delay: i * 0.08,
  ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
});

export default function DashboardPage() {
  const { user } = useAuthUser();
  const { data, isLoading } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary", user?.id ?? "anon"],
    queryFn: fetchDashboard,
    refetchOnWindowFocus: false,
    staleTime: 30 * 1000,
  });

  if (isLoading || !data) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> 加载中…
      </main>
    );
  }

  const isAnonPreview = !data.is_authenticated;

  return (
    <main className="mx-auto max-w-7xl px-4 pb-24 pt-20 md:px-6 md:pt-10">
      {/* 顶部访客横幅 — 仅未登录 (说明数据是演示性的) */}
      {isAnonPreview && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-violet-200 bg-violet-50/80 px-4 py-2.5 text-sm backdrop-blur dark:border-violet-900/40 dark:bg-violet-950/30"
        >
          <span className="rounded-full bg-violet-500 px-2 py-0.5 text-xs font-semibold text-white">
            预览
          </span>
          <span className="text-muted-foreground">
            以下是访客视图的演示数据。
          </span>
          <a
            href="/login"
            className="ml-auto font-medium text-violet-600 hover:underline dark:text-violet-300"
          >
            登录看自己的数据 →
          </a>
        </motion.div>
      )}

      {/* Bento 12 列 — 真非对称: 7×2 / 5×1 / 5×1 / 4×1 / 3×1 / 2×1 / 3×1 / 12×1
       * (Hero 7×2 主焦点, 右侧 Tokens 5×1 + Tasks 5×1 上下叠拼成 5×2, 第二行
       * 数据卡尺寸 4/3/2/3 阶梯式变化, 最后 Activities 12×1 横向铺满)
       * 移动单列从上往下顺次. */}
      <div className="grid auto-rows-[minmax(140px,auto)] grid-cols-1 gap-4 md:grid-cols-12">
        {/* Hero 主卡 — 7×2, 左大 */}
        <motion.div
          {...STAGGER}
          transition={STAGGER_TRANSITION(0)}
          className="md:col-span-7 md:row-span-2"
        >
          <HeroCard name={user?.name ?? null} />
        </motion.div>

        {/* Tokens — 5×1, Hero 右上 */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(1)} className="md:col-span-5">
          <TokensCard used={data.tokens_this_month} limit={data.tokens_limit} />
        </motion.div>

        {/* Tasks — 5×1, Hero 右下 (跟 Tokens 上下叠拼成 Hero 等高) */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(2)} className="md:col-span-5">
          <TasksCard count={data.tasks_count} />
        </motion.div>

        {/* 4 张数据卡 — 尺寸阶梯式 4/3/2/3, 节奏感非对称 */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(3)} className="md:col-span-4">
          <StatCard
            icon={FileText}
            iconGradient="from-violet-500 to-fuchsia-500"
            label="笔记"
            value={data.notes_count}
            emptyHint="Phase 3 还没做"
          />
        </motion.div>
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(4)} className="md:col-span-3">
          <StatCard
            icon={ScrollText}
            iconGradient="from-blue-500 to-cyan-500"
            label="RAG 文档"
            value={data.rag_docs_count}
            emptyHint="Phase 4 上线时启用"
          />
        </motion.div>
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(5)} className="md:col-span-2">
          <StatCard
            icon={Bot}
            iconGradient="from-indigo-500 to-violet-500"
            label="Agent"
            value={data.agents_count}
            emptyHint="Phase 6"
          />
        </motion.div>
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(6)} className="md:col-span-3">
          <StatCard
            icon={ImageIcon}
            iconGradient="from-pink-500 to-rose-500"
            label="图像生成"
            value={data.images_count}
            emptyHint="Phase 7 上线时启用"
          />
        </motion.div>

        {/* 最近活动 — 12×1 横向铺满, 整页收尾 */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(7)} className="md:col-span-12">
          <ActivitiesCard items={data.recent_activities} />
        </motion.div>
      </div>
    </main>
  );
}
