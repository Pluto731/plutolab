"use client";

import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Calendar,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  Flag,
  GripVertical,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import {
  createTask,
  deleteTask,
  listTasks,
  type Priority,
  reorderTasks,
  type TaskPublic,
  updateTask,
} from "@/lib/tasks";
import { cn } from "@/lib/utils";

type View = "all" | "today" | "week" | "overdue";

interface TaskWithChildren extends TaskPublic {
  children: TaskPublic[];
}

const VIEWS: { key: View; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "today", label: "今天" },
  { key: "week", label: "本周" },
  { key: "overdue", label: "过期" },
];

const PRIORITY_CYCLE: Record<Priority, Priority> = {
  normal: "high",
  high: "low",
  low: "normal",
};

function startOfTodayMs(): number {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function dueBucket(due: string | null): "overdue" | "today" | "week" | "future" | "none" {
  if (!due) return "none";
  const today = startOfTodayMs();
  const t = new Date(`${due}T00:00:00`).getTime();
  const days = Math.round((t - today) / 86400000);
  if (days < 0) return "overdue";
  if (days === 0) return "today";
  if (days <= 6) return "week";
  return "future";
}

function formatDueLabel(due: string): string {
  const today = startOfTodayMs();
  const t = new Date(`${due}T00:00:00`).getTime();
  const days = Math.round((t - today) / 86400000);
  if (days < 0) return `过期 ${-days} 天`;
  if (days === 0) return "今天";
  if (days === 1) return "明天";
  if (days <= 6) {
    const wd = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    return wd[new Date(`${due}T00:00:00`).getDay()];
  }
  // 同年只显示月日, 跨年显示年月日
  const d = new Date(`${due}T00:00:00`);
  const now = new Date();
  if (d.getFullYear() === now.getFullYear()) {
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  }
  return due;
}

function sortKey(task: TaskPublic): number {
  // (dueBucket × 10) + priorityRank — 低分排前
  const b = dueBucket(task.due_date);
  const bucketRank: Record<string, number> = {
    overdue: 0,
    today: 1,
    week: 2,
    future: 3,
    none: 4,
  };
  const prioRank: Record<Priority, number> = { high: 0, normal: 1, low: 2 };
  return bucketRank[b] * 10 + prioRank[task.priority];
}

function matchesView(task: TaskPublic, view: View): boolean {
  if (view === "all") return true;
  return dueBucket(task.due_date) === view;
}

export default function TasksPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, loading, mounted } = useAuthUser();

  useEffect(() => {
    if (mounted && !loading && !user) router.replace("/login");
  }, [mounted, loading, user, router]);

  const { data: tasks, isLoading } = useQuery<TaskPublic[]>({
    queryKey: ["tasks"],
    queryFn: listTasks,
    enabled: !!user,
    staleTime: 10 * 1000,
  });

  const [newTitle, setNewTitle] = useState("");
  const [view, setView] = useState<View>("all");
  // C-2: 默认全部展开; 用户折叠时记 collapsed set (state 反向避免冷启动闪折叠)
  const [collapsedParents, setCollapsedParents] = useState<Set<string>>(new Set());
  // 当前正在添加子任务的 parent id (null = 没有)
  const [addingSubFor, setAddingSubFor] = useState<string | null>(null);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["tasks"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
  };

  const createMutation = useMutation({
    mutationFn: (title: string) => createTask({ title }),
    onSuccess: () => {
      invalidate();
      setNewTitle("");
    },
  });

  // C-2: 创建子任务 (independent mutation 不重置 newTitle)
  const createSubMutation = useMutation({
    mutationFn: ({ title, parent_id }: { title: string; parent_id: string }) =>
      createTask({ title, parent_id }),
    onSuccess: invalidate,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, done }: { id: string; done: boolean }) =>
      updateTask(id, { done }),
    onSuccess: invalidate,
  });

  const priorityMutation = useMutation({
    mutationFn: ({ id, priority }: { id: string; priority: Priority }) =>
      updateTask(id, { priority }),
    onSuccess: invalidate,
  });

  const dueMutation = useMutation({
    mutationFn: ({ id, due_date }: { id: string; due_date: string | null }) =>
      updateTask(id, { due_date }),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: invalidate,
  });

  // C-1: 拖拽排序
  const reorderMutation = useMutation({
    mutationFn: (ids: string[]) => reorderTasks(ids),
    onSuccess: invalidate,
  });
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // 视图计数 (仅未完成参与计数)
  const viewCounts = useMemo(() => {
    if (!tasks) return { all: 0, today: 0, week: 0, overdue: 0 } as Record<View, number>;
    const undoneOnly = tasks.filter((t) => !t.done);
    return {
      all: undoneOnly.length,
      today: undoneOnly.filter((t) => dueBucket(t.due_date) === "today").length,
      week: undoneOnly.filter((t) => dueBucket(t.due_date) === "week").length,
      overdue: undoneOnly.filter((t) => dueBucket(t.due_date) === "overdue").length,
    } satisfies Record<View, number>;
  }, [tasks]);

  // C-2: 视图过滤只在顶层任务级别. 子任务跟随父任务显示 (不参与视图过滤)
  const { undone, done } = useMemo(() => {
    if (!tasks)
      return {
        undone: [] as TaskWithChildren[],
        done: [] as TaskWithChildren[],
      };

    // 按 parent_id 分组建索引
    const childMap = new Map<string, TaskPublic[]>();
    for (const t of tasks) {
      if (t.parent_id) {
        const arr = childMap.get(t.parent_id) ?? [];
        arr.push(t);
        childMap.set(t.parent_id, arr);
      }
    }
    const withChildren = (p: TaskPublic): TaskWithChildren => ({
      ...p,
      children: (childMap.get(p.id) ?? []).sort(
        (a, b) => a.sort_order - b.sort_order,
      ),
    });

    const tops = tasks.filter((t) => !t.parent_id && matchesView(t, view));
    const sortFn =
      view === "all"
        ? (a: TaskPublic, b: TaskPublic) => a.sort_order - b.sort_order
        : (a: TaskPublic, b: TaskPublic) => sortKey(a) - sortKey(b);
    const u = tops.filter((t) => !t.done).sort(sortFn).map(withChildren);
    const d = tops.filter((t) => t.done).map(withChildren);
    return { undone: u, done: d };
  }, [tasks, view]);

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIndex = undone.findIndex((t) => t.id === active.id);
    const newIndex = undone.findIndex((t) => t.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const newUndone = arrayMove(undone, oldIndex, newIndex);
    // 乐观更新缓存, 让 UI 立刻看到新顺序 (不等 API)
    queryClient.setQueryData<TaskPublic[]>(["tasks"], (old) => {
      if (!old) return old;
      const map = new Map(newUndone.map((t, i) => [t.id, i]));
      // 重写未完成任务 sort_order 让前端 sort 命中新顺序
      return old.map((t) =>
        !t.done && map.has(t.id) ? { ...t, sort_order: map.get(t.id)! } : t,
      );
    });
    reorderMutation.mutate(newUndone.map((t) => t.id));
  };

  const onSubmitNew = (e: React.FormEvent) => {
    e.preventDefault();
    const title = newTitle.trim();
    if (!title) return;
    createMutation.mutate(title);
  };

  if (!user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> 加载中…
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-6 pb-24 pt-20 md:pt-10">
      {/* 渐变 hero */}
      <header className="relative mb-8 overflow-hidden rounded-3xl border border-white/40 bg-gradient-to-br from-emerald-500/90 via-teal-500/90 to-cyan-500/90 p-6 text-white shadow-lg dark:border-white/10">
        <div className="pointer-events-none absolute -right-10 -top-12 size-44 rounded-full bg-white/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-12 left-1/3 size-40 rounded-full bg-cyan-300/30 blur-3xl" />
        <div className="relative">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-0.5 text-xs font-medium backdrop-blur">
            <Sparkles className="size-3" />
            Phase 3.2.b · 优先级 + 截止
          </div>
          <h1 className="text-2xl font-bold">任务</h1>
          <p className="mt-1 text-sm text-white/85">
            {viewCounts.all === 0
              ? "全部完成 ✨"
              : `${viewCounts.all} 个待办${viewCounts.overdue > 0 ? ` · ${viewCounts.overdue} 过期` : ""}${viewCounts.today > 0 ? ` · ${viewCounts.today} 今天` : ""}`}
          </p>
        </div>
      </header>

      {/* 新增 input */}
      <form
        onSubmit={onSubmitNew}
        className="mb-4 flex items-center gap-2 rounded-2xl border border-border bg-card/80 px-3 py-2 shadow-sm backdrop-blur"
      >
        <Plus className="size-4 shrink-0 text-emerald-500" />
        <input
          type="text"
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="加新任务，回车保存"
          maxLength={200}
          autoFocus
          className="flex-1 bg-transparent text-sm placeholder:text-muted-foreground focus:outline-none"
        />
        <Button
          type="submit"
          size="sm"
          disabled={!newTitle.trim() || createMutation.isPending}
          className="bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-sm hover:brightness-110"
        >
          {createMutation.isPending ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            "添加"
          )}
        </Button>
      </form>

      {/* 视图 tab */}
      <ViewTabs view={view} setView={setView} counts={viewCounts} />

      {/* 列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
          <Loader2 className="mr-2 size-4 animate-spin" /> 加载中…
        </div>
      ) : !tasks || tasks.length === 0 ? (
        <EmptyState />
      ) : undone.length === 0 && done.length === 0 ? (
        <EmptyView view={view} />
      ) : (
        <div className="space-y-5">
          {undone.length > 0 && (
            <section>
              <p className="mb-2 flex items-center gap-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                待办 · {undone.length}
                {view === "all" && undone.length > 1 && (
                  <span className="font-normal normal-case tracking-normal">
                    （拖动排序）
                  </span>
                )}
              </p>
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={onDragEnd}
              >
                <SortableContext
                  items={undone.map((t) => t.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <ul className="overflow-hidden rounded-2xl border border-border bg-card/80 shadow-sm backdrop-blur">
                    {undone.map((task) => (
                      <SortableTaskRow
                        key={task.id}
                        task={task}
                        draggable={view === "all"}
                        collapsed={collapsedParents.has(task.id)}
                        onToggleCollapse={() =>
                          setCollapsedParents((prev) => {
                            const next = new Set(prev);
                            if (next.has(task.id)) next.delete(task.id);
                            else next.add(task.id);
                            return next;
                          })
                        }
                        onAddSub={() => {
                          setCollapsedParents((prev) => {
                            const next = new Set(prev);
                            next.delete(task.id);
                            return next;
                          });
                          setAddingSubFor(task.id);
                        }}
                        onToggle={() => toggleMutation.mutate({ id: task.id, done: true })}
                        onCyclePriority={() =>
                          priorityMutation.mutate({
                            id: task.id,
                            priority: PRIORITY_CYCLE[task.priority],
                          })
                        }
                        onChangeDue={(d) => dueMutation.mutate({ id: task.id, due_date: d })}
                        onDelete={() => deleteMutation.mutate(task.id)}
                      >
                        {/* 子任务区域 */}
                        {(task.children.length > 0 || addingSubFor === task.id) &&
                          !collapsedParents.has(task.id) && (
                            <div className="border-t border-border/40 bg-card/30">
                              {task.children.map((sub) => (
                                <div
                                  key={sub.id}
                                  className="border-b border-border/30 pl-12 last:border-b-0"
                                >
                                  <TaskRow
                                    task={sub}
                                    onToggle={() =>
                                      toggleMutation.mutate({
                                        id: sub.id,
                                        done: !sub.done,
                                      })
                                    }
                                    onCyclePriority={() =>
                                      priorityMutation.mutate({
                                        id: sub.id,
                                        priority: PRIORITY_CYCLE[sub.priority],
                                      })
                                    }
                                    onChangeDue={(d) =>
                                      dueMutation.mutate({
                                        id: sub.id,
                                        due_date: d,
                                      })
                                    }
                                    onDelete={() => deleteMutation.mutate(sub.id)}
                                  />
                                </div>
                              ))}
                              {addingSubFor === task.id && (
                                <SubAddInput
                                  pending={createSubMutation.isPending}
                                  onSubmit={(title) =>
                                    createSubMutation.mutate(
                                      { title, parent_id: task.id },
                                      { onSuccess: () => setAddingSubFor(null) },
                                    )
                                  }
                                  onCancel={() => setAddingSubFor(null)}
                                />
                              )}
                            </div>
                          )}
                      </SortableTaskRow>
                    ))}
                  </ul>
                </SortableContext>
              </DndContext>
            </section>
          )}

          {done.length > 0 && (
            <section>
              <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                已完成 · {done.length}
              </p>
              <ul className="overflow-hidden rounded-2xl border border-border bg-card/40 shadow-sm backdrop-blur">
                <AnimatePresence initial={false}>
                  {done.map((task) => (
                    <motion.li
                      key={task.id}
                      layout
                      initial={{ opacity: 0, x: 8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -24, height: 0, transition: { duration: 0.18 } }}
                      transition={{ duration: 0.22 }}
                      className="border-b border-border/50 last:border-b-0"
                    >
                      <TaskRow
                        task={task}
                        onToggle={() => toggleMutation.mutate({ id: task.id, done: false })}
                        onCyclePriority={() =>
                          priorityMutation.mutate({
                            id: task.id,
                            priority: PRIORITY_CYCLE[task.priority],
                          })
                        }
                        onChangeDue={(d) => dueMutation.mutate({ id: task.id, due_date: d })}
                        onDelete={() => deleteMutation.mutate(task.id)}
                      />
                      {/* 子任务区域 (已完成父任务仍显示子任务列表, 不显示添加 input) */}
                      {task.children.length > 0 && (
                        <div className="border-t border-border/40 bg-card/30">
                          {task.children.map((sub) => (
                            <div
                              key={sub.id}
                              className="border-b border-border/30 pl-12 last:border-b-0"
                            >
                              <TaskRow
                                task={sub}
                                onToggle={() =>
                                  toggleMutation.mutate({
                                    id: sub.id,
                                    done: !sub.done,
                                  })
                                }
                                onCyclePriority={() =>
                                  priorityMutation.mutate({
                                    id: sub.id,
                                    priority: PRIORITY_CYCLE[sub.priority],
                                  })
                                }
                                onChangeDue={(d) =>
                                  dueMutation.mutate({ id: sub.id, due_date: d })
                                }
                                onDelete={() => deleteMutation.mutate(sub.id)}
                              />
                            </div>
                          ))}
                        </div>
                      )}
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            </section>
          )}
        </div>
      )}
    </main>
  );
}

