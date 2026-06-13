"use client";

import { CheckSquare, Circle } from "lucide-react";

interface TasksCardProps {
  count: number;
}

// Phase 3 真做时拉真任务列表; 现在 stub 一份
const DEMO_TASKS = [
  { title: "修 RAG 检索 bug", done: false },
  { title: "写 Phase 3 设计文档", done: false },
  { title: "整理 LLM 微调笔记", done: false },
];

export function TasksCard({ count }: TasksCardProps) {
  const items = count > 0 ? DEMO_TASKS.slice(0, count) : [];

  return (
    <div className="group relative h-full overflow-hidden rounded-2xl border border-border bg-card/80 p-5 backdrop-blur-md">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 shadow-md">
          <CheckSquare className="size-4 text-white" />
        </div>
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          待办
        </p>
        <span className="ml-auto text-2xl font-bold tabular-nums">{count}</span>
      </div>

      {items.length === 0 ? (
        <div className="flex h-20 flex-col items-center justify-center text-center">
          <p className="text-sm text-muted-foreground">暂无待办</p>
          <p className="mt-0.5 text-xs text-muted-foreground/70">
            Phase 3 任务系统上线后会出现这里
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((t, i) => (
            <li key={i} className="flex items-center gap-2 text-sm">
              <Circle className="size-3.5 shrink-0 text-emerald-500" />
              <span className="truncate">{t.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
