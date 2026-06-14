"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Loader2, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import { deleteNote, getNote, type NotePublic, updateNote } from "@/lib/notes";

type SaveState = "idle" | "saving" | "saved" | "error";

export default function NoteEditorPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, loading, mounted } = useAuthUser();

  useEffect(() => {
    if (mounted && !loading && !user) router.replace("/login");
  }, [mounted, loading, user, router]);

  const { data: note, isLoading, error } = useQuery<NotePublic>({
    queryKey: ["note", id],
    queryFn: () => getNote(id),
    enabled: !!user,
    retry: false,
  });

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (note && !hydrated) {
      setTitle(note.title);
      setContent(note.content);
      setHydrated(true);
    }
  }, [note, hydrated]);

  const saveMutation = useMutation({
    mutationFn: (body: { title: string; content: string }) => updateNote(id, body),
    onMutate: () => setSaveState("saving"),
    onSuccess: () => {
      setSaveState("saved");
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      // 2s 后回到 idle
      setTimeout(() => setSaveState((s) => (s === "saved" ? "idle" : s)), 2000);
    },
    onError: (err) => {
      setSaveState("error");
      setErrorMsg(err instanceof Error ? err.message : "保存失败");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteNote(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      router.push("/notes");
    },
  });

  const onSave = () => {
    if (!hydrated) return;
    const trimmed = title.trim() || "无标题笔记";
    if (trimmed !== title) setTitle(trimmed);
    saveMutation.mutate({ title: trimmed, content });
  };

  // ⌘S / Ctrl+S 保存
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        onSave();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, content, hydrated]);

  if (!user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> 加载中…
      </main>
    );
  }

  if (isLoading) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> 加载笔记…
      </main>
    );
  }

  if (error || !note) {
    return (
      <main className="mx-auto max-w-2xl px-6 pb-24 pt-20 text-center md:pt-10">
        <h1 className="text-xl font-semibold">笔记不存在</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          它可能已被删除，或属于其他账号。
        </p>
        <Button
          type="button"
          variant="outline"
          className="mt-6"
          onClick={() => router.push("/notes")}
        >
          <ArrowLeft className="size-4" />
          返回笔记列表
        </Button>
      </main>
    );
  }

  const onDelete = () => {
    if (!confirm(`确定删除「${title || "无标题笔记"}」？删除后不可恢复。`)) return;
    deleteMutation.mutate();
  };

  return (
    <main className="mx-auto max-w-3xl px-6 pb-24 pt-20 md:pt-10">
      {/* 工具栏 */}
      <div className="sticky top-16 z-10 -mx-2 mb-6 flex items-center justify-between gap-3 rounded-2xl border border-white/40 bg-white/70 px-4 py-2.5 backdrop-blur-xl md:top-4 dark:border-white/10 dark:bg-black/40">
        <button
          type="button"
          onClick={() => router.push("/notes")}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          全部笔记
        </button>
        <div className="flex items-center gap-3">
          <SaveBadge state={saveState} message={errorMsg} />
          <Button type="button" size="sm" onClick={onSave} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? "保存中…" : "保存"}
          </Button>
          <button
            type="button"
            onClick={onDelete}
            disabled={deleteMutation.isPending}
            className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
            aria-label="删除"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>

      {/* 标题 — Lora 衬线字, 读书感 */}
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={200}
        placeholder="无标题笔记"
        className="w-full border-0 bg-transparent font-serif text-4xl font-semibold tracking-tight placeholder:text-muted-foreground/50 focus:outline-none"
      />

      {/* 元信息 */}
      <p className="mt-2 text-xs text-muted-foreground">
        {new Date(note.updated_at).toLocaleString()}
      </p>

      {/* 正文 */}
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        maxLength={200_000}
        placeholder="想到就写。Markdown 渲染下一片做。"
        rows={24}
        className="mt-6 w-full resize-none border-0 bg-transparent font-mono text-[15px] leading-7 placeholder:text-muted-foreground/50 focus:outline-none"
      />

      <p className="mt-4 text-xs text-muted-foreground">
        提示：⌘/Ctrl + S 快速保存
      </p>
    </main>
  );
}

function SaveBadge({ state, message }: { state: SaveState; message: string }) {
  if (state === "saving")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="size-3 animate-spin" /> 保存中
      </span>
    );
  if (state === "saved")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
        <Check className="size-3" /> 已保存
      </span>
    );
  if (state === "error")
    return (
      <span className="text-xs text-destructive">{message || "保存失败"}</span>
    );
  return null;
}
