"use client";

import { BookOpen, Database, FileText, Layers } from "lucide-react";
import React from "react";

import type { KnowledgeBaseSummary } from "@/lib/rag";

interface KBStatsBannerProps {
  knowledgeBases: KnowledgeBaseSummary[];
}

export function KBStatsBanner({ knowledgeBases }: KBStatsBannerProps) {
  const totalKBs = knowledgeBases.length;
  const totalDocs = knowledgeBases.reduce((acc, kb) => acc + (kb.doc_count || 0), 0);
  const totalChunks = knowledgeBases.reduce((acc, kb) => acc + (kb.chunk_count || 0), 0);
  const totalChars = knowledgeBases.reduce((acc, kb) => acc + (kb.char_count || 0), 0);

  const formattedChars =
    totalChars >= 1_000_000
      ? `${(totalChars / 1_000_000).toFixed(1)}M`
      : totalChars >= 1_000
        ? `${(totalChars / 1_000).toFixed(1)}k`
        : String(totalChars);

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div className="flex items-center gap-3 rounded-xl border border-zinc-200/60 bg-white/50 p-3.5 backdrop-blur-md dark:border-white/[0.06] dark:bg-zinc-900/40">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-blue-500/10 text-blue-500">
          <BookOpen className="size-5" />
        </div>
        <div>
          <div className="text-[11px] font-medium text-zinc-400">知识库</div>
          <div className="text-lg font-bold text-zinc-800 dark:text-zinc-100">{totalKBs}</div>
        </div>
      </div>

      <div className="flex items-center gap-3 rounded-xl border border-zinc-200/60 bg-white/50 p-3.5 backdrop-blur-md dark:border-white/[0.06] dark:bg-zinc-900/40">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-purple-500/10 text-purple-500">
          <FileText className="size-5" />
        </div>
        <div>
          <div className="text-[11px] font-medium text-zinc-400">解析文档</div>
          <div className="text-lg font-bold text-zinc-800 dark:text-zinc-100">{totalDocs}</div>
        </div>
      </div>

      <div className="flex items-center gap-3 rounded-xl border border-zinc-200/60 bg-white/50 p-3.5 backdrop-blur-md dark:border-white/[0.06] dark:bg-zinc-900/40">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-500">
          <Layers className="size-5" />
        </div>
        <div>
          <div className="text-[11px] font-medium text-zinc-400">向量切片</div>
          <div className="text-lg font-bold text-zinc-800 dark:text-zinc-100">{totalChunks}</div>
        </div>
      </div>

      <div className="flex items-center gap-3 rounded-xl border border-zinc-200/60 bg-white/50 p-3.5 backdrop-blur-md dark:border-white/[0.06] dark:bg-zinc-900/40">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-amber-500/10 text-amber-500">
          <Database className="size-5" />
        </div>
        <div>
          <div className="text-[11px] font-medium text-zinc-400">沉淀字符</div>
          <div className="text-lg font-bold text-zinc-800 dark:text-zinc-100">{formattedChars}</div>
        </div>
      </div>
    </div>
  );
}
