"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Circle, Loader2, Plus, Sparkles, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import {
  createTask,
  deleteTask,
  listTasks,
  type TaskPublic,
  updateTask,
} from "@/lib/tasks";
import { cn } from "@/lib/utils";

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

  const createMutation = useMutation({
    mutationFn: (title: string) => createTask(title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
      setNewTitle("");
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, done }: { id: string; done: boolean }) =>
      updateTask(id, { done }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
  });

  const { undone, done } = useMemo(() => {
    if (!tasks) return { undone: [], done: [] };
    return {
      undone: tasks.filter((t) => !t.done),
      done: tasks.filter((t) => t.done),
    };
  }, [tasks]);

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
      {/* 渐变 hero 头部 */}
      <header className="relative mb-8 overflow-hidden rounded-3xl border border-white/40 bg-gradient-to-br from-emerald-500/90 via-teal-500/90 to-cyan-500/90 p-6 text-white shadow-lg dark:border-white/10">
        <div className="pointer-events-none absolute -right-10 -top-12 size-44 rounded-full bg-white/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-12 left-1/3 size-40 rounded-full bg-cyan-300/30 blur-3xl" />
        <div className="relative">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-0.5 text-xs font-medium backdrop-blur">
            <Sparkles className="size-3" />
            Phase 3.2.a · MVP
          </div>
          <h1 className="text-2xl font-bold">任务</h1>
          <p className="mt-1 text-sm text-white/85">
            {undone.length === 0
              ? "全部完成 ✨"
              : `${undone.length} 个待办${done.length > 0 ? ` · 已完成 ${done.length}` : ""}`}
          </p>
        </div>
      </header>

      {/* 新增 input */}
      <form
        onSubmit={onSubmitNew}
        className="mb-6 flex items-center gap-2 rounded-2xl border border-border bg-card/80 px-3 py-2 shadow-sm backdrop-blur"
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

      {/* 列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
          <Loader2 className="mr-2 size-4 animate-spin" /> 加载中…
        </div>
      ) : !tasks || tasks.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-5">
          {/* 未完成 */}
          {undone.length > 0 && (
            <section>
              <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                待办 · {undone.length}
              </p>
              <ul className="overflow-hidden rounded-2xl border border-border bg-card/80 shadow-sm backdrop-blur">
                <AnimatePresence initial={false}>
                  {undone.map((task) => (
                    <motion.li
                      key={task.id}
                      layout
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{
                        opacity: 0,
                        x: 24,
                        height: 0,
                        transition: { duration: 0.18 },
                      }}
                      transition={{ duration: 0.22 }}
                      className="border-b border-border/50 last:border-b-0"
                    >
                      <TaskRow
                        task={task}
                        onToggle={() =>
                          toggleMutation.mutate({ id: task.id, done: true })
                        }
                        onDelete={() => deleteMutation.mutate(task.id)}
                      />
                    </motion.li>
                  ))}
                </AnimatePresence>
              </ul>
            </section>
          )}

          {/* 已完成 */}
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
                      exit={{
                        opacity: 0,
                        x: -24,
                        height: 0,
                        transition: { duration: 0.18 },
                      }}
                      transition={{ duration: 0.22 }}
                      className="border-b border-border/50 last:border-b-0"
                    >
                      <TaskRow
                        task={task}
                        onToggle={() =>
                          toggleMutation.mutate({ id: task.id, done: false })
                        }
                        onDelete={() => deleteMutation.mutate(task.id)}
                      />
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

function TaskRow({
  task,
  onToggle,
  onDelete,
}: {
  task: TaskPublic;
  onToggle: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent/30">
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
          "flex-1 text-sm transition-all",
          task.done && "text-muted-foreground line-through opacity-60",
        )}
      >
        {task.title}
      </span>
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
