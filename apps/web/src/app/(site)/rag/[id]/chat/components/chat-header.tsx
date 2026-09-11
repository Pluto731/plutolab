'use client'

import { ArrowLeft, BookOpen, Menu, Sparkles } from 'lucide-react'
import Link from 'next/link'
import React from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { ConversationPublic, ConversationSummary, KnowledgeBasePublic } from '@/lib/rag'

interface ChatHeaderProps {
  kb: KnowledgeBasePublic
  conversation?: ConversationSummary | ConversationPublic | null
  onOpenMobileSidebar?: () => void
}

export function ChatHeader({ kb, conversation, onOpenMobileSidebar }: ChatHeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/80 bg-background/80 px-4 backdrop-blur-xl">
      {/* Left: Mobile hamburger & title */}
      <div className="flex items-center gap-3 min-w-0">
        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenMobileSidebar}
          className="size-8 text-muted-foreground md:hidden"
        >
          <Menu className="size-4.5" />
        </Button>

        <div className="flex items-center gap-2 min-w-0">
          <span className="truncate text-sm font-semibold text-foreground">
            {conversation ? conversation.title : '开始新会话'}
          </span>

          <Badge variant="outline" className="hidden font-mono text-[10px] sm:inline-flex">
            <Sparkles className="size-2.5 mr-1 text-primary" />
            混合检索
          </Badge>
        </div>
      </div>

      {/* Right: KB Info & Back link */}
      <div className="flex items-center gap-2.5">
        <div className="hidden items-center gap-1.5 text-xs text-muted-foreground lg:flex">
          <BookOpen className="size-3" />
          <span>{kb.title}</span>
          <span>
            ({kb.doc_count} 篇文档 / {kb.chunk_count} 切片)
          </span>
        </div>

        <Link href={`/rag/${kb.id}`}>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-3.5 mr-1" />
            <span>详情</span>
          </Button>
        </Link>
      </div>
    </header>
  )
}
