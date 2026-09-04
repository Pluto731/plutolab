"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  FileCode,
  FileText,
  Layers,
  Sparkles,
  X,
} from "lucide-react";
import React, { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { CitationItem } from "@/lib/rag";

interface CitationDrawerProps {
  open: boolean;
  onClose: () => void;
  citations: CitationItem[];
  currentIndex: number;
  onNavigate: (index: number) => void;
}

function getFileIcon(filename: string) {
  const ext = filename.split(".").pop()?.toLowerCase();
  if (ext === "md") return <FileCode className="size-4 text-purple-500" />;
  if (ext === "pdf") return <FileText className="size-4 text-red-500" />;
  if (ext === "docx") return <FileText className="size-4 text-blue-500" />;
  return <FileText className="size-4 text-zinc-500" />;
}

export function CitationDrawer({
  open,
  onClose,
  citations,
  currentIndex,
  onNavigate,
}: CitationDrawerProps) {
  const [copied, setCopied] = useState(false);

  // Keyboard navigation: Esc to close, ArrowLeft/Right to navigate
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowLeft") {
        if (currentIndex > 0) {
          onNavigate(currentIndex - 1);
        }
      } else if (e.key === "ArrowRight") {
        if (currentIndex < citations.length - 1) {
          onNavigate(currentIndex + 1);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, currentIndex, citations.length, onClose, onNavigate]);

  const currentItem: CitationItem | undefined = citations[currentIndex];

  const handleCopyContent = async () => {
    if (!currentItem) return;
    try {
      await navigator.clipboard.writeText(currentItem.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy citation text", err);
    }
  };

  const hasMultiple = citations.length > 1;
  const matchPercentage = currentItem?.similarity
    ? (currentItem.similarity * 100).toFixed(1)
    : null;

  return (
    <AnimatePresence>
      {open && currentItem && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/30 backdrop-blur-xs"
          />

          {/* Drawer Panel */}
          <motion.div
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 280 }}
            className="relative flex w-full max-w-md sm:max-w-lg flex-col bg-white shadow-2xl dark:bg-zinc-950 border-l border-zinc-200/80 dark:border-white/[0.1] z-10"
          >
            {/* Drawer Header */}
            <div className="flex items-center justify-between border-b border-zinc-200/80 bg-zinc-50/70 px-5 py-3.5 backdrop-blur-md dark:border-white/[0.08] dark:bg-zinc-900/50">
              <div className="flex items-center gap-2">
                <div className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Sparkles className="size-3.5" />
                </div>
                <div>
                  <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">
                    原文切片溯源
                  </h3>
                  <p className="text-[11px] text-zinc-400">
                    检索增强召回切片与余弦相似度
                  </p>
                </div>
              </div>

              {/* Navigation & Close */}
              <div className="flex items-center gap-1.5">
                {hasMultiple && (
                  <div className="flex items-center gap-1 rounded-lg border border-zinc-200 bg-white px-1.5 py-0.5 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
                    <button
                      onClick={() => onNavigate(Math.max(0, currentIndex - 1))}
                      disabled={currentIndex === 0}
                      className="rounded p-0.5 hover:bg-zinc-100 disabled:opacity-30 dark:hover:bg-zinc-800"
                      title="上一个切片 (←)"
                    >
                      <ChevronLeft className="size-3.5" />
                    </button>
                    <span className="font-mono text-[11px] px-1 font-medium">
                      {currentIndex + 1} / {citations.length}
                    </span>
                    <button
                      onClick={() => onNavigate(Math.min(citations.length - 1, currentIndex + 1))}
                      disabled={currentIndex === citations.length - 1}
                      className="rounded p-0.5 hover:bg-zinc-100 disabled:opacity-30 dark:hover:bg-zinc-800"
                      title="下一个切片 (→)"
                    >
                      <ChevronRight className="size-3.5" />
                    </button>
                  </div>
                )}

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  className="size-7 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
                >
                  <X className="size-4" />
                </Button>
              </div>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* Document Meta Card */}
              <div className="rounded-xl border border-zinc-200/80 bg-zinc-50/50 p-3.5 dark:border-white/[0.08] dark:bg-zinc-900/40 space-y-2.5">
                <div className="flex items-start gap-2.5">
                  <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-white shadow-xs dark:bg-zinc-800">
                    {getFileIcon(currentItem.filename)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-xs text-zinc-900 dark:text-zinc-100 truncate" title={currentItem.filename}>
                      {currentItem.filename}
                    </p>
                    <div className="flex flex-wrap items-center gap-2 pt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                      <span className="inline-flex items-center gap-1">
                        <Layers className="size-3 text-zinc-400" />
                        <span>分块 #{currentItem.chunk_index}</span>
                      </span>

                      {currentItem.metadata?.page && (
                        <>
                          <span>•</span>
                          <span>第 {currentItem.metadata.page} 页</span>
                        </>
                      )}

                      <span>•</span>
                      <span>{currentItem.content.length} 字符</span>
                    </div>
                  </div>
                </div>

                {/* Match Score Badge */}
                {matchPercentage && (
                  <div className="flex items-center justify-between pt-1 border-t border-zinc-200/60 dark:border-white/[0.05]">
                    <span className="text-[11px] text-zinc-400">向量召回余弦评分:</span>
                    <Badge variant="secondary" className="font-mono text-[11px] bg-primary/10 text-primary border-primary/20">
                      <Sparkles className="size-2.5 mr-1" />
                      {matchPercentage}% 匹配度
                    </Badge>
                  </div>
                )}
              </div>

              {/* Raw Content Section */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                    切片原文内容
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopyContent}
                    className="h-7 text-xs px-2 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100"
                  >
                    {copied ? (
                      <>
                        <Check className="size-3 mr-1 text-emerald-500" />
                        <span className="text-emerald-500">已复制</span>
                      </>
                    ) : (
                      <>
                        <Copy className="size-3 mr-1" />
                        <span>复制切片</span>
                      </>
                    )}
                  </Button>
                </div>

                {/* Content Box */}
                <div className="rounded-xl border border-zinc-200/90 bg-white p-4 text-xs sm:text-sm leading-relaxed text-zinc-800 shadow-xs dark:border-white/[0.08] dark:bg-zinc-900/60 dark:text-zinc-200 max-h-[460px] overflow-y-auto whitespace-pre-wrap font-sans">
                  {currentItem.content}
                </div>
              </div>

              {/* Technical identifiers */}
              <div className="rounded-lg bg-zinc-100/60 p-2.5 text-[10px] text-zinc-400 dark:bg-zinc-900/30 space-y-1 font-mono">
                <div className="truncate">Chunk ID: {currentItem.chunk_id}</div>
                <div className="truncate">Doc ID: {currentItem.document_id}</div>
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="flex items-center justify-end border-t border-zinc-200/80 bg-zinc-50/50 p-3.5 dark:border-white/[0.08] dark:bg-zinc-900/40">
              <Button size="sm" variant="outline" onClick={onClose} className="text-xs">
                关闭抽屉 (Esc)
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