/* ─── ViewTabs ─── */

function ViewTabs({
  view,
  setView,
  counts,
}: {
  view: View;
  setView: (v: View) => void;
  counts: Record<View, number>;
}) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto rounded-xl border border-border bg-card/50 p-1 backdrop-blur">
      {VIEWS.map((t) => {
        const active = view === t.key;
        const count = counts[t.key];
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => setView(t.key)}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
              active
                ? "bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-sm shadow-teal-500/30"
                : "text-muted-foreground hover:bg-accent",
            )}
          >
            {t.label}
            {count > 0 && (
              <span
                className={cn(
                  "rounded-full px-1.5 text-[10px] font-mono",
                  active ? "bg-white/25" : "bg-zinc-100 text-zinc-500 dark:bg-white/[0.06] dark:text-zinc-400",
                )}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ─── TaskRow + SortableTaskRow ─── */

interface TaskRowProps {
  task: TaskPublic;
  onToggle: () => void;
  onCyclePriority: () => void;
  onChangeDue: (d: string | null) => void;
  onDelete: () => void;
  dragHandle?: React.ReactNode;
  dragging?: boolean;
  extraRight?: React.ReactNode;
}

function TaskRow({
  task,
  onToggle,
  onCyclePriority,
  onChangeDue,
  onDelete,
  dragHandle,
  dragging,
  extraRight,
}: TaskRowProps) {
  return (
    <div
      className={cn(
        "group flex items-center gap-2 px-4 py-3 transition-colors hover:bg-accent/30",
        dragging && "bg-accent/40 shadow-lg ring-1 ring-emerald-500/20",
      )}
    >
      {dragHandle}
      <button
        type="button"
        onClick={onToggle}
        aria-label={task.done ? "标为未完成" : "标为完成"}
        className="shrink-0"
      >
        {task.done ? (
          <CheckCircle2 className="size-5 text-emerald-500 transition-transform hover:scale-110" />
        ) : (
          <Circle className="size-5 text-muted-foreground transition-colors hover:text-emerald-500" />
        )}
      </button>
      <span
        className={cn(
          "min-w-0 flex-1 truncate text-sm transition-all",
          task.done && "text-muted-foreground line-through opacity-60",
        )}
      >
        {task.title}
      </span>
      {!task.done && <DueChip due={task.due_date} onChange={onChangeDue} />}
      {!task.done && (
        <PriorityDot priority={task.priority} onCycle={onCyclePriority} />
      )}
      {extraRight}
      <button
        type="button"
        onClick={onDelete}
        aria-label="删除任务"
        className="rounded-md p-1 text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
      >
        <Trash2 className="size-4" />
      </button>
    </div>
  );
}

function SortableTaskRow({
  task,
  draggable,
  collapsed,
  onToggleCollapse,
  onAddSub,
  children: subRows,
  ...rest
}: TaskRowProps & {
  task: TaskWithChildren;
  draggable: boolean;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onAddSub: () => void;
  children?: React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: task.id, disabled: !draggable });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  const handle = draggable ? (
    <button
      type="button"
      {...attributes}
      {...listeners}
      aria-label="拖动排序"
      className="cursor-grab touch-none rounded p-1 text-muted-foreground/50 opacity-0 transition-all hover:text-foreground group-hover:opacity-100 active:cursor-grabbing"
    >
      <GripVertical className="size-4" />
    </button>
  ) : null;
  return (
    <li
      ref={setNodeRef}
      style={style}
      className={cn(
        "border-b border-border/50 last:border-b-0",
        isDragging && "z-10",
      )}
    >
      <TaskRow
        {...rest}
        task={task}
        dragHandle={handle}
        dragging={isDragging}
        extraRight={
          !task.done ? (
            <SubtaskControls
              childCount={task.children.length}
              collapsed={collapsed}
              onToggleCollapse={onToggleCollapse}
              onAddSub={onAddSub}
            />
          ) : null
        }
      />
      {subRows}
    </li>
  );
}

function SubtaskControls({
  childCount,
  collapsed,
  onToggleCollapse,
  onAddSub,
}: {
  childCount: number;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onAddSub: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center">
      {childCount > 0 && (
        <button
          type="button"
          onClick={onToggleCollapse}
          aria-label={collapsed ? "展开子任务" : "折叠子任务"}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          {collapsed ? <ChevronRight className="size-3" /> : <ChevronDown className="size-3" />}
          <span className="font-mono tabular-nums">{childCount}</span>
        </button>
      )}
      <button
        type="button"
        onClick={onAddSub}
        aria-label="加子任务"
        className="rounded-md p-1 text-muted-foreground opacity-0 transition-all hover:bg-accent hover:text-emerald-500 group-hover:opacity-100"
      >
        <Plus className="size-3.5" />
      </button>
    </div>
  );
}

function SubAddInput({
  pending,
  onSubmit,
  onCancel,
}: {
  pending: boolean;
  onSubmit: (title: string) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const t = title.trim();
        if (!t) {
          onCancel();
          return;
        }
        onSubmit(t);
        setTitle("");
      }}
      className="flex items-center gap-2 border-b border-border/30 pl-12 pr-4 py-2.5 last:border-b-0"
    >
      <Plus className="size-3.5 shrink-0 text-emerald-500" />
      <input
        ref={ref}
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onCancel();
        }}
        onBlur={() => {
          if (!title.trim()) onCancel();
        }}
        placeholder="加子任务，回车保存 (Esc 取消)"
        maxLength={200}
        disabled={pending}
        className="flex-1 bg-transparent text-sm placeholder:text-muted-foreground/60 focus:outline-none disabled:opacity-50"
      />
      {pending && <Loader2 className="size-3.5 animate-spin text-muted-foreground" />}
    </form>
  );
}

