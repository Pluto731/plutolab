"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Loader2, Trash2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { use, useEffect, useRef, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import { deleteNote, getNote, type NotePublic, updateNote } from "@/lib/notes";

type SaveState = "idle" | "saving" | "saved" | "error";

// CodeMirror 用 window, 禁 SSR
const NoteEditor = dynamic(
  () => import("@/components/notes/note-editor").then((m) => m.NoteEditor),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center py-16 text-sm text-muted-foreground">
        <Loader2 className="mr-2 size-4 animate-spin" /> 编辑器加载中…
      </div>
    ),
  },
);

// 自动保存 debounce 间隔
const AUTOSAVE_DEBOUNCE_MS = 1500;

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

  const dirty =
    hydrated && note !== undefined && (title !== note.title || content !== note.content);

  const onSave = () => {
    if (!hydrated) return;
    const trimmed = title.trim() || "无标题笔记";
    if (trimmed !== title) setTitle(trimmed);
    saveMutation.mutate({ title: trimmed, content });
  };

  // 自动保存 — debounce 1.5s; 用 ref 拿最新值避免 stale closure
  const latestRef = useRef({ title, content });
  useEffect(() => {
    latestRef.current = { title, content };
  }, [title, content]);

  useEffect(() => {
    if (!dirty) return;
    const t = setTimeout(() => {
      const { title: latestTitle, content: latestContent } = latestRef.current;
      saveMutation.mutate({
        title: latestTitle.trim() || "无标题笔记",
        content: latestContent,
      });
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, content, dirty]);

  // ⌘S / Ctrl+S 立即保存
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (dirty) onSave();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dirty, title, content]);

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
    <main className="mx-auto flex h-[calc(100vh-5rem)] max-w-3xl flex-col px-6 pt-20 md:pt-10">
      {/* 工具栏 */}
      <div className="sticky top-16 z-10 -mx-2 mb-4 flex items-center justify-between gap-3 rounded-2xl border border-white/40 bg-white/70 px-4 py-2.5 backdrop-blur-xl md:top-4 dark:border-white/10 dark:bg-black/40">
        <button
          type="button"
          onClick={() => router.push("/notes")}
          className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          全部笔记
        </button>
        <div className="flex items-center gap-3">
          <SaveBadge state={saveState} message={errorMsg} dirty={dirty} />
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

      {/* 标题 — Lora 衬线字 */}
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={200}
        placeholder="无标题笔记"
        className="shrink-0 border-0 bg-transparent font-serif text-4xl font-semibold tracking-tight placeholder:text-muted-foreground/50 focus:outline-none"
      />

      {/* 元信息 */}
      <p className="mt-2 shrink-0 text-xs text-muted-foreground">
        {new Date(note.updated_at).toLocaleString()} · 改了自动保存 · ⌘/Ctrl + S 立即保存
      </p>

      {/* 正文 — CodeMirror */}
      <div className="mt-4 flex-1 overflow-hidden">
        <NoteEditor
          value={content}
          onChange={setContent}
          autoFocus
          placeholder="想到就写… # 标题 / **加粗** / *斜体* / > 引文 / `code` 都会自动美化"
        />
      </div>
    </main>
  );
}

function SaveBadge({
  state,
  message,
  dirty,
}: {
  state: SaveState;
  message: string;
  dirty: boolean;
}) {
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
  if (dirty)
    return <span className="text-xs text-muted-foreground">未保存…</span>;
  return null;
}
