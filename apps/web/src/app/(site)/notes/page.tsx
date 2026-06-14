"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Plus, Sparkles, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import { createNote, deleteNote, listNotes, type NoteSummary } from "@/lib/notes";

function formatRelative(iso: string): string {
  const now = Date.now();
  const t = new Date(iso).getTime();
  const diffSec = Math.max(0, Math.floor((now - t) / 1000));
  if (diffSec < 60) return "刚刚";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} 分钟前`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} 小时前`;
  if (diffSec < 86400 * 30) return `${Math.floor(diffSec / 86400)} 天前`;
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function NotesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, loading, mounted } = useAuthUser();

  // 未登录跳 /login (沿用 settings 页范式)
  useEffect(() => {
    if (mounted && !loading && !user) router.replace("/login");
  }, [mounted, loading, user, router]);

  const { data: notes, isLoading } = useQuery<NoteSummary[]>({
    queryKey: ["notes"],
    queryFn: listNotes,
    enabled: !!user,
    staleTime: 10 * 1000,
  });

  const createMutation = useMutation({
    mutationFn: () => createNote({ title: "无标题笔记", content: "" }),
    onSuccess: (note) => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      router.push(`/notes/${note.id}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteNote,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notes"] }),
  });

  if (!user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> 加载中…
      </main>
    );
  }

  const onDelete = async (e: React.MouseEvent, id: string, title: string) => {
    e.stopPropagation();
    e.preventDefault();
    if (!confirm(`确定删除「${title}」？删除后不可恢复。`)) return;
    deleteMutation.mutate(id);
  };

  return (
    <main className="mx-auto max-w-5xl px-6 pb-24 pt-20 md:pt-10">
      {/* 头部 — 渐变胶囊 */}
      <header className="relative mb-8 overflow-hidden rounded-3xl border border-white/40 bg-gradient-to-br from-indigo-500/90 via-violet-500/90 to-fuchsia-500/90 p-6 text-white shadow-lg dark:border-white/10">
        <div className="pointer-events-none absolute -right-10 -top-12 size-44 rounded-full bg-white/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-12 left-1/3 size-40 rounded-full bg-fuchsia-300/30 blur-3xl" />
        <div className="relative flex items-end justify-between gap-4">
          <div className="min-w-0">
            <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-0.5 text-xs font-medium backdrop-blur">
              <Sparkles className="size-3" />
              Phase 3.1 · MVP
            </div>
            <h1 className="truncate text-2xl font-bold">笔记</h1>
            <p className="mt-1 text-sm text-white/85">
              想到就写。一切从这里开始。
            </p>
          </div>
          <Button
            type="button"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            className="shrink-0 bg-white text-violet-600 shadow-md hover:bg-white/90 hover:text-violet-700"
          >
            {createMutation.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Plus className="size-4" />
            )}
            新建笔记
          </Button>
        </div>
      </header>

      {/* 列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
          <Loader2 className="mr-2 size-4 animate-spin" /> 加载中…
        </div>
      ) : !notes || notes.length === 0 ? (
        <EmptyState onCreate={() => createMutation.mutate()} pending={createMutation.isPending} />
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {notes.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={() => router.push(`/notes/${n.id}`)}
                className="group relative flex h-full w-full flex-col items-start gap-3 rounded-2xl border border-border bg-card/80 p-5 text-left shadow-sm backdrop-blur transition-all hover:-translate-y-0.5 hover:border-violet-300/60 hover:shadow-md dark:hover:border-violet-500/40"
              >
                <div className="flex w-full items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-white shadow-sm">
                      <FileText className="size-4" />
                    </span>
                    <h3 className="line-clamp-1 font-semibold">{n.title}</h3>
                  </div>
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => onDelete(e, n.id, n.title)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") onDelete(e as never, n.id, n.title);
                    }}
                    className="rounded-md p-1 text-muted-foreground opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                    aria-label="删除"
                  >
                    <Trash2 className="size-4" />
                  </span>
                </div>
                <p className="line-clamp-4 text-sm text-muted-foreground">
                  {n.excerpt || <span className="italic">（空笔记）</span>}
                </p>
                <p className="mt-auto text-xs text-muted-foreground">
                  {formatRelative(n.updated_at)}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}

function EmptyState({ onCreate, pending }: { onCreate: () => void; pending: boolean }) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-dashed border-border bg-gradient-to-br from-indigo-50 via-white to-fuchsia-50 py-20 text-center dark:from-indigo-950/30 dark:via-zinc-900/40 dark:to-fuchsia-950/30">
      <div className="pointer-events-none absolute left-1/2 top-1/2 size-72 -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-400/10 blur-3xl" />
      <div className="relative">
        <div className="mx-auto mb-4 inline-flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-white shadow-lg shadow-fuchsia-500/30">
          <FileText className="size-7" />
        </div>
        <h2 className="text-lg font-semibold">还没有笔记</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          想到就写。第一个想法不必完美。
        </p>
        <Button
          type="button"
          onClick={onCreate}
          disabled={pending}
          className="mt-6 bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-md shadow-fuchsia-500/30 hover:brightness-110"
        >
          {pending ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
          写第一个笔记
        </Button>
      </div>
    </div>
  );
}
