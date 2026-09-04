"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  FileCode,
  FileText,
  Loader2,
  UploadCloud,
  X,
} from "lucide-react";
import React, { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { uploadDocuments } from "@/lib/rag";

const ALLOWED_EXTENSIONS = [".md", ".txt", ".pdf", ".docx"];
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB
const MAX_BATCH_FILES = 10;

interface DocumentUploadZoneProps {
  kbId: string;
  onUploadSuccess?: () => void;
  disabled?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentUploadZone({
  kbId,
  onUploadSuccess,
  disabled = false,
}: DocumentUploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const validateFiles = (files: File[]): { valid: File[]; error: string | null } => {
    if (files.length === 0) {
      return { valid: [], error: null };
    }
    if (files.length > MAX_BATCH_FILES) {
      return {
        valid: [],
        error: `单次上传最多支持 ${MAX_BATCH_FILES} 个文件，当前选择了 ${files.length} 个`,
      };
    }

    const validFiles: File[] = [];
    for (const file of files) {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        return {
          valid: [],
          error: `文件「${file.name}」格式不受支持。仅支持 Markdown (.md), 文本 (.txt), PDF (.pdf), Word (.docx)`,
        };
      }
      if (file.size > MAX_FILE_SIZE) {
        return {
          valid: [],
          error: `文件「${file.name}」(${formatBytes(file.size)}) 超过了 20MB 单文件上限`,
        };
      }
      validFiles.push(file);
    }

    return { valid: validFiles, error: null };
  };

  const handleUpload = async (files: File[]) => {
    setErrorMessage(null);
    setSuccessMessage(null);

    const { valid, error } = validateFiles(files);
    if (error) {
      setErrorMessage(error);
      return;
    }
    if (valid.length === 0) return;

    try {
      setIsUploading(true);
      const res = await uploadDocuments(kbId, valid);
      setSuccessMessage(`成功上传 ${res.length} 篇文档，后台已启动切片解析与向量化！`);
      onUploadSuccess?.();
    } catch (err: any) {
      setErrorMessage(err?.message || "上传失败，请检查网络或稍后重试");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled && !isUploading) {
      setIsDragging(true);
    }
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (disabled || isUploading) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFiles = Array.from(e.dataTransfer.files);
      handleUpload(droppedFiles);
    }
  };

  const onFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);
      handleUpload(selectedFiles);
    }
  };

  return (
    <div className="space-y-3">
      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".md,.txt,.pdf,.docx,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={onFileInputChange}
        className="hidden"
        disabled={disabled || isUploading}
      />

      {/* Drag & Drop Container */}
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => {
          if (!disabled && !isUploading) {
            fileInputRef.current?.click();
          }
        }}
        className={`group relative flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 transition-all duration-200 ${
          isDragging
            ? "border-primary bg-primary/5 scale-[1.005] shadow-md dark:border-primary/80 dark:bg-primary/10"
            : "border-zinc-200/90 bg-white/40 hover:border-zinc-300 hover:bg-white/70 dark:border-white/[0.08] dark:bg-zinc-900/30 dark:hover:border-zinc-700 dark:hover:bg-zinc-900/50"
        } ${disabled || isUploading ? "pointer-events-none opacity-60" : ""}`}
      >
        <div className="flex flex-col items-center text-center space-y-3">
          <div
            className={`flex size-14 items-center justify-center rounded-2xl transition-colors ${
              isDragging
                ? "bg-primary text-white shadow-lg"
                : "bg-primary/10 text-primary dark:bg-primary/20"
            }`}
          >
            {isUploading ? (
              <Loader2 className="size-7 animate-spin" />
            ) : (
              <UploadCloud className="size-7 transition-transform group-hover:-translate-y-0.5" />
            )}
          </div>

          <div className="space-y-1">
            <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
              {isUploading
                ? "正在传输文档并提交后台解析..."
                : isDragging
                ? "松开鼠标立即上传文档"
                : "点击选择本地文档 或 拖拽文件至此处"}
            </p>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              支持 <span className="font-medium text-zinc-700 dark:text-zinc-300">Markdown (.md)</span>、
              <span className="font-medium text-zinc-700 dark:text-zinc-300">纯文本 (.txt)</span>、
              <span className="font-medium text-zinc-700 dark:text-zinc-300">PDF (.pdf)</span>、
              <span className="font-medium text-zinc-700 dark:text-zinc-300">Word (.docx)</span>
            </p>
          </div>

          <div className="flex items-center gap-3 text-[11px] text-zinc-400">
            <span>单文件上限 20MB</span>
            <span>•</span>
            <span>单次批量最多 10 份</span>
            <span>•</span>
            <span>自动切片 & 向量化</span>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      <AnimatePresence>
        {errorMessage && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex items-center justify-between rounded-xl border border-destructive/20 bg-destructive/10 px-4 py-2.5 text-xs text-destructive"
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="size-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-destructive/70 hover:text-destructive"
            >
              <X className="size-3.5" />
            </button>
          </motion.div>
        )}

        {successMessage && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            className="flex items-center justify-between rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2.5 text-xs text-emerald-600 dark:text-emerald-400"
          >
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-emerald-500" />
              <span>{successMessage}</span>
            </div>
            <button
              onClick={() => setSuccessMessage(null)}
              className="text-emerald-500/70 hover:text-emerald-600 dark:hover:text-emerald-300"
            >
              <X className="size-3.5" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
