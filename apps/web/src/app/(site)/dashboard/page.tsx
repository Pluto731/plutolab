"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Bot, ImageIcon, Loader2, ScrollText } from "lucide-react";

import { useAuthUser } from "@/components/auth/use-auth";
import { ActivitiesCard } from "@/components/dashboard/activities-card";
import { HeroCard } from "@/components/dashboard/hero-card";
import { NotesPanel } from "@/components/dashboard/notes-panel";
import { StatCard } from "@/components/dashboard/stat-card";
import { StreakCard } from "@/components/dashboard/streak-card";
import { TasksCard } from "@/components/dashboard/tasks-card";
import { TodayCard } from "@/components/dashboard/today-card";
import { TokensCard } from "@/components/dashboard/tokens-card";
import { type DashboardSummary, fetchDashboard } from "@/lib/dashboard";

const STAGGER = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
};
const STAGGER_TRANSITION = (i: number) => ({
  duration: 0.5,
  delay: i * 0.07,
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

      {/*
        12 列 bento — A.1-3 重排:
          Row 1-2: [Hero 7×2]                 [TodayCard 5×1]
                                              [StreakCard 5×1]
          Row 3-4: [NotesPanel 7×2]           [TokensCard 5×1]
                                              [TasksCard 5×1]
          Row 5:   [StatCard RAG 4] [Agent 4] [Image 4]
          Row 6:   [Activities 12×1]

        让"笔记"成为视觉第二主角 (NotesPanel 7×2), Hero 仍是第一主角.
        Today/Streak 在 Hero 右侧, 形成"今日写作进度"叙事块.
        移动端 grid-cols-1 自然顺次, 顺序天然合理.
      */}
      <div className="grid auto-rows-[minmax(140px,auto)] grid-cols-1 gap-4 md:grid-cols-12">
        {/* Hero 7×2 — 仍是主焦点 */}
        <motion.div
          {...STAGGER}
          transition={STAGGER_TRANSITION(0)}
          className="md:col-span-7 md:row-span-2"
        >
          <HeroCard name={user?.name ?? null} />
        </motion.div>

        {/* TodayCard 5×1 — Hero 右上 */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(1)} className="md:col-span-5">
          <TodayCard words={data.today_words} />
        </motion.div>

        {/* StreakCard 5×1 — Hero 右下 */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(2)} className="md:col-span-5">
          <StreakCard days={data.writing_streak} />
        </motion.div>

        {/* NotesPanel 7×2 — 笔记升级到大卡 (代替原 StatCard 笔记格) */}
        <motion.div
          {...STAGGER}
          transition={STAGGER_TRANSITION(3)}
          className="md:col-span-7 md:row-span-2"
        >
          <NotesPanel count={data.notes_count} recent={data.recent_activities} />
        </motion.div>

        {/* TokensCard 5×1 — Notes 右上 */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(4)} className="md:col-span-5">
          <TokensCard used={data.tokens_this_month} limit={data.tokens_limit} />
        </motion.div>

        {/* TasksCard 5×1 — Notes 右下 */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(5)} className="md:col-span-5">
          <TasksCard count={data.tasks_count} />
        </motion.div>

        {/* Row 5: 3 张小 StatCard 均分 (4/4/4), 比之前 4/3/2/3 整齐, 笔记格已撤 */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(6)} className="md:col-span-4">
          <StatCard
            icon={ScrollText}
            iconGradient="from-blue-500 to-cyan-500"
            label="RAG 文档"
            value={data.rag_docs_count}
            emptyHint="Phase 4 上线时启用"
          />
        </motion.div>
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(7)} className="md:col-span-4">
          <StatCard
            icon={Bot}
            iconGradient="from-indigo-500 to-violet-500"
            label="Agent"
            value={data.agents_count}
            emptyHint="Phase 6"
          />
        </motion.div>
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(8)} className="md:col-span-4">
          <StatCard
            icon={ImageIcon}
            iconGradient="from-pink-500 to-rose-500"
            label="图像生成"
            value={data.images_count}
            emptyHint="Phase 7 上线时启用"
          />
        </motion.div>

        {/* 最近活动 — 12×1 横向铺满, 整页收尾 */}
        <motion.div {...STAGGER} transition={STAGGER_TRANSITION(9)} className="md:col-span-12">
          <ActivitiesCard items={data.recent_activities} />
        </motion.div>
      </div>
    </main>
  );
}
