"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Clock,
  FileCode,
  FileText,
  Loader2,
  StickyNote,
  Trash2,
} from "lucide-react";
import React, { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DocumentFileType, DocumentPublic, DocumentStatus } from "@/lib/rag";

interface DocumentTableProps {
  documents: DocumentPublic[];
  isLoading: boolean;
  onDeleteDocument: (docId: string, filename: string) => Promise<void>;
  onOpenImportModal?: () => void;
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

function formatCharCount(chars: number): string {
  if (chars >= 1_000_000) return `${(chars / 1_000_000).toFixed(1)}M`;
  if (chars >= 1_000) return `${(chars / 1_000).toFixed(1)}k`;
  return String(chars);
}

function getFileTypeIcon(fileType: DocumentFileType) {
  switch (fileType) {
    case "md":
      return <FileCode className="size-4 text-purple-500" />;
    case "pdf":
      return <FileText className="size-4 text-red-500" />;
    case "docx":
      return <FileText className="size-4 text-blue-500" />;
    case "note":
      return <StickyNote className="size-4 text-amber-500" />;
    default:
      return <FileText className="size-4 text-zinc-500" />;
  }
}

function StatusBadge({
  status,
  errorMessage,
}: {
  status: DocumentStatus;
  errorMessage?: string | null;
}) {
  switch (status) {
    case "pending":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
          <Clock className="size-3" />
          <span>排队中</span>
        </span>
      );
    case "parsing":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-600 dark:bg-blue-500/20 dark:text-blue-400">
          <Loader2 className="size-3 animate-spin" />
          <span>解析向量化中</span>
        </span>
      );
    case "ready":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400">
          <CheckCircle2 className="size-3" />
          <span>已就绪</span>
        </span>
      );
    case "failed":
      return (
        <span
          title={errorMessage || "解析失败"}
          className="inline-flex cursor-help items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive dark:bg-destructive/20"
        >
          <AlertCircle className="size-3" />
          <span>解析失败</span>
        </span>
      );
    default:
      return null;
  }
}

export function DocumentTable({
  documents,
  isLoading,
  onDeleteDocument,
  onOpenImportModal,
}: DocumentTableProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = async (doc: DocumentPublic) => {
    if (window.confirm(`确定要删除文档「${doc.filename}」吗？\n该文档的所有切片和向量索引将被彻底移除。`)) {
      try {
        setDeletingId(doc.id);
        await onDeleteDocument(doc.id, doc.filename);
      } finally {
        setDeletingId(null);
      }
    }
  };

  const activeProcessingCount = documents.filter(
    (d) => d.status === "pending" || d.status === "parsing"
  ).length;

  return (
    <div className="space-y-4">
      {/* Section Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2.5">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            文档资料列表
          </h2>
          <Badge variant="secondary" className="text-xs font-normal">
            共 {documents.length} 篇
          </Badge>
          {activeProcessingCount > 0 && (
            <span className="flex items-center gap-1.5 rounded-full bg-blue-500/10 px-2.5 py-0.5 text-xs text-blue-600 dark:bg-blue-500/20 dark:text-blue-400">
              <Loader2 className="size-3 animate-spin" />
              <span>{activeProcessingCount} 篇正在解析（实时刷新中）</span>
            </span>
          )}
        </div>

        {onOpenImportModal && (
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenImportModal}
            className="flex items-center gap-1.5 self-start sm:self-auto"
          >
            <BookOpen className="size-3.5" />
            <span>从已有笔记导入</span>
          </Button>
        )}
      </div>

      {/* Table Container */}
      <div className="overflow-hidden rounded-2xl border border-zinc-200/80 bg-white/70 backdrop-blur-xl dark:border-white/[0.08] dark:bg-zinc-900/60 shadow-sm">
        {isLoading && documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Loader2 className="size-7 animate-spin text-primary" />
            <p className="mt-3 text-xs text-zinc-400">正在加载文档列表...</p>
          </div>
        ) : documents.length === 0 ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
            <div className="flex size-12 items-center justify-center rounded-2xl bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500 mb-3">
              <FileText className="size-6" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
              知识库暂无文档
            </h3>
            <p className="mt-1 max-w-sm text-xs text-zinc-500 dark:text-zinc-400">
              可通过上方区域拖拽上传 PDF、Markdown、Word 文档，或从已有的 Markdown 笔记一键导入构建索引。
            </p>
            {onOpenImportModal && (
              <Button
                variant="outline"
                size="sm"
                onClick={onOpenImportModal}
                className="mt-4 flex items-center gap-1.5"
              >
                <BookOpen className="size-3.5" />
                <span>从已有笔记中导入</span>
              </Button>
            )}
          </div>
        ) : (
          /* Documents Table */
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-zinc-200/60 bg-zinc-50/50 text-zinc-500 dark:border-white/[0.05] dark:bg-zinc-800/30 dark:text-zinc-400">
                  <th className="px-4 py-3 font-medium">文档名称</th>
                  <th className="px-4 py-3 font-medium">来源</th>
                  <th className="px-4 py-3 font-medium">切片数</th>
                  <th className="px-4 py-3 font-medium">字符量</th>
                  <th className="px-4 py-3 font-medium">解析状态</th>
                  <th className="px-4 py-3 font-medium">上传时间</th>
                  <th className="px-4 py-3 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200/60 dark:divide-white/[0.05]">
                <AnimatePresence initial={false}>
                  {documents.map((doc) => (
                    <motion.tr
                      key={doc.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: -8 }}
                      className="group transition-colors hover:bg-zinc-50/60 dark:hover:bg-zinc-800/20"
                    >
                      {/* Filename & Type */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800">
                            {getFileTypeIcon(doc.file_type)}
                          </div>
                          <div className="min-w-0 max-w-xs md:max-w-md">
                            <p className="truncate font-medium text-zinc-900 dark:text-zinc-100" title={doc.filename}>
                              {doc.filename}
                            </p>
                            {doc.error_message && (
                              <p className="truncate text-[11px] text-destructive" title={doc.error_message}>
                                错误: {doc.error_message}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Source */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        {doc.source_type === "note" ? (
                          <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:bg-amber-500/20 dark:text-amber-400">
                            <BookOpen className="size-3" />
                            笔记
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-md bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                            <FileText className="size-3" />
                            上传
                          </span>
                        )}
                      </td>

                      {/* Chunk count */}
                      <td className="px-4 py-3 whitespace-nowrap text-zinc-600 dark:text-zinc-300 font-mono">
                        {doc.status === "ready" ? `${doc.chunk_count} 个` : "-"}
                      </td>

                      {/* Char count */}
                      <td className="px-4 py-3 whitespace-nowrap text-zinc-600 dark:text-zinc-300 font-mono">
                        {doc.status === "ready" ? `${formatCharCount(doc.char_count)} 字` : "-"}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <StatusBadge status={doc.status} errorMessage={doc.error_message} />
                      </td>

                      {/* Time */}
                      <td className="px-4 py-3 whitespace-nowrap text-zinc-400" title={doc.created_at}>
                        {formatRelativeTime(doc.created_at)}
                      </td>

                      {/* Action */}
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(doc)}
                          disabled={deletingId === doc.id}
                          className="size-7 text-zinc-400 hover:bg-destructive/10 hover:text-destructive dark:hover:bg-destructive/20"
                          title="删除文档"
                        >
                          {deletingId === doc.id ? (
                            <Loader2 className="size-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="size-3.5" />
                          )}
                        </Button>
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
