"use client";

import { motion, type Variants } from "framer-motion";
import {
  Code2,
  FileSearch,
  GitPullRequest,
  Image as ImageIcon,
  StickyNote,
  Workflow,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const features = [
  {
    icon: StickyNote,
    title: "智能笔记",
    description: "Markdown 编辑器 · 标签 · 全文搜索 · AI 自动总结归纳",
    gradient: "from-amber-500 to-orange-500",
    badge: "Phase 3",
    live: false,
  },
  {
    icon: FileSearch,
    title: "RAG 文档问答",
    description: "上传 PDF / Markdown / Word，自然语言提问，AI 回答含原文引用与跳转",
    gradient: "from-violet-500 to-purple-500",
    badge: "Phase 4",
    live: false,
  },
  {
    icon: GitPullRequest,
    title: "AI 代码评审",
    description: "连接 GitHub PR 自动触发 Claude 评审：安全 / 性能 / 风格三维度",
    gradient: "from-fuchsia-500 to-pink-500",
    badge: "Phase 5",
    live: false,
  },
  {
    icon: Workflow,
    title: "多 Agent 协作",
    description: "可视化编排工作流，研究员 / 文案 / 数据分析师协同完成复杂任务",
    gradient: "from-pink-500 to-rose-500",
    badge: "Phase 6",
    live: false,
  },
  {
    icon: ImageIcon,
    title: "画作收藏",
    description: "Pixiv 风格画廊，收藏精美插画，AI 自动打标签 · 寻找相似 · 风格分组",
    gradient: "from-emerald-500 to-teal-500",
    badge: "Phase 7",
    live: false,
  },
  {
    icon: Code2,
    title: "API & 文档",
    description: "FastAPI 自动生成 OpenAPI 文档，开箱即用的 REST + WebSocket",
    gradient: "from-cyan-500 to-sky-500",
    badge: "Live",
    live: true,
  },
];

// stagger 容器 — 子项依次入场, 间隔 0.08s
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 30 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: "easeOut" },
  },
};

export function Features() {
  return (
    <section id="features" className="relative px-6 py-24">
      {/* 标题区 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.6 }}
        className="mx-auto max-w-2xl text-center"
      >
        <h2 className="bg-gradient-to-r from-zinc-900 to-zinc-600 bg-clip-text text-3xl font-bold tracking-tight text-transparent dark:from-zinc-100 dark:to-zinc-400 sm:text-4xl">
          一站式 · 全能工具箱
        </h2>
        <p className="mt-4 text-base text-zinc-500 dark:text-zinc-400">
          6 个模块 · 覆盖知识管理 · AI 协作 · 创作收藏
        </p>
      </motion.div>

      {/* 卡片网格 */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-50px" }}
        className="mx-auto mt-16 grid max-w-6xl grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
      >
        {features.map((f) => {
          const Icon = f.icon;
          return (
            <motion.div
              key={f.title}
              variants={itemVariants}
              whileHover={{ y: -6 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
            >
              <Card
                className="group h-full overflow-hidden border border-white/40 bg-white/30 backdrop-blur-2xl
                           shadow-[inset_0_1px_0_0_rgba(255,255,255,0.7),0_8px_30px_-12px_rgba(0,0,0,0.08)]
                           transition-all duration-300
                           hover:border-white/60 hover:bg-white/50
                           hover:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.9),0_20px_50px_-12px_rgba(139,92,246,0.25)]
                           dark:border-white/[0.06] dark:bg-white/[0.03]
                           dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_8px_30px_-12px_rgba(0,0,0,0.5)]
                           dark:hover:border-white/[0.12] dark:hover:bg-white/[0.05]
                           dark:hover:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1),0_20px_50px_-12px_rgba(139,92,246,0.4)]"
              >
                <CardHeader>
                  <div className="flex items-center justify-between">
                    {/* 渐变图标 — hover 旋转 + 放大 */}
                    <div
                      className={`inline-flex size-12 items-center justify-center rounded-xl bg-gradient-to-br ${f.gradient} text-white shadow-lg transition-all duration-300 group-hover:scale-110 group-hover:rotate-6 group-hover:shadow-xl`}
                    >
                      <Icon className="size-6" />
                    </div>
                    <Badge
                      variant={f.live ? "default" : "secondary"}
                      className={
                        f.live
                          ? "bg-emerald-500 text-white hover:bg-emerald-500/90 dark:bg-emerald-500 dark:text-white"
                          : ""
                      }
                    >
                      {f.live && (
                        <span className="mr-1 inline-block size-1.5 animate-pulse rounded-full bg-white" />
                      )}
                      {f.badge}
                    </Badge>
                  </div>
                  <CardTitle className="mt-5 text-xl tracking-tight">
                    {f.title}
                  </CardTitle>
                  <CardDescription className="mt-2 leading-relaxed">
                    {f.description}
                  </CardDescription>
                </CardHeader>
              </Card>
            </motion.div>
          );
        })}
      </motion.div>
    </section>
  );
}
