"use client";

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  BookOpen,
  Check,
  CheckCheck,
  CheckSquare,
  Clock,
  Loader2,
  Search,
  Square,
  Tag,
  X,
} from "lucide-react";
import React, { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { listNotes, type NoteSummary } from "@/lib/notes";
import { importNotesToKnowledgeBase, type DocumentPublic } from "@/lib/rag";

interface ImportNotesDialogProps {
  open: boolean;
  onClose: () => void;
  kbId: string;
  existingDocuments: DocumentPublic[];
  onImportSuccess?: () => void;
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

export function ImportNotesDialog({
  open,
  onClose,
  kbId,
  existingDocuments,
  onImportSuccess,
}: ImportNotesDialogProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isImporting, setIsImporting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Fetch all user notes
  const { data: notes = [], isLoading } = useQuery<NoteSummary[]>({
    queryKey: ["notes"],
    queryFn: () => listNotes(),
    enabled: open,
    staleTime: 30 * 1000,
  });

  // Collect notes already imported in this KB
  const importedNoteIdSet = useMemo(() => {
    const set = new Set<string>();
    for (const doc of existingDocuments) {
      if (doc.source_note_id) {
        set.add(doc.source_note_id);
      }
    }
    return set;
  }, [existingDocuments]);

  // Extract all distinct tags
  const allTags = useMemo(() => {
    const tagSet = new Set<string>();
    for (const note of notes) {
      for (const t of note.tags || []) {
        tagSet.add(t);
      }
    }
    return Array.from(tagSet).sort();
  }, [notes]);

  // Filter notes based on search query and selected tag
  const filteredNotes = useMemo(() => {
    let result = notes;
    if (selectedTag) {
      result = result.filter((n) => n.tags?.includes(selectedTag));
    }
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      result = result.filter(
        (n) =>
          n.title.toLowerCase().includes(q) ||
          (n.excerpt && n.excerpt.toLowerCase().includes(q)) ||
          n.tags?.some((t) => t.toLowerCase().includes(q))
      );
    }
    return result;
  }, [notes, selectedTag, searchQuery]);

  // Selectable notes in current filtered list (exclude already imported)
  const selectableNotes = useMemo(() => {
    return filteredNotes.filter((n) => !importedNoteIdSet.has(n.id));
  }, [filteredNotes, importedNoteIdSet]);

  const toggleSelect = (id: string) => {
    if (importedNoteIdSet.has(id)) return;
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    const next = new Set(selectedIds);
    for (const note of selectableNotes) {
      next.add(note.id);
    }
    setSelectedIds(next);
  };

  const handleClearSelection = () => {
    setSelectedIds(new Set());
  };

  const handleConfirmImport = async () => {
    if (selectedIds.size === 0) return;

    try {
      setIsImporting(true);
      setErrorMessage(null);
      await importNotesToKnowledgeBase(kbId, Array.from(selectedIds));
      setSelectedIds(new Set());
      onImportSuccess?.();
      onClose();
    } catch (err: any) {
      setErrorMessage(err?.message || "导入笔记失败，请重试");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/40 backdrop-blur-md dark:bg-black/60"
          />

          {/* Dialog Container */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ type: "spring", duration: 0.25 }}
            className="relative flex flex-col w-full max-w-2xl max-h-[85vh] overflow-hidden rounded-2xl border border-zinc-200/80 bg-white/95 p-6 shadow-2xl backdrop-blur-2xl dark:border-white/[0.1] dark:bg-zinc-950/95"
          >
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-zinc-100 dark:border-zinc-800">
              <div className="flex items-center gap-2.5">
                <div className="flex size-9 items-center justify-center rounded-xl bg-amber-500/10 text-amber-500 dark:bg-amber-500/20">
                  <BookOpen className="size-4.5" />
                </div>
                <div>
                  <h3 className="font-semibold text-base text-zinc-900 dark:text-zinc-100">
                    从已有笔记导入
                  </h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    一键将 Markdown 笔记转换为知识库语料，自动切块并向量化入库
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                className="size-7 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
              >
                <X className="size-4" />
              </Button>
            </div>

            {/* Error Banner */}
            {errorMessage && (
              <div className="mt-3 flex items-center gap-2 rounded-xl bg-destructive/10 px-3.5 py-2 text-xs text-destructive">
                <AlertCircle className="size-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {/* Search & Tag Filter Bar */}
            <div className="mt-4 space-y-2.5">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="搜索笔记标题、内容摘要或标签..."
                  className="pl-9 h-9 text-xs"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                  >
                    <X className="size-3.5" />
                  </button>
                )}
              </div>

              {/* Tag Badges */}
              {allTags.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                  <button
                    onClick={() => setSelectedTag(null)}
                    className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors ${
                      selectedTag === null
                        ? "bg-primary text-white"
                        : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
                    }`}
                  >
                    全部标签
                  </button>
                  {allTags.map((tag) => (
                    <button
                      key={tag}
                      onClick={() => setSelectedTag(selectedTag === tag ? null : tag)}
                      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors ${
                        selectedTag === tag
                          ? "bg-primary text-white"
                          : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
                      }`}
                    >
                      <Tag className="size-2.5" />
                      <span>{tag}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Selection Quick Actions */}
            <div className="mt-3 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400 px-1">
              <span>
                匹配到 <span className="font-semibold text-zinc-800 dark:text-zinc-200">{filteredNotes.length}</span> 篇笔记
                {selectableNotes.length < filteredNotes.length && (
                  <span className="text-zinc-400 ml-1">
                    ({filteredNotes.length - selectableNotes.length} 篇已在此库中)
                  </span>
                )}
              </span>

              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSelectAll}
                  disabled={selectableNotes.length === 0}
                  className="h-7 text-xs px-2"
                >
                  <CheckSquare className="size-3 mr-1" />
                  全选当前
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearSelection}
                  disabled={selectedIds.size === 0}
                  className="h-7 text-xs px-2 text-zinc-400"
                >
                  <Square className="size-3 mr-1" />
                  清空已选
                </Button>
              </div>
            </div>

            {/* Notes List Container */}
            <div className="mt-2 flex-1 overflow-y-auto divide-y divide-zinc-100 dark:divide-zinc-800/80 rounded-xl border border-zinc-200/60 dark:border-white/[0.05] max-h-[380px]">
              {isLoading ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Loader2 className="size-6 animate-spin text-primary" />
                  <p className="mt-2 text-xs text-zinc-400">正在读取笔记列表...</p>
                </div>
              ) : filteredNotes.length === 0 ? (
                <div className="py-12 px-4 text-center text-xs text-zinc-400">
                  {searchQuery || selectedTag
                    ? "未找到符合筛选条件的笔记"
                    : "您尚未创建任何 Markdown 笔记"}
                </div>
              ) : (
                filteredNotes.map((note) => {
                  const isAlreadyImported = importedNoteIdSet.has(note.id);
                  const isSelected = selectedIds.has(note.id);

                  return (
                    <div
                      key={note.id}
                      onClick={() => toggleSelect(note.id)}
                      className={`flex items-start gap-3 p-3 text-xs transition-colors ${
                        isAlreadyImported
                          ? "opacity-50 cursor-not-allowed bg-zinc-50/40 dark:bg-zinc-900/40"
                          : isSelected
                          ? "bg-primary/5 dark:bg-primary/10 cursor-pointer hover:bg-primary/10"
                          : "hover:bg-zinc-50 cursor-pointer dark:hover:bg-zinc-800/30"
                      }`}
                    >
                      {/* Checkbox Icon */}
                      <div className="pt-0.5 shrink-0">
                        {isAlreadyImported ? (
                          <div className="flex size-4 items-center justify-center rounded border border-zinc-300 bg-zinc-200 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800">
                            <Check className="size-3" />
                          </div>
                        ) : isSelected ? (
                          <div className="flex size-4 items-center justify-center rounded bg-primary text-white">
                            <Check className="size-3" strokeWidth={3} />
                          </div>
                        ) : (
                          <div className="size-4 rounded border border-zinc-300 dark:border-zinc-600" />
                        )}
                      </div>

                      {/* Content Info */}
                      <div className="flex-1 min-w-0 space-y-1">
                        <div className="flex items-center gap-2">
                          <h4 className="font-semibold text-zinc-900 dark:text-zinc-100 truncate">
                            {note.title}
                          </h4>
                          {isAlreadyImported && (
                            <Badge
                              variant="outline"
                              className="text-[10px] text-zinc-400 border-zinc-200 dark:border-zinc-700 shrink-0"
                            >
                              已导入本库
                            </Badge>
                          )}
                        </div>

                        {note.excerpt && (
                          <p className="text-zinc-500 dark:text-zinc-400 line-clamp-1 text-[11px] leading-relaxed">
                            {note.excerpt}
                          </p>
                        )}

                        <div className="flex flex-wrap items-center gap-2 pt-0.5 text-[10px] text-zinc-400">
                          <span className="flex items-center gap-1">
                            <Clock className="size-2.5" />
                            {formatRelativeTime(note.updated_at)}
                          </span>

                          {note.tags && note.tags.length > 0 && (
                            <>
                              <span>•</span>
                              <div className="flex items-center gap-1">
                                {note.tags.slice(0, 3).map((t) => (
                                  <span
                                    key={t}
                                    className="rounded bg-zinc-100 px-1.5 py-0.2 text-[10px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                                  >
                                    #{t}
                                  </span>
                                ))}
                                {note.tags.length > 3 && (
                                  <span>+{note.tags.length - 3}</span>
                                )}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer Actions */}
            <div className="mt-5 flex items-center justify-between pt-4 border-t border-zinc-100 dark:border-zinc-800">
              <div className="text-xs text-zinc-500">
                已选中 <span className="font-bold text-primary">{selectedIds.size}</span> 篇笔记
              </div>

              <div className="flex items-center gap-2.5">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onClose}
                  disabled={isImporting}
                >
                  取消
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={isImporting || selectedIds.size === 0}
                  onClick={handleConfirmImport}
                  className="flex items-center gap-1.5 shadow-sm"
                >
                  {isImporting ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <CheckCheck className="size-3.5" />
                  )}
                  <span>确认导入 ({selectedIds.size})</span>
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
