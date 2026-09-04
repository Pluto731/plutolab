"use client";

import { ArrowUp, Square } from "lucide-react";
import React, { useRef, useState } from "react";

import { Button } from "@/components/ui/button";

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  onStop,
  disabled = false,
  isStreaming = false,
  placeholder = "向该知识库提问任何问题...",
}: ChatInputProps) {
  const [content, setContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (isStreaming) {
      onStop?.();
      return;
    }
    const trimmed = content.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setContent("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value);
    // Auto-resize up to 160px
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  return (
    <div className="border-t border-zinc-200/80 bg-white/70 p-4 backdrop-blur-xl dark:border-white/[0.08] dark:bg-zinc-900/60">
      <form onSubmit={handleSubmit} className="mx-auto max-w-3xl">
        <div className="relative flex items-end gap-2 rounded-2xl border border-zinc-200/90 bg-white p-2 shadow-sm transition-all focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 dark:border-white/[0.1] dark:bg-zinc-950">
          <textarea
            ref={textareaRef}
            rows={1}
            value={content}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            disabled={disabled || isStreaming}
            placeholder={isStreaming ? "AI 正在回答中，可点击右侧按钮随时停止生成..." : placeholder}
            className="w-full resize-none bg-transparent px-3 py-1.5 text-xs sm:text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none dark:text-zinc-100 disabled:opacity-60"
          />

          {isStreaming ? (
            <Button
              type="button"
              size="icon"
              onClick={onStop}
              className="size-8 shrink-0 rounded-xl bg-destructive hover:bg-destructive/90 text-destructive-foreground shadow-xs"
              title="停止生成"
            >
              <Square className="size-3.5 fill-current" />
            </Button>
          ) : (
            <Button
              type="submit"
              size="icon"
              disabled={!content.trim() || disabled}
              className="size-8 shrink-0 rounded-xl"
            >
              <ArrowUp className="size-4" strokeWidth={2.5} />
            </Button>
          )}
        </div>

        <div className="mt-2 flex items-center justify-between px-1 text-[11px] text-zinc-400">
          <span>按 <kbd className="rounded border border-zinc-200 bg-zinc-100 px-1 py-0.5 text-[10px] dark:border-zinc-700 dark:bg-zinc-800">Enter</kbd> 发送，<kbd className="rounded border border-zinc-200 bg-zinc-100 px-1 py-0.5 text-[10px] dark:border-zinc-700 dark:bg-zinc-800">Shift + Enter</kbd> 换行</span>
          <span className="hidden sm:inline">流式打字机 · 原生 SSE · 混合检索</span>
        </div>
      </form>
    </div>
  );
}
