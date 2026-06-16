"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bookmark,
  ExternalLink,
  Globe,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import { createLink, deleteLink, listLinks, type LinkPublic } from "@/lib/links";

function formatRelative(iso: string): string {
  const now = Date.now();
  const t = new Date(iso).getTime();
  const min = Math.floor((now - t) / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min} 分钟前`;
  if (min < 1440) return `${Math.floor(min / 60)} 小时前`;
  const d = Math.floor(min / 1440);
  if (d < 30) return `${d} 天前`;
  const dd = new Date(iso);
  return `${dd.getFullYear()}-${String(dd.getMonth() + 1).padStart(2, "0")}-${String(dd.getDate()).padStart(2, "0")}`;
}

function hostFromUrl(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

function normalizeUrl(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

export default function LinksPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, loading, mounted } = useAuthUser();

  useEffect(() => {
    if (mounted && !loading && !user) router.replace("/login");
  }, [mounted, loading, user, router]);

  const { data: links, isLoading } = useQuery<LinkPublic[]>({
    queryKey: ["links"],
    queryFn: listLinks,
    enabled: !!user,
    staleTime: 10 * 1000,
  });

  const [url, setUrl] = useState("");
  const [error, setError] = useState("");

  const createMutation = useMutation({
    mutationFn: (raw: string) => createLink(normalizeUrl(raw)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["links"] });
      setUrl("");
      setError("");
    },
    onError: (err) =>
      setError(err instanceof Error ? err.message : "保存失败"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLink,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["links"] }),
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const normalized = normalizeUrl(url);
    if (!normalized) return;
    createMutation.mutate(normalized);
  };

  if (!user) {
    return (
      <main className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> 加载中…
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 pb-24 pt-20 md:pt-10">
      {/* 渐变 hero */}
      <header className="relative mb-8 overflow-hidden rounded-3xl border border-white/40 bg-gradient-to-br from-amber-500/90 via-orange-500/90 to-rose-500/90 p-6 text-white shadow-lg dark:border-white/10">
        <div className="pointer-events-none absolute -right-10 -top-12 size-44 rounded-full bg-white/15 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-12 left-1/3 size-40 rounded-full bg-rose-300/30 blur-3xl" />
        <div className="relative">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-0.5 text-xs font-medium backdrop-blur">
            <Sparkles className="size-3" />
            Phase 3.3 · 收藏
          </div>
          <h1 className="text-2xl font-bold">收藏</h1>
          <p className="mt-1 text-sm text-white/85">
            把好链接留下来。粘 URL 自动抓标题 / 描述 / 封面。
          </p>
        </div>
      </header>

      {/* 新增 input */}
      <form
        onSubmit={onSubmit}
        className="mb-6 rounded-2xl border border-border bg-card/80 px-3 py-2 shadow-sm backdrop-blur"
      >
        <div className="flex items-center gap-2">
          <Globe className="size-4 shrink-0 text-amber-500" />
          <input
            type="text"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (error) setError("");
            }}
            placeholder="粘 URL，回车保存…"
            maxLength={2048}
            autoFocus
            className="flex-1 bg-transparent text-sm placeholder:text-muted-foreground focus:outline-none"
          />
          <Button
            type="submit"
            size="sm"
            disabled={!url.trim() || createMutation.isPending}
            className="bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-sm hover:brightness-110"
          >
            {createMutation.isPending ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Plus className="size-3.5" />
            )}
            收藏
          </Button>
        </div>
        {error && (
          <p className="mt-2 px-1 text-xs text-destructive">{error}</p>
        )}
      </form>

      {/* 列表 */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
          <Loader2 className="mr-2 size-4 animate-spin" /> 加载中…
        </div>
      ) : !links || links.length === 0 ? (
        <EmptyState />
      ) : (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <AnimatePresence initial={false}>
            {links.map((link) => (
              <motion.li
                key={link.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.18 } }}
                transition={{ duration: 0.22 }}
              >
                <LinkCard
                  link={link}
                  onDelete={() => deleteMutation.mutate(link.id)}
                />
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </main>
  );
}

function LinkCard({
  link,
  onDelete,
}: {
  link: LinkPublic;
  onDelete: () => void;
}) {
  return (
    <article className="group relative flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card/80 shadow-sm backdrop-blur transition-all hover:-translate-y-0.5 hover:border-amber-300/60 hover:shadow-md dark:hover:border-amber-500/40">
      {/* OG image 顶图 (有就显示) */}
      {link.image_url ? (
        <a
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="relative block aspect-video w-full overflow-hidden bg-muted"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={link.image_url}
            alt=""
            referrerPolicy="no-referrer"
            loading="lazy"
            className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            onError={(e) => {
              // 失败的图片淡出避免破图标
              (e.currentTarget as HTMLImageElement).style.display = "none";
            }}
          />
        </a>
      ) : (
        <a
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="relative flex aspect-video w-full items-center justify-center bg-gradient-to-br from-amber-500/10 via-orange-500/10 to-rose-500/10"
        >
          <Globe className="size-10 text-amber-500/40" />
        </a>
      )}

      {/* 卡片正文 */}
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start gap-2">
          {link.favicon_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={link.favicon_url}
              alt=""
              referrerPolicy="no-referrer"
              className="mt-0.5 size-4 shrink-0 rounded-sm"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          ) : (
            <Globe className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          )}
          <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="line-clamp-2 flex-1 text-sm font-semibold leading-snug hover:underline"
          >
            {link.title}
          </a>
        </div>
        {link.description && (
          <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {link.description}
          </p>
        )}
        <div className="mt-auto flex items-center justify-between gap-2 pt-1 text-[10px] text-muted-foreground">
          <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex min-w-0 items-center gap-1 truncate transition-colors hover:text-amber-600 dark:hover:text-amber-400"
          >
            <span className="truncate">{hostFromUrl(link.url)}</span>
            <ExternalLink className="size-2.5 shrink-0" />
          </a>
          <span className="shrink-0">{formatRelative(link.created_at)}</span>
        </div>
      </div>

      {/* 删除按钮 (右上角 hover) */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          if (!confirm("确定删除这条收藏？")) return;
          onDelete();
        }}
        aria-label="删除收藏"
        className="absolute right-2 top-2 z-10 rounded-md bg-black/30 p-1.5 text-white opacity-0 backdrop-blur-sm transition-all hover:bg-destructive group-hover:opacity-100"
      >
        <Trash2 className="size-3.5" />
      </button>
    </article>
  );
}

function EmptyState() {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-dashed border-border bg-gradient-to-br from-amber-50 via-white to-rose-50 py-20 text-center dark:from-amber-950/30 dark:via-zinc-900/40 dark:to-rose-950/30">
      <div className="pointer-events-none absolute left-1/2 top-1/2 size-72 -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-400/10 blur-3xl" />
      <div className="relative">
        <div className="mx-auto mb-4 inline-flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-500 to-rose-500 text-white shadow-lg shadow-rose-500/30">
          <Bookmark className="size-7" />
        </div>
        <h2 className="text-lg font-semibold">还没有收藏</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          看到值得回头的链接 → 粘上面框里 → 自动抓元数据。
        </p>
      </div>
    </div>
  );
}
