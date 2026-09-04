"use client";

import { motion } from "framer-motion";
import {
  BookOpen,
  Bot,
  FileText,
  Loader2,
  Sparkles,
  User,
} from "lucide-react";
import React, { useEffect, useRef } from "react";

import type { ConversationPublic, KnowledgeBasePublic, MessagePublic } from "@/lib/rag";

interface ChatMessagesProps {
  kb: KnowledgeBasePublic;
  conversation: ConversationPublic | null;
  isLoading: boolean;
  streamingDelta?: string;
  onSendPresetQuery?: (query: string) => void;
}

const PRESET_QUERIES = [
  "总结此知识库收录文档的核心要点与主题脉络",
  "根据知识库文档，列出关键技术决策与最佳实践",
  "梳理文档中涉及的常见问题与解决方案",
];

export function ChatMessages({
  kb,
  conversation,
  isLoading,
  streamingDelta,
  onSendPresetQuery,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages, streamingDelta]);

  if (isLoading && !conversation) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
        <Loader2 className="size-7 animate-spin text-primary" />
        <p className="mt-3 text-xs text-zinc-400">正在加载会话对话流...</p>
      </div>
    );
  }

  const messages = conversation?.messages || [];

  if (messages.length === 0 && !streamingDelta) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
        <div className="max-w-md space-y-4">
          <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-3xl text-primary ring-1 ring-primary/20">
            {kb.icon || <BookOpen className="size-7" />}
          </div>

          <div className="space-y-1.5">
            <h3 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
              与「{kb.title}」开始智能对话
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
              基于该知识库收录的 {kb.doc_count} 篇文档与 {kb.chunk_count} 个切片，采用 pgvector 余弦向量与全文检索混合召回，提供精准原文溯源解答。
            </p>
          </div>

          {/* Preset Prompts */}
          <div className="pt-3 space-y-2">
            <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
              推荐探索问题
            </p>
            <div className="space-y-2 text-left">
              {PRESET_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => onSendPresetQuery?.(q)}
                  className="w-full rounded-xl border border-zinc-200/80 bg-white/60 p-3 text-xs text-zinc-700 transition-all hover:border-primary/40 hover:bg-primary/5 hover:text-primary dark:border-white/[0.08] dark:bg-zinc-900/40 dark:text-zinc-300 dark:hover:border-primary/40 dark:hover:bg-primary/10"
                >
                  <div className="flex items-center gap-2">
                    <Sparkles className="size-3.5 text-primary shrink-0" />
                    <span className="truncate">{q}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
      {messages.map((msg: MessagePublic) => {
        const isUser = msg.role === "user";

        return (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex gap-3 max-w-3xl ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`}
          >
            {/* Avatar */}
            <div
              className={`flex size-8 shrink-0 items-center justify-center rounded-xl text-xs font-semibold ${
                isUser
                  ? "bg-primary text-white shadow-xs"
                  : "bg-zinc-100 text-zinc-700 ring-1 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-200 dark:ring-white/[0.1]"
              }`}
            >
              {isUser ? <User className="size-4" /> : <Bot className="size-4 text-primary" />}
            </div>

            {/* Bubble */}
            <div className="space-y-2 min-w-0 max-w-[85%]">
              <div
                className={`rounded-2xl px-4 py-3 text-xs sm:text-sm leading-relaxed ${
                  isUser
                    ? "bg-primary text-primary-foreground rounded-tr-xs"
                    : "bg-white/80 border border-zinc-200/80 text-zinc-800 dark:bg-zinc-900/80 dark:border-white/[0.08] dark:text-zinc-200 rounded-tl-xs shadow-xs"
                }`}
              >
                <div className="whitespace-pre-wrap break-words">{msg.content}</div>
              </div>

              {/* Citations Preview (if any) */}
              {!isUser && msg.citations && msg.citations.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {msg.citations.map((cite, idx) => (
                    <span
                      key={cite.chunk_id || idx}
                      title={cite.content}
                      className="inline-flex items-center gap-1 rounded-md border border-primary/20 bg-primary/5 px-2 py-0.5 text-[10px] text-primary cursor-pointer hover:bg-primary/10 transition-colors"
                    >
                      <FileText className="size-2.5" />
                      <span className="truncate max-w-[140px]">{cite.filename}</span>
                      <span className="font-mono">#{cite.chunk_index}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        );
      })}

      {/* Streaming Delta Bubble (if active in 4.5.b) */}
      {streamingDelta && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex gap-3 max-w-3xl mr-auto"
        >
          <div className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-zinc-100 text-zinc-700 ring-1 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-200 dark:ring-white/[0.1]">
            <Bot className="size-4 text-primary" />
          </div>
          <div className="rounded-2xl rounded-tl-xs border border-zinc-200/80 bg-white/80 px-4 py-3 text-xs sm:text-sm leading-relaxed text-zinc-800 shadow-xs dark:border-white/[0.08] dark:bg-zinc-900/80 dark:text-zinc-200 min-w-0 max-w-[85%]">
            <div className="whitespace-pre-wrap break-words">{streamingDelta}</div>
          </div>
        </motion.div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
