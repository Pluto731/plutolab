"use client";

import { ArrowLeft, BookOpen, Menu, Sparkles } from "lucide-react";
import Link from "next/link";
import React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ConversationPublic, ConversationSummary, KnowledgeBasePublic } from "@/lib/rag";

interface ChatHeaderProps {
  kb: KnowledgeBasePublic;
  conversation?: ConversationSummary | ConversationPublic | null;
  onOpenMobileSidebar?: () => void;
}

export function ChatHeader({
  kb,
  conversation,
  onOpenMobileSidebar,
}: ChatHeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-zinc-200/80 bg-white/70 px-4 backdrop-blur-xl dark:border-white/[0.08] dark:bg-zinc-900/60">
      {/* Left: Mobile hamburger & title */}
      <div className="flex items-center gap-3 min-w-0">
        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenMobileSidebar}
          className="size-8 md:hidden text-zinc-500"
        >
          <Menu className="size-4.5" />
        </Button>

        <div className="flex items-center gap-2 min-w-0">
          <span className="font-semibold text-sm text-zinc-900 dark:text-zinc-100 truncate">
            {conversation ? conversation.title : "开始新会话"}
          </span>

          <Badge variant="outline" className="hidden sm:inline-flex text-[10px] border-zinc-200 dark:border-zinc-700 font-mono">
            <Sparkles className="size-2.5 mr-1 text-primary" />
            混合检索
          </Badge>
        </div>
      </div>

      {/* Right: KB Info & Back link */}
      <div className="flex items-center gap-2.5">
        <div className="hidden lg:flex items-center gap-1.5 text-xs text-zinc-400">
          <BookOpen className="size-3" />
          <span>{kb.title}</span>
          <span>({kb.doc_count} 篇文档 / {kb.chunk_count} 切片)</span>
        </div>

        <Link href={`/rag/${kb.id}`}>
          <Button variant="ghost" size="sm" className="h-8 text-xs text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200">
            <ArrowLeft className="size-3.5 mr-1" />
            <span>详情</span>
          </Button>
        </Link>
      </div>
    </header>
  );
}
