"use client";

import { ArrowUp, Loader2 } from "lucide-react";
import React, { useRef, useState } from "react";

import { Button } from "@/components/ui/button";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  isLoading?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  disabled = false,
  isLoading = false,
  placeholder = "向该知识库提问任何问题...",
}: ChatInputProps) {
  const [content, setContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = content.trim();
    if (!trimmed || disabled || isLoading) return;
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
    // Auto-resize
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
            disabled={disabled || isLoading}
            placeholder={placeholder}
            className="w-full resize-none bg-transparent px-3 py-1.5 text-xs sm:text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none dark:text-zinc-100 disabled:opacity-50"
          />

          <Button
            type="submit"
            size="icon"
            disabled={!content.trim() || disabled || isLoading}
            className="size-8 shrink-0 rounded-xl"
          >
            {isLoading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ArrowUp className="size-4" strokeWidth={2.5} />
            )}
          </Button>
        </div>

        <div className="mt-2 flex items-center justify-between px-1 text-[11px] text-zinc-400">
          <span>按 <kbd className="rounded border border-zinc-200 bg-zinc-100 px-1 py-0.5 text-[10px] dark:border-zinc-700 dark:bg-zinc-800">Enter</kbd> 发送，<kbd className="rounded border border-zinc-200 bg-zinc-100 px-1 py-0.5 text-[10px] dark:border-zinc-700 dark:bg-zinc-800">Shift + Enter</kbd> 换行</span>
          <span className="hidden sm:inline">多路召回融合 · 溯源角标</span>
        </div>
      </form>
    </div>
  );
}
