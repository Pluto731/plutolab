"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  BookOpen,
  Check,
  Edit2,
  MessageSquare,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import React, { useState } from "react";

import { Button } from "@/components/ui/button";
import type { ConversationSummary, KnowledgeBasePublic } from "@/lib/rag";

interface ConversationSidebarProps {
  kb: KnowledgeBasePublic;
  conversations: ConversationSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => Promise<void>;
  onRename: (id: string, newTitle: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  isCreating?: boolean;
  className?: string;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const t = new Date(iso).getTime();
  const min = Math.floor((now - t) / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min}m 前`;
  if (min < 1440) return `${Math.floor(min / 60)}h 前`;
  const d = Math.floor(min / 1440);
  if (d < 30) return `${d}d 前`;
  const date = new Date(iso);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

export function ConversationSidebar({
  kb,
  conversations,
  selectedId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  isCreating = false,
  className = "",
  isOpenMobile = false,
  onCloseMobile,
}: ConversationSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [isRenaming, setIsRenaming] = useState(false);

  const startRename = (c: ConversationSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(c.id);
    setEditingTitle(c.title);
  };

  const cancelRename = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingId(null);
    setEditingTitle("");
  };

  const saveRename = async (id: string, e?: React.FormEvent | React.MouseEvent) => {
    e?.stopPropagation();
    if (!editingTitle.trim()) {
      cancelRename();
      return;
    }
    try {
      setIsRenaming(true);
      await onRename(id, editingTitle.trim());
      setEditingId(null);
    } finally {
      setIsRenaming(false);
    }
  };

  const handleDelete = async (c: ConversationSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm(`确定要删除会话「${c.title}」吗？\n该会话下的所有问答消息将被彻底清空。`)) {
      await onDelete(c.id);
    }
  };

  const sidebarContent = (
    <div className="flex h-full flex-col">
      {/* Top Header: Return to KB */}
      <div className="p-4 border-b border-zinc-200/70 dark:border-white/[0.08]">
        <Link
          href={`/rag/${kb.id}`}
          className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors mb-3"
        >
          <ArrowLeft className="size-3.5" />
          <span>返回知识库详情</span>
        </Link>

        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary font-medium text-lg">
            {kb.icon || <BookOpen className="size-4" />}
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-bold text-zinc-900 dark:text-zinc-100 truncate" title={kb.title}>
              {kb.title}
            </h2>
            <p className="text-[11px] text-zinc-400 truncate">
              {kb.doc_count} 篇文档 · {kb.chunk_count} 切片
            </p>
          </div>
        </div>

        {/* New Chat Button */}
        <Button
          onClick={onCreate}
          disabled={isCreating}
          size="sm"
          className="mt-3.5 w-full flex items-center justify-center gap-1.5 shadow-sm"
        >
          <Plus className="size-4" />
          <span>新建对话</span>
        </Button>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-1">
        <div className="px-2 py-1 text-[11px] font-medium uppercase tracking-wider text-zinc-400">
          历史会话 ({conversations.length})
        </div>

        {conversations.length === 0 ? (
          <div className="p-4 text-center text-xs text-zinc-400">
            暂无历史对话<br />点击上方按钮开始
          </div>
        ) : (
          conversations.map((c) => {
            const isSelected = selectedId === c.id;
            const isEditing = editingId === c.id;

            return (
              <div
                key={c.id}
                onClick={() => {
                  if (!isEditing) {
                    onSelect(c.id);
                    onCloseMobile?.();
                  }
                }}
                className={`group relative flex items-center justify-between rounded-xl px-3 py-2.5 text-xs transition-all cursor-pointer ${
                  isSelected
                    ? "bg-primary/10 text-primary font-semibold shadow-xs ring-1 ring-primary/20 dark:bg-primary/15"
                    : "text-zinc-600 hover:bg-zinc-100/80 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800/50 dark:hover:text-zinc-200"
                }`}
              >
                {/* Left side: Icon + Title or Inline Editor */}
                <div className="flex items-center gap-2 min-w-0 flex-1 mr-2">
                  <MessageSquare className={`size-4 shrink-0 ${isSelected ? "text-primary" : "text-zinc-400"}`} />

                  {isEditing ? (
                    <div
                      className="flex items-center gap-1 w-full"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="text"
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveRename(c.id, e);
                          if (e.key === "Escape") cancelRename();
                        }}
                        autoFocus
                        disabled={isRenaming}
                        className="w-full rounded border border-primary/40 bg-white px-1.5 py-0.5 text-xs text-zinc-900 outline-none dark:bg-zinc-900 dark:text-zinc-100"
                      />
                      <button
                        onClick={(e) => saveRename(c.id, e)}
                        disabled={isRenaming}
                        className="text-primary hover:text-primary/80"
                        title="保存"
                      >
                        <Check className="size-3.5" />
                      </button>
                      <button
                        onClick={cancelRename}
                        className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                        title="取消"
                      >
                        <X className="size-3.5" />
                      </button>
                    </div>
                  ) : (
                    <div className="truncate min-w-0 flex-1">
                      <span className="truncate block" title={c.title}>
                        {c.title}
                      </span>
                    </div>
                  )}
                </div>

                {/* Right side: Time / Actions */}
                {!isEditing && (
                  <div className="flex items-center gap-1 shrink-0">
                    {/* Hover action buttons */}
                    <div className="hidden group-hover:flex items-center gap-0.5">
                      <button
                        onClick={(e) => startRename(c, e)}
                        className="rounded p-1 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
                        title="重命名"
                      >
                        <Edit2 className="size-3" />
                      </button>
                      <button
                        onClick={(e) => handleDelete(c, e)}
                        className="rounded p-1 text-zinc-400 hover:text-destructive"
                        title="删除会话"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </div>

                    {/* Time indicator (shown when not hovering) */}
                    <span className="text-[10px] text-zinc-400 group-hover:hidden">
                      {formatRelativeTime(c.updated_at)}
                    </span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:flex flex-col w-72 shrink-0 border-r border-zinc-200/80 bg-white/70 backdrop-blur-xl dark:border-white/[0.08] dark:bg-zinc-900/60 ${className}`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Drawer Overlay */}
      <AnimatePresence>
        {isOpenMobile && (
          <div className="fixed inset-0 z-50 flex md:hidden">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onCloseMobile}
              className="absolute inset-0 bg-black/40 backdrop-blur-xs"
            />
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 250 }}
              className="relative flex flex-col w-80 max-w-[85vw] bg-white dark:bg-zinc-950 shadow-2xl z-10"
            >
              <div className="absolute right-3 top-3">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onCloseMobile}
                  className="size-7 text-zinc-400"
                >
                  <X className="size-4" />
                </Button>
              </div>
              {sidebarContent}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