/* ─── PriorityDot ─── */

function PriorityDot({
  priority,
  onCycle,
}: {
  priority: Priority;
  onCycle: () => void;
}) {
  const meta: Record<Priority, { label: string; color: string; bg: string }> = {
    high: {
      label: "高",
      color: "text-rose-600 dark:text-rose-400",
      bg: "bg-rose-500",
    },
    normal: {
      label: "中",
      color: "text-zinc-400",
      bg: "bg-zinc-300 dark:bg-zinc-600",
    },
    low: {
      label: "低",
      color: "text-zinc-300",
      bg: "bg-zinc-200 dark:bg-zinc-700",
    },
  };
  const m = meta[priority];
  return (
    <button
      type="button"
      onClick={onCycle}
      title={`优先级 ${m.label} · 点击循环`}
      aria-label={`优先级 ${m.label}`}
      className="inline-flex shrink-0 items-center gap-1 rounded-md p-1 transition-colors hover:bg-accent"
    >
      {priority === "high" ? (
        <Flag className={cn("size-3.5 fill-current", m.color)} />
      ) : (
        <span className={cn("size-2.5 rounded-full", m.bg)} />
      )}
    </button>
  );
}

/* ─── DueChip ─── */

function DueChip({
  due,
  onChange,
}: {
  due: string | null;
  onChange: (d: string | null) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const bucket = dueBucket(due);
  const overdue = bucket === "overdue";
  const today = bucket === "today";

  const onClickChip = () => {
    const el = inputRef.current;
    if (!el) return;
    try {
      if (typeof el.showPicker === "function") {
        el.showPicker();
        return;
      }
    } catch {
      // 浏览器不支持 / iframe 限制 → fallback click
    }
    el.click();
  };

  return (
    <div className="relative inline-flex shrink-0 items-center">
      {due ? (
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors",
            overdue
              ? "bg-rose-500/10 text-rose-600 dark:bg-rose-400/15 dark:text-rose-300"
              : today
                ? "bg-amber-500/10 text-amber-700 dark:bg-amber-400/15 dark:text-amber-300"
                : "bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/15 dark:text-emerald-300",
          )}
        >
          <button
            type="button"
            onClick={onClickChip}
            className="inline-flex items-center gap-1"
            aria-label="改截止日期"
          >
            <CalendarClock className="size-3" />
            {formatDueLabel(due)}
          </button>
          <button
            type="button"
            onClick={() => onChange(null)}
            aria-label="清除截止日期"
            className="ml-0.5 -mr-0.5 rounded-full p-0.5 transition-colors hover:bg-black/10 dark:hover:bg-white/10"
          >
            <X className="size-2.5" />
          </button>
        </span>
      ) : (
        <button
          type="button"
          onClick={onClickChip}
          aria-label="加截止日期"
          className="rounded-md p-1 text-muted-foreground opacity-0 transition-all hover:bg-accent hover:text-foreground group-hover:opacity-100"
        >
          <Calendar className="size-3.5" />
        </button>
      )}
      <input
        ref={inputRef}
        type="date"
        value={due ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="pointer-events-none absolute inset-0 -z-10 opacity-0"
        tabIndex={-1}
        aria-hidden
      />
    </div>
  );
}

/* ─── 空状态 ─── */

function EmptyState() {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-dashed border-border bg-gradient-to-br from-emerald-50 via-white to-cyan-50 py-20 text-center dark:from-emerald-950/30 dark:via-zinc-900/40 dark:to-cyan-950/30">
      <div className="pointer-events-none absolute left-1/2 top-1/2 size-72 -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-400/10 blur-3xl" />
      <div className="relative">
        <div className="mx-auto mb-4 inline-flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-500 text-white shadow-lg shadow-teal-500/30">
          <CheckCircle2 className="size-7" />
        </div>
        <h2 className="text-lg font-semibold">还没有任务</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          从上面添加第一个，让今天有点章法。
        </p>
      </div>
    </div>
  );
}

function EmptyView({ view }: { view: View }) {
  const labels: Record<View, string> = {
    all: "暂无任务",
    today: "今天没有截止的任务",
    week: "本周没有截止的任务",
    overdue: "没有过期任务 ✨",
  };
  return (
    <div className="rounded-2xl border border-dashed border-border py-12 text-center text-sm text-muted-foreground">
      {labels[view]}
    </div>
  );
}
