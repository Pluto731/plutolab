"use client";

import { motion } from "framer-motion";
import {
  BookOpen,
  Calendar,
  ChevronRight,
  Database,
  FileText,
  Layers,
  Sparkles,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { KnowledgeBaseSummary } from "@/lib/rag";

interface KnowledgeBaseCardProps {
  kb: KnowledgeBaseSummary;
  onDelete: (id: string, title: string) => void;
  isDeleting?: boolean;
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

export function KnowledgeBaseCard({ kb, onDelete, isDeleting }: KnowledgeBaseCardProps) {
  const isEmoji = kb.icon && /\p{Extended_Pictographic}/u.test(kb.icon);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{ y: -3 }}
      transition={{ duration: 0.2 }}
      className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-zinc-200/80 bg-white/70 p-5 backdrop-blur-xl transition-shadow hover:shadow-lg dark:border-white/[0.08] dark:bg-zinc-900/60 dark:hover:border-primary/40 dark:hover:shadow-[0_10px_30px_-10px_rgba(147,51,234,0.2)]"
    >
      <div>
        {/* Top Header Row */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-xl text-primary ring-1 ring-primary/20 dark:bg-primary/20">
              {isEmoji ? kb.icon : <BookOpen className="size-5" />}
            </div>
            <div>
              <Link
                href={`/rag/${kb.id}`}
                className="group/title flex items-center gap-1.5 font-semibold text-zinc-900 transition-colors hover:text-primary dark:text-zinc-100"
              >
                <span className="line-clamp-1">{kb.title}</span>
                <ChevronRight className="size-3.5 opacity-0 transition-all group-hover/title:translate-x-0.5 group-hover/title:opacity-100" />
              </Link>
              <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                <Calendar className="size-3" />
                <span>更新于 {formatRelativeTime(kb.updated_at)}</span>
              </div>
            </div>
          </div>

          {/* Delete Action Button */}
          <Button
            variant="ghost"
            size="icon"
            disabled={isDeleting}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onDelete(kb.id, kb.title);
            }}
            title="删除知识库"
            className="size-7 text-zinc-400 opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>

        {/* Description */}
        <p className="mt-3.5 text-xs leading-relaxed text-zinc-500 line-clamp-2 dark:text-zinc-400">
          {kb.description || "暂无描述，点击进入知识库上传文档或开始提问。"}
        </p>
      </div>

      {/* Footer Metrics */}
      <div className="mt-5 space-y-3 pt-3.5 border-t border-zinc-100 dark:border-zinc-800/80">
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div className="rounded-lg bg-zinc-50/80 p-1.5 dark:bg-zinc-800/40">
            <div className="text-[10px] text-zinc-400 flex items-center justify-center gap-1">
              <FileText className="size-3" /> 文档
            </div>
            <div className="font-semibold text-zinc-800 dark:text-zinc-200">
              {kb.doc_count}
            </div>
          </div>
          <div className="rounded-lg bg-zinc-50/80 p-1.5 dark:bg-zinc-800/40">
            <div className="text-[10px] text-zinc-400 flex items-center justify-center gap-1">
              <Layers className="size-3" /> 切片
            </div>
            <div className="font-semibold text-zinc-800 dark:text-zinc-200">
              {kb.chunk_count}
            </div>
          </div>
          <div className="rounded-lg bg-zinc-50/80 p-1.5 dark:bg-zinc-800/40">
            <div className="text-[10px] text-zinc-400 flex items-center justify-center gap-1">
              <Database className="size-3" /> 字数
            </div>
            <div className="font-semibold text-zinc-800 dark:text-zinc-200">
              {formatCharCount(kb.char_count)}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <Badge variant="outline" className="text-[10px] font-mono border-zinc-200/80 dark:border-zinc-700/80 text-zinc-500 dark:text-zinc-400">
            <Sparkles className="size-2.5 mr-1 text-primary" />
            {kb.embedding_model}
          </Badge>

          <Link
            href={`/rag/${kb.id}`}
            className="text-xs font-medium text-primary hover:underline flex items-center gap-0.5"
          >
            进入知识库
            <ChevronRight className="size-3" />
          </Link>
        </div>
      </div>
    </motion.div>
  );
}
