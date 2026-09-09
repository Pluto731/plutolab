'use client'

import { motion, useReducedMotion } from 'framer-motion'
import Link from 'next/link'
import { BookOpen, Bot, FileText, Loader2, RefreshCw, Sparkles, User } from 'lucide-react'
import React, { useEffect, useRef } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type {
  CitationItem,
  ConversationPublic,
  KnowledgeBasePublic,
  MessagePublic,
} from '@/lib/rag'
import { MarkdownMessage } from './markdown-message'

interface ChatMessagesProps {
  kb: KnowledgeBasePublic
  conversation: ConversationPublic | null
  isLoading: boolean
  streamingMessage?: string | null
  streamingCitations?: CitationItem[]
  isStreaming?: boolean
  streamError?: string | null
  onRetry?: () => void
  onSendPresetQuery?: (query: string) => void
  onOpenCitation?: (citations: CitationItem[], index: number) => void
}

const PRESET_QUERIES = [
  '总结此知识库收录文档的核心要点与主题脉络',
  '根据知识库文档，列出关键技术决策与最佳实践',
  '梳理文档中涉及的常见问题与解决方案',
]

export function ChatMessages({
  kb,
  conversation,
  isLoading,
  streamingMessage,
  streamingCitations = [],
  isStreaming = false,
  streamError,
  onRetry,
  onSendPresetQuery,
  onOpenCitation,
}: ChatMessagesProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const followBottom = useRef(true)
  const reducedMotion = useReducedMotion()

  // Auto-scroll on content updates
  useEffect(() => {
    followBottom.current = true
  }, [conversation?.id])
  useEffect(() => {
    const container = containerRef.current
    if (container && followBottom.current) container.scrollTop = container.scrollHeight
  }, [conversation?.messages, streamingMessage, streamingCitations, isStreaming])

  if (isLoading && !conversation) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 overflow-hidden p-4 sm:p-6">
        {['w-2/3', 'w-5/6', 'w-1/2'].map((width) => (
          <div key={width} className="flex items-start gap-3">
            <Skeleton className="size-8 shrink-0 rounded-xl" />
            <div className="flex w-full max-w-xl flex-col gap-2">
              <Skeleton className={`h-4 ${width}`} />
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-16 w-full rounded-2xl" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  const messages = conversation?.messages || []

  if (messages.length === 0 && !streamingMessage && !isStreaming && !streamError) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
        <div className="max-w-md space-y-4">
          <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-3xl text-primary ring-1 ring-primary/20">
            {kb.icon || <BookOpen className="size-7" />}
          </div>

          <div className="space-y-1.5">
            <h3 className="text-lg font-bold text-foreground">与「{kb.title}」开始智能对话</h3>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {kb.chunk_count > 0
                ? `从 ${kb.doc_count} 篇文档中寻找线索，点击回答中的引用即可核对原文。`
                : '先添加文档，解析完成后即可围绕内容提问。'}
            </p>
          </div>

          {/* Preset Prompts */}
          {kb.chunk_count === 0 ? (
            <Button asChild>
              <Link href={`/rag/${kb.id}`}>添加文档</Link>
            </Button>
          ) : (
            <div className="pt-3 space-y-2">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                推荐探索问题
              </p>
              <div className="space-y-2 text-left">
                {PRESET_QUERIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => onSendPresetQuery?.(q)}
                    className="w-full rounded-xl border border-border/80 bg-card/60 p-3 text-left text-xs text-foreground transition-all hover:border-primary/40 hover:bg-primary/5 hover:text-primary"
                  >
                    <div className="flex items-center gap-2">
                      <Sparkles className="size-3.5 text-primary shrink-0" />
                      <span className="truncate">{q}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      onScroll={(event) => {
        const node = event.currentTarget
        followBottom.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80
      }}
      className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6"
    >
      {messages.map((msg: MessagePublic) => {
        const isUser = msg.role === 'user'

        return (
          <motion.div
            key={msg.id}
            initial={reducedMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex gap-3 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
          >
            {/* Avatar */}
            <div
              className={`flex size-8 shrink-0 items-center justify-center rounded-xl text-xs font-semibold ${
                isUser
                  ? 'bg-primary text-primary-foreground shadow-xs'
                  : 'bg-muted text-muted-foreground ring-1 ring-border'
              }`}
            >
              {isUser ? <User className="size-4" /> : <Bot className="size-4 text-primary" />}
            </div>

            {/* Bubble */}
            <div className="space-y-2 min-w-0 max-w-[85%] [overflow-wrap:anywhere]">
              <div
                className={`rounded-2xl px-4 py-3 text-xs sm:text-sm leading-relaxed ${
                  isUser
                    ? 'bg-primary text-primary-foreground rounded-tr-xs'
                    : 'bg-card border border-border text-card-foreground rounded-tl-xs shadow-xs'
                }`}
              >
                {isUser ? (
                  <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                ) : (
                  <MarkdownMessage
                    content={msg.content}
                    onCitationClick={(num) => {
                      if (msg.citations[num - 1]) {
                        onOpenCitation?.(msg.citations, num - 1)
                      }
                    }}
                  />
                )}
              </div>

              {/* Citations Preview */}
              {!isUser && msg.citations && msg.citations.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] text-muted-foreground">参考来源:</span>
                  {msg.citations.map((cite, idx) => (
                    <button
                      key={cite.chunk_id || idx}
                      type="button"
                      onClick={() => onOpenCitation?.(msg.citations, idx)}
                      title={cite.content}
                      className="inline-flex items-center gap-1 rounded-md border border-primary/20 bg-primary/5 px-2 py-0.5 text-[10px] text-primary hover:bg-primary/10 transition-colors"
                    >
                      <FileText className="size-2.5" />
                      <span className="truncate max-w-[130px]">{cite.filename}</span>
                      <span className="font-mono">#{cite.chunk_index}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )
      })}

      {/* Streaming Assistant Bubble */}
      {isStreaming && (
        <motion.div
          initial={reducedMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex gap-3 max-w-3xl mr-auto"
        >
          <div className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-muted text-muted-foreground ring-1 ring-border">
            <Bot className="size-4 text-primary" />
          </div>

          <div className="space-y-2 min-w-0 max-w-[85%] [overflow-wrap:anywhere]">
            <div className="rounded-2xl rounded-tl-xs border border-border bg-card px-4 py-3 text-xs sm:text-sm leading-relaxed text-card-foreground shadow-xs">
              {streamingMessage ? (
                <MarkdownMessage
                  content={streamingMessage}
                  isStreaming={true}
                  onCitationClick={(num) => {
                    if (streamingCitations[num - 1]) {
                      onOpenCitation?.(streamingCitations, num - 1)
                    }
                  }}
                />
              ) : (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="size-3.5 animate-spin text-primary" />
                  <span>正在查找相关内容并组织回答...</span>
                </div>
              )}
            </div>

            {/* Streaming Citations */}
            {streamingCitations.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className="text-[10px] text-muted-foreground">参考来源:</span>
                {streamingCitations.map((cite, idx) => (
                  <button
                    key={cite.chunk_id || idx}
                    type="button"
                    onClick={() => onOpenCitation?.(streamingCitations, idx)}
                    title={cite.content}
                    className="inline-flex items-center gap-1 rounded-md border border-primary/20 bg-primary/5 px-2 py-0.5 text-[10px] text-primary hover:bg-primary/10 transition-colors"
                  >
                    <FileText className="size-2.5" />
                    <span className="truncate max-w-[130px]">{cite.filename}</span>
                    <span className="font-mono">#{cite.chunk_index}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}

      {streamError && (
        <div
          role="alert"
          className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 rounded-xl border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-xs text-destructive"
        >
          <span className="min-w-0 break-words">{streamError}</span>
          {onRetry && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRetry}
              className="h-7 shrink-0 border-destructive/30 text-destructive hover:bg-destructive/10"
            >
              <RefreshCw className="size-3.5" />
              重试
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
