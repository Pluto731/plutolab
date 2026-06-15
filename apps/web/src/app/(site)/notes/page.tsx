"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Calendar,
  Clock4,
  FileText,
  Hash,
  Loader2,
  Maximize2,
  Plus,
  Save,
  Search,
  Sparkles,
  Trash2,
  Wand2,
  X,
} from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";

// CodeMirror 用 window, 禁 SSR
const NoteEditor = dynamic(
  () => import("@/components/notes/note-editor").then((m) => m.NoteEditor),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center py-12 text-xs text-muted-foreground">
        <Loader2 className="mr-2 size-3 animate-spin" /> 编辑器加载中…
      </div>
    ),
  },
);

const AUTOSAVE_DEBOUNCE_MS = 1500;
import {
  createNote,
  createSampleNote,
  deleteNote,
  getNote,
  listNotes,
  listTags,
  type NotePublic,
  type NoteSummary,
  searchNotes,
  type TagWithCount,
  updateNote,
} from "@/lib/notes";
import { cn } from "@/lib/utils";

type Filter = "all" | "today" | "week";

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

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
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { user, loading, mounted } = useAuthUser();

  useEffect(() => {
    if (mounted && !loading && !user) router.replace("/login");
  }, [mounted, loading, user, router]);

  const selectedId = searchParams.get("id");

  const setSelected = (id: string | null) => {
    const sp = new URLSearchParams(Array.from(searchParams.entries()));
    if (id) sp.set("id", id);
    else sp.delete("id");
    const qs = sp.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  const [selectedTag, setSelectedTag] = useState<string | null>(null);

  // B.3: 全局搜索 + 300ms debounce
  const [searchInput, setSearchInput] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(searchInput.trim()), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const { data: notes, isLoading } = useQuery<NoteSummary[]>({
    queryKey: ["notes", { tag: selectedTag, q: debouncedQuery }],
    queryFn: () =>
      debouncedQuery
        ? searchNotes(debouncedQuery)
        : listNotes(selectedTag ?? undefined),
    enabled: !!user,
    staleTime: 10 * 1000,
  });

  const { data: tags } = useQuery<TagWithCount[]>({
    queryKey: ["note-tags"],
    queryFn: listTags,
    enabled: !!user,
    staleTime: 10 * 1000,
  });

  // 桌面端自动选中第一条 (列表非空且没选). 移动端不自动选 — 因为右栏不显示, 用户应该看到列表全貌.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.innerWidth < 768) return;
    if (notes && notes.length > 0 && !selectedId) {
      setSelected(notes[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notes]);

  const [filter, setFilter] = useState<Filter>("all");

  const filteredNotes = useMemo(() => {
    if (!notes) return [];
    const now = Date.now();
    return notes.filter((n) => {
      const t = new Date(n.updated_at).getTime();
      if (filter === "today") return t >= startOfDay(new Date(now));
      if (filter === "week") return t >= now - 7 * 86400 * 1000;
      return true;
    });
  }, [notes, filter]);

  const invalidateNotes = () => {
    queryClient.invalidateQueries({ queryKey: ["notes"] });
    queryClient.invalidateQueries({ queryKey: ["note-tags"] });
  };

  const createMutation = useMutation({
    mutationFn: () => createNote({ title: "无标题笔记", content: "" }),
    onSuccess: (note) => {
      invalidateNotes();
      setSelected(note.id);
    },
  });

  const sampleMutation = useMutation({
    mutationFn: createSampleNote,
    onSuccess: (note) => {
      invalidateNotes();
      setSelected(note.id);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteNote,
    onSuccess: () => {
      invalidateNotes();
      setSelected(null);
    },
  });

  if (!user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> 加载中…
      </main>
    );
  }

  return (
    <main className="px-3 pt-20 pb-6 md:px-6 md:pt-10">
      <div
        className="mx-auto flex w-full max-w-[1600px] gap-3 overflow-hidden rounded-2xl border border-white/40 bg-white/40 backdrop-blur-xl dark:border-white/[0.06] dark:bg-white/[0.02]"
        style={{ height: "calc(100vh - 6rem)" }}
      >
        {/* 左栏 — 时间筛选 + #hashtag 标签 (仅 xl+) */}
        <FilterColumn
          filter={filter}
          setFilter={setFilter}
          notes={notes}
          tags={tags}
          selectedTag={selectedTag}
          setSelectedTag={setSelectedTag}
          createPending={createMutation.isPending}
          onCreate={() => createMutation.mutate()}
        />

        {/* 中栏 — 列表 */}
        <NotesListColumn
          notes={filteredNotes}
          isLoading={isLoading}
          selectedId={selectedId}
          onSelect={setSelected}
          onCreate={() => createMutation.mutate()}
          createPending={createMutation.isPending}
          onLoadSample={() => sampleMutation.mutate()}
          samplePending={sampleMutation.isPending}
          searchInput={searchInput}
          setSearchInput={setSearchInput}
          isSearching={debouncedQuery.length > 0}
        />

        {/* 右栏 — 预览/编辑 (md+) */}
        <PreviewColumn
          id={selectedId}
          onDelete={(id) => deleteMutation.mutate(id)}
          onCreate={() => createMutation.mutate()}
          createPending={createMutation.isPending}
        />
      </div>
    </main>
  );
}

/* ─── 左栏 ─────────────────────────────────────────────── */

function FilterColumn({
  filter,
  setFilter,
  notes,
  tags,
  selectedTag,
  setSelectedTag,
  createPending,
  onCreate,
}: {
  filter: Filter;
  setFilter: (f: Filter) => void;
  notes: NoteSummary[] | undefined;
  tags: TagWithCount[] | undefined;
  selectedTag: string | null;
  setSelectedTag: (t: string | null) => void;
  createPending: boolean;
  onCreate: () => void;
}) {
  const counts = useMemo(() => {
    if (!notes) return { all: 0, today: 0, week: 0 };
    const now = Date.now();
    const sod = startOfDay(new Date(now));
    return {
      all: notes.length,
      today: notes.filter((n) => new Date(n.updated_at).getTime() >= sod).length,
      week: notes.filter(
        (n) => new Date(n.updated_at).getTime() >= now - 7 * 86400 * 1000,
      ).length,
    };
  }, [notes]);

  const items: { key: Filter; label: string; icon: typeof Calendar; count: number }[] = [
    { key: "all", label: "全部", icon: FileText, count: counts.all },
    { key: "today", label: "今天", icon: Sparkles, count: counts.today },
    { key: "week", label: "本周", icon: Calendar, count: counts.week },
  ];

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-white/40 bg-white/30 p-4 dark:border-white/[0.05] dark:bg-white/[0.02] xl:flex">
      <Button
        type="button"
        onClick={onCreate}
        disabled={createPending}
        className="mb-5 w-full bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-md shadow-fuchsia-500/30 hover:brightness-110"
      >
        {createPending ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
        新建笔记
      </Button>

      <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        筛选
      </p>
      <ul className="space-y-0.5">
        {items.map((it) => {
          const Icon = it.icon;
          const active = filter === it.key;
          return (
            <li key={it.key}>
              <button
                type="button"
                onClick={() => setFilter(it.key)}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-violet-500/15 text-zinc-900 ring-1 ring-violet-500/20 dark:bg-violet-400/15 dark:text-zinc-100 dark:ring-violet-400/25"
                    : "text-zinc-600 hover:bg-zinc-100/60 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-white/[0.05] dark:hover:text-zinc-100",
                )}
              >
                <Icon
                  className={cn(
                    "size-4 shrink-0",
                    active && "text-violet-600 dark:text-violet-400",
                  )}
                />
                <span className="flex-1 text-left">{it.label}</span>
                <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-mono text-zinc-500 dark:bg-white/[0.06] dark:text-zinc-400">
                  {it.count}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      {/* #hashtag 标签筛选 — B.1 */}
      <div className="mt-5 flex min-h-0 flex-1 flex-col">
        <div className="mb-2 flex items-center justify-between px-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            标签
          </p>
          {selectedTag && (
            <button
              type="button"
              onClick={() => setSelectedTag(null)}
              className="inline-flex items-center gap-0.5 text-[10px] text-violet-600 transition-colors hover:text-violet-700 dark:text-violet-400 dark:hover:text-violet-300"
            >
              <X className="size-3" />
              清除
            </button>
          )}
        </div>
        {!tags || tags.length === 0 ? (
          <p className="px-3 text-xs italic text-muted-foreground">
            在笔记里写 <span className="font-mono">#想法</span> 自动出现
          </p>
        ) : (
          <ul className="flex flex-wrap gap-1.5 overflow-y-auto px-2 pb-2">
            {tags.map((tag) => {
              const active = selectedTag === tag.name.toLowerCase();
              return (
                <li key={tag.name}>
                  <button
                    type="button"
                    onClick={() =>
                      setSelectedTag(active ? null : tag.name.toLowerCase())
                    }
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-all",
                      active
                        ? "bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-sm shadow-fuchsia-500/30"
                        : "border border-violet-500/20 bg-violet-500/5 text-violet-700 hover:bg-violet-500/15 dark:border-violet-400/25 dark:bg-violet-400/10 dark:text-violet-300 dark:hover:bg-violet-400/20",
                    )}
                  >
                    <Hash className="size-3" />
                    {tag.name}
                    <span
                      className={cn(
                        "rounded px-1 text-[10px] font-mono",
                        active
                          ? "bg-white/25"
                          : "bg-violet-500/15 dark:bg-violet-400/15",
                      )}
                    >
                      {tag.count}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}

/* ─── 中栏 ─────────────────────────────────────────────── */

function NotesListColumn({
  notes,
  isLoading,
  selectedId,
  onSelect,
  onCreate,
  createPending,
  onLoadSample,
  samplePending,
  searchInput,
  setSearchInput,
  isSearching,
}: {
  notes: NoteSummary[];
  isLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  createPending: boolean;
  onLoadSample: () => void;
  samplePending: boolean;
  searchInput: string;
  setSearchInput: (v: string) => void;
  isSearching: boolean;
}) {
  return (
    <section className="flex w-full shrink-0 flex-col md:w-[22rem] md:border-r md:border-white/40 dark:md:border-white/[0.05]">
      {/* 列表头 — 标题 + 计数 + (移动端) 新建按钮 */}
      <div className="flex items-center justify-between gap-2 border-b border-white/30 px-4 py-3 dark:border-white/[0.06]">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold">
            {isSearching ? "搜索结果" : "笔记"}
          </h2>
          <p className="text-xs text-muted-foreground">
            {isSearching ? `找到 ${notes.length} 条` : `${notes.length} 条`}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          onClick={onCreate}
          disabled={createPending}
          className="bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-sm shadow-fuchsia-500/30 hover:brightness-110 xl:hidden"
        >
          {createPending ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
          新建
        </Button>
      </div>

      {/* B.3: 全局搜索框 */}
      <div className="border-b border-white/30 px-3 py-2 dark:border-white/[0.06]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="搜索标题或正文…"
            className="h-9 w-full rounded-lg border border-white/40 bg-white/40 pl-8 pr-8 text-sm placeholder:text-muted-foreground focus:border-violet-500/40 focus:bg-white/70 focus:outline-none focus:ring-2 focus:ring-violet-500/15 dark:border-white/[0.08] dark:bg-white/[0.03] dark:focus:bg-white/[0.06]"
          />
          {searchInput && (
            <button
              type="button"
              onClick={() => setSearchInput("")}
              aria-label="清除搜索"
              className="absolute right-1.5 top-1/2 inline-flex size-6 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-zinc-100/60 hover:text-foreground dark:hover:bg-white/[0.06]"
            >
              <X className="size-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" /> 加载中…
          </div>
        ) : notes.length === 0 ? (
          <EmptyListState
            onCreate={onCreate}
            pending={createPending}
            onLoadSample={onLoadSample}
            samplePending={samplePending}
          />
        ) : (
          <ul className="divide-y divide-white/30 dark:divide-white/[0.04]">
            <AnimatePresence initial={false}>
              {notes.map((n) => {
                const active = selectedId === n.id;
                return (
                  <motion.li
                    key={n.id}
                    layout
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{
                      opacity: 0,
                      x: 30,
                      height: 0,
                      transition: { duration: 0.2, ease: [0.4, 0, 0.2, 1] },
                    }}
                    transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                  >
                    <ListItem note={n} active={active} onSelect={onSelect} />
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ul>
        )}
      </div>
    </section>
  );
}

function ListItem({
  note,
  active,
  onSelect,
}: {
  note: NoteSummary;
  active: boolean;
  onSelect: (id: string) => void;
}) {
  // 移动端 < md 点击直接跳全屏编辑, 桌面端选中预览
  return (
    <>
      {/* 桌面 — 选中预览 */}
      <button
        type="button"
        onClick={() => onSelect(note.id)}
        className={cn(
          "group hidden w-full flex-col items-start gap-1.5 px-4 py-3 text-left transition-colors md:flex",
          active
            ? "bg-gradient-to-r from-violet-500/15 to-fuchsia-500/10 ring-1 ring-inset ring-violet-500/20 dark:from-violet-400/15 dark:to-fuchsia-400/10 dark:ring-violet-400/25"
            : "hover:bg-white/40 dark:hover:bg-white/[0.03]",
        )}
      >
        <div className="flex w-full items-start justify-between gap-2">
          <h3 className="line-clamp-1 flex-1 font-semibold">{note.title}</h3>
          <span className="shrink-0 text-[10px] font-mono text-muted-foreground">
            {formatRelative(note.updated_at)}
          </span>
        </div>
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {note.excerpt || <span className="italic">（空笔记）</span>}
        </p>
      </button>

      {/* 移动 — 跳全屏编辑 */}
      <Link
        href={`/notes/${note.id}`}
        className="flex w-full flex-col items-start gap-1.5 px-4 py-3 text-left transition-colors hover:bg-white/40 md:hidden dark:hover:bg-white/[0.03]"
      >
        <div className="flex w-full items-start justify-between gap-2">
          <h3 className="line-clamp-1 flex-1 font-semibold">{note.title}</h3>
          <span className="shrink-0 text-[10px] font-mono text-muted-foreground">
            {formatRelative(note.updated_at)}
          </span>
        </div>
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {note.excerpt || <span className="italic">（空笔记）</span>}
        </p>
      </Link>
    </>
  );
}

function EmptyListState({
  onCreate,
  pending,
  onLoadSample,
  samplePending,
}: {
  onCreate: () => void;
  pending: boolean;
  onLoadSample: () => void;
  samplePending: boolean;
}) {
  return (
    <div className="relative overflow-hidden px-6 py-16 text-center">
      <div className="pointer-events-none absolute left-1/2 top-1/2 size-48 -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-400/10 blur-3xl" />
      <div className="relative">
        <div className="mx-auto mb-3 inline-flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-white shadow-lg shadow-fuchsia-500/30">
          <FileText className="size-6" />
        </div>
        <h3 className="text-base font-semibold">还没有笔记</h3>
        <p className="mt-1 text-xs text-muted-foreground">想到就写。第一个想法不必完美。</p>
        <div className="mt-5 flex flex-col items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={onCreate}
            disabled={pending || samplePending}
            className="bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-md shadow-fuchsia-500/30 hover:brightness-110"
          >
            {pending ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
            写第一个
          </Button>
          <button
            type="button"
            onClick={onLoadSample}
            disabled={pending || samplePending}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-violet-600 disabled:opacity-50 dark:hover:text-violet-400"
          >
            {samplePending ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <Wand2 className="size-3" />
            )}
            或载入示例笔记看长什么样
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── 右栏 ─────────────────────────────────────────────── */

function PreviewColumn({
  id,
  onDelete,
  onCreate,
  createPending,
}: {
  id: string | null;
  onDelete: (id: string) => void;
  onCreate: () => void;
  createPending: boolean;
}) {
  return (
    <section className="hidden flex-1 flex-col overflow-hidden md:flex">
      <AnimatePresence mode="wait" initial={false}>
        {id ? (
          <motion.div
            key={id}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4, transition: { duration: 0.14 } }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-1 flex-col overflow-hidden"
          >
            <PreviewBody id={id} onDelete={onDelete} />
          </motion.div>
        ) : (
          <motion.div
            key="placeholder"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.12 } }}
            transition={{ duration: 0.25 }}
            className="flex flex-1 flex-col"
          >
            <PreviewPlaceholder onCreate={onCreate} createPending={createPending} />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function PreviewBody({
  id,
  onDelete,
}: {
  id: string;
  onDelete: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const { data: note, isLoading } = useQuery<NotePublic>({
    queryKey: ["note", id],
    queryFn: () => getNote(id),
    retry: false,
  });

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [saved, setSaved] = useState<"idle" | "saving" | "saved" | "err">("idle");
  const [errMsg, setErrMsg] = useState("");

  useEffect(() => {
    if (note && !hydrated) {
      setTitle(note.title);
      setContent(note.content);
      setHydrated(true);
    }
  }, [note, hydrated]);

  const dirty = hydrated && note && (title !== note.title || content !== note.content);

  const saveMutation = useMutation({
    mutationFn: (body: { title: string; content: string }) => updateNote(id, body),
    onMutate: () => setSaved("saving"),
    onSuccess: () => {
      setSaved("saved");
      queryClient.invalidateQueries({ queryKey: ["notes"] });
      queryClient.invalidateQueries({ queryKey: ["note", id] });
      setTimeout(() => setSaved((s) => (s === "saved" ? "idle" : s)), 2000);
    },
    onError: (err) => {
      setSaved("err");
      setErrMsg(err instanceof Error ? err.message : "保存失败");
    },
  });

  // 自动保存 debounce 1.5s
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

  // ⌘S 立即保存
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (dirty) {
          saveMutation.mutate({
            title: title.trim() || "无标题笔记",
            content,
          });
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dirty, title, content]);

  if (isLoading || !note) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 size-4 animate-spin" /> 加载笔记…
      </div>
    );
  }

  const handleDelete = () => {
    if (!confirm(`确定删除「${title || "无标题笔记"}」？删除后不可恢复。`)) return;
    onDelete(id);
  };

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* 工具栏 */}
      <div className="flex items-center justify-between gap-3 border-b border-white/30 px-5 py-2.5 dark:border-white/[0.06]">
        <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
          <Clock4 className="size-3.5" />
          <span className="truncate">{new Date(note.updated_at).toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-2">
          {saved === "saving" && (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" /> 保存中
            </span>
          )}
          {saved === "saved" && (
            <span className="text-xs text-emerald-600 dark:text-emerald-400">✓ 已保存</span>
          )}
          {saved === "err" && (
            <span className="text-xs text-destructive">{errMsg || "保存失败"}</span>
          )}
          {saved === "idle" && dirty && (
            <span className="text-xs text-muted-foreground">未保存…</span>
          )}
          <Link
            href={`/notes/${id}`}
            className="inline-flex h-8 items-center gap-1 rounded-md border border-white/40 bg-white/40 px-2.5 text-xs font-medium text-zinc-700 transition-colors hover:bg-white/70 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-zinc-200 dark:hover:bg-white/[0.08]"
            aria-label="全屏编辑"
          >
            <Maximize2 className="size-3.5" />
            全屏
          </Link>
          <button
            type="button"
            onClick={handleDelete}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
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
        className="border-0 bg-transparent px-5 pt-6 font-serif text-3xl font-semibold tracking-tight placeholder:text-muted-foreground/50 focus:outline-none"
      />

      {/* 正文 — CodeMirror */}
      <div className="mt-3 flex-1 overflow-hidden px-5 pb-6">
        <NoteEditor
          value={content}
          onChange={setContent}
          placeholder="想到就写… # 标题 / **加粗** / `code` 自动美化"
        />
      </div>
    </div>
  );
}

function PreviewPlaceholder({
  onCreate,
  createPending,
}: {
  onCreate: () => void;
  createPending: boolean;
}) {
  return (
    <div className="relative flex flex-1 items-center justify-center overflow-hidden">
      <div className="pointer-events-none absolute left-1/2 top-1/2 size-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-400/10 blur-3xl" />
      <div className="relative text-center">
        <div className="mx-auto mb-4 inline-flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-white shadow-lg shadow-fuchsia-500/30">
          <FileText className="size-8" />
        </div>
        <h3 className="text-lg font-semibold">选个笔记看看</h3>
        <p className="mt-1 text-sm text-muted-foreground">从左边列表点一个，或者新写一个。</p>
        <Button
          type="button"
          onClick={onCreate}
          disabled={createPending}
          className="mt-6 bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-md shadow-fuchsia-500/30 hover:brightness-110"
        >
          {createPending ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
          新建笔记
        </Button>
      </div>
    </div>
  );
}
