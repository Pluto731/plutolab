"use client";

import {
  ArrowLeft,
  BookOpen,
  Calendar,
  Database,
  FileText,
  Layers,
  MessageSquare,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { KnowledgeBasePublic } from "@/lib/rag";

interface KBHeaderProps {
  kb: KnowledgeBasePublic;
  onOpenImportModal?: () => void;
}

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const t = new Date(iso).getTime();
  const min = Math.floor((now - t) / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min} 分钟前`;
  if (min < 1440) return `${Math.floor(min / 60)} 小时前`;
  const d = Math.floor(min / 1440);
  if (d < 30) return `${d} 天前`;
  const date = new Date(iso);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatCharCount(chars: number): string {
  if (chars >= 1_000_000) return `${(chars / 1_000_000).toFixed(1)}M`;
  if (chars >= 1_000) return `${(chars / 1_000).toFixed(1)}k`;
  return String(chars);
}

export function KBHeader({ kb, onOpenImportModal }: KBHeaderProps) {
  const isEmoji = kb.icon && /\p{Extended_Pictographic}/u.test(kb.icon);

  return (
    <div className="space-y-4">
      {/* Back link */}
      <div>
        <Link
          href="/rag"
          className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft className="size-3.5" />
          <span>返回知识库列表</span>
        </Link>
      </div>

      {/* Main Header Info Card */}
      <div className="rounded-2xl border border-zinc-200/80 bg-white/70 p-6 backdrop-blur-xl dark:border-white/[0.08] dark:bg-zinc-900/60 shadow-sm">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-3xl text-primary ring-1 ring-primary/20 dark:bg-primary/20">
              {isEmoji ? kb.icon : <BookOpen className="size-7" />}
            </div>
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-2.5">
                <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 sm:text-2xl">
                  {kb.title}
                </h1>
                <Badge variant="outline" className="text-[11px] font-mono border-zinc-200 dark:border-zinc-700">
                  <Sparkles className="size-3 mr-1 text-primary" />
                  {kb.embedding_model}
                </Badge>
              </div>

              <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-2xl leading-relaxed">
                {kb.description || "暂无描述信息"}
              </p>

              <div className="flex items-center gap-2 text-xs text-zinc-400 pt-1">
                <Calendar className="size-3" />
                <span>最近更新：{formatRelativeTime(kb.updated_at)}</span>
              </div>
            </div>
          </div>

          {/* Quick Metrics & Actions */}
          <div className="flex flex-wrap items-center gap-4 lg:flex-col lg:items-end">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-lg bg-zinc-100/80 px-2.5 py-1 text-xs text-zinc-600 dark:bg-zinc-800/60 dark:text-zinc-300">
                <FileText className="size-3.5 text-zinc-400" />
                <span className="font-semibold">{kb.doc_count}</span> 篇文档
              </div>
              <div className="flex items-center gap-1.5 rounded-lg bg-zinc-100/80 px-2.5 py-1 text-xs text-zinc-600 dark:bg-zinc-800/60 dark:text-zinc-300">
                <Layers className="size-3.5 text-zinc-400" />
                <span className="font-semibold">{kb.chunk_count}</span> 个切片
              </div>
              <div className="flex items-center gap-1.5 rounded-lg bg-zinc-100/80 px-2.5 py-1 text-xs text-zinc-600 dark:bg-zinc-800/60 dark:text-zinc-300">
                <Database className="size-3.5 text-zinc-400" />
                <span className="font-semibold">{formatCharCount(kb.char_count)}</span> 字
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              {onOpenImportModal && (
                <Button variant="outline" size="sm" onClick={onOpenImportModal}>
                  <BookOpen className="size-3.5 mr-1.5" />
                  导入笔记
                </Button>
              )}
              <Link href={`/rag/${kb.id}/chat`}>
                <Button size="sm" className="flex items-center gap-1.5 shadow-sm">
                  <MessageSquare className="size-3.5" />
                  <span>开始智能对话</span>
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
