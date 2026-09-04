"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Sparkles, X } from "lucide-react";
import React, { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { KnowledgeBaseCreate } from "@/lib/rag";

interface CreateKnowledgeBaseDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: KnowledgeBaseCreate) => Promise<void>;
}

const PRESET_ICONS = ["📚", "🧠", "🪐", "⚡️", "🔬", "💻", "🎯", "🚀", "📊", "💡"];

export function CreateKnowledgeBaseDialog({
  open,
  onClose,
  onSubmit,
}: CreateKnowledgeBaseDialogProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState("📚");
  const [embeddingModel, setEmbeddingModel] = useState("text-embedding-3-small");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("知识库名称不能为空");
      return;
    }

    try {
      setLoading(true);
      setError("");
      await onSubmit({
        title: title.trim(),
        description: description.trim() || null,
        icon,
        embedding_model: embeddingModel,
      });
      // Reset form
      setTitle("");
      setDescription("");
      setIcon("📚");
      onClose();
    } catch (err: any) {
      setError(err?.message || "创建知识库失败，请重试");
    } finally {
      setLoading(false);
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
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ type: "spring", duration: 0.25 }}
            className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-zinc-200/80 bg-white/90 p-6 shadow-2xl backdrop-blur-2xl dark:border-white/[0.1] dark:bg-zinc-950/90"
          >
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-zinc-100 dark:border-zinc-800">
              <div className="flex items-center gap-2">
                <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary dark:bg-primary/20">
                  <Sparkles className="size-4" />
                </div>
                <h3 className="font-semibold text-lg text-zinc-900 dark:text-zinc-100">
                  新建知识库
                </h3>
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

            {/* Error banner */}
            {error && (
              <div className="mt-4 rounded-lg bg-destructive/10 p-3 text-xs text-destructive">
                {error}
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="mt-5 space-y-4">
              {/* Title */}
              <div className="space-y-1.5">
                <Label htmlFor="kb-title" className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                  知识库名称 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="kb-title"
                  placeholder="例如：系统设计与架构规范"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={100}
                  autoFocus
                  className="h-9 text-sm"
                />
              </div>

              {/* Icon Selector */}
              <div className="space-y-1.5">
                <Label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                  选择图标 Emoji
                </Label>
                <div className="flex flex-wrap gap-2">
                  {PRESET_ICONS.map((emoji) => (
                    <button
                      key={emoji}
                      type="button"
                      onClick={() => setIcon(emoji)}
                      className={`flex size-8 items-center justify-center rounded-lg text-base transition-transform hover:scale-110 ${
                        icon === emoji
                          ? "bg-primary/20 ring-2 ring-primary"
                          : "bg-zinc-100/80 hover:bg-zinc-200/80 dark:bg-zinc-800/80 dark:hover:bg-zinc-700/80"
                      }`}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              </div>

              {/* Description */}
              <div className="space-y-1.5">
                <Label htmlFor="kb-desc" className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                  知识库描述（可选）
                </Label>
                <textarea
                  id="kb-desc"
                  rows={3}
                  placeholder="说明此知识库收录的文档范围、用途或核心主题..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  maxLength={500}
                  className="w-full rounded-md border border-zinc-200 bg-transparent px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary dark:border-zinc-800 dark:text-zinc-100"
                />
              </div>

              {/* Model */}
              <div className="space-y-1.5">
                <Label htmlFor="kb-model" className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                  向量嵌入模型
                </Label>
                <Input
                  id="kb-model"
                  value={embeddingModel}
                  onChange={(e) => setEmbeddingModel(e.target.value)}
                  className="h-9 font-mono text-xs text-zinc-500 dark:text-zinc-400"
                />
                <p className="text-[11px] text-zinc-400">
                  默认采用 OpenAI text-embedding-3-small（1536维高质量向量，兼顾性能与高检索召回率）。
                </p>
              </div>

              {/* Footer Actions */}
              <div className="mt-6 flex items-center justify-end gap-2.5 pt-4 border-t border-zinc-100 dark:border-zinc-800">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={onClose}
                  disabled={loading}
                >
                  取消
                </Button>
                <Button type="submit" size="sm" disabled={loading || !title.trim()}>
                  {loading && <Loader2 className="mr-1.5 size-3.5 animate-spin" />}
                  立即创建
                </Button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
