"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  BookOpen,
  FolderPlus,
  Loader2,
  Plus,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
  type KnowledgeBaseCreate,
  type KnowledgeBaseSummary,
} from "@/lib/rag";

import { CreateKnowledgeBaseDialog } from "./components/create-kb-dialog";
import { KBStatsBanner } from "./components/kb-stats-banner";
import { KnowledgeBaseCard } from "./components/knowledge-base-card";

export default function RAGKnowledgeBasesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user, loading: authLoading, mounted } = useAuthUser();

  const [searchQuery, setSearchQuery] = useState("");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Authentication check
  useEffect(() => {
    if (mounted && !authLoading && !user) {
      router.replace("/login");
    }
  }, [mounted, authLoading, user, router]);

  // Query Knowledge Bases
  const {
    data: knowledgeBases = [],
    isLoading,
    isError,
    error,
  } = useQuery<KnowledgeBaseSummary[]>({
    queryKey: ["knowledge-bases"],
    queryFn: listKnowledgeBases,
    enabled: !!user,
    staleTime: 10 * 1000,
  });

  // Create Mutation
  const createMutation = useMutation({
    mutationFn: (payload: KnowledgeBaseCreate) => createKnowledgeBase(payload),
    onSuccess: (newKb) => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
      // Redirect to the newly created KB detail page
      router.push(`/rag/${newKb.id}`);
    },
  });

  // Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteKnowledgeBase(id),
    onMutate: (id) => setDeletingId(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
    },
    onSettled: () => setDeletingId(null),
  });

  const handleDelete = (id: string, title: string) => {
    if (window.confirm(`确定要删除知识库「${title}」吗？\n删除后该库下的所有文档、分块和对话历史都将被永久物理删除！`)) {
      deleteMutation.mutate(id);
    }
  };

  // Filtered KBs
  const filteredKBs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return knowledgeBases;
    return knowledgeBases.filter(
      (kb) =>
        kb.title.toLowerCase().includes(q) ||
        (kb.description && kb.description.toLowerCase().includes(q))
    );
  }, [knowledgeBases, searchQuery]);

  return (
    <div className="mx-auto max-w-7xl space-y-8 px-4 py-8 sm:px-6 lg:px-8">
      {/* Top Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-primary text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="size-3.5" />
            <span>Phase 4 · RAG 知识中枢</span>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-3xl">
            智能文档知识库
          </h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            上传文档构建私有语义索引，支持多格式切片、向量检索与精准原文角标溯源。
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            onClick={() => setCreateDialogOpen(true)}
            className="flex items-center gap-1.5 shadow-sm"
          >
            <Plus className="size-4" />
            <span>新建知识库</span>
          </Button>
        </div>
      </div>

      {/* Global Stats Indicator Banner */}
      {!isLoading && knowledgeBases.length > 0 && (
        <KBStatsBanner knowledgeBases={knowledgeBases} />
      )}

      {/* Search & Filter Row */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-400" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索知识库名称或描述..."
            className="pl-9 h-9 text-sm bg-white/50 backdrop-blur-md dark:bg-zinc-900/50"
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

        <div className="text-xs text-zinc-400 shrink-0">
          共 {filteredKBs.length} 个知识库
        </div>
      </div>

      {/* Content Area */}
      {isLoading ? (
        /* Loading Skeleton Grid */
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="rounded-2xl border border-zinc-200/60 bg-white/40 p-5 backdrop-blur-md dark:border-white/[0.05] dark:bg-zinc-900/30 space-y-4"
            >
              <div className="flex items-center gap-3">
                <Skeleton className="size-11 rounded-xl" />
                <div className="space-y-1.5 flex-1">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
              <Skeleton className="h-10 w-full" />
              <div className="grid grid-cols-3 gap-2">
                <Skeleton className="h-12 w-full rounded-lg" />
                <Skeleton className="h-12 w-full rounded-lg" />
                <Skeleton className="h-12 w-full rounded-lg" />
              </div>
            </div>
          ))}
        </div>
      ) : isError ? (
        /* Error State */
        <div className="rounded-2xl border border-destructive/20 bg-destructive/5 p-8 text-center">
          <div className="text-sm font-medium text-destructive">
            加载知识库失败：{error instanceof Error ? error.message : "未知错误"}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] })}
            className="mt-4"
          >
            重试
          </Button>
        </div>
      ) : filteredKBs.length === 0 ? (
        /* Empty State */
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-200/80 bg-white/40 py-16 px-4 text-center backdrop-blur-md dark:border-white/[0.08] dark:bg-zinc-900/20">
          <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-4">
            <BookOpen className="size-7" />
          </div>
          <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            {searchQuery ? "未找到匹配的知识库" : "尚未创建任何知识库"}
          </h3>
          <p className="mt-1.5 max-w-sm text-xs text-zinc-500 dark:text-zinc-400">
            {searchQuery
              ? "您可以尝试更改搜索关键词，或清除筛选条件。"
              : "知识库用于归类管理您的特定业务领域文档，立即创建属于您的第一个私有知识空间。"}
          </p>
          <Button
            onClick={() => setCreateDialogOpen(true)}
            size="sm"
            className="mt-5 flex items-center gap-1.5"
          >
            <FolderPlus className="size-4" />
            <span>创建第一个知识库</span>
          </Button>
        </div>
      ) : (
        /* Cards Grid */
        <motion.div
          layout
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <AnimatePresence>
            {filteredKBs.map((kb) => (
              <KnowledgeBaseCard
                key={kb.id}
                kb={kb}
                onDelete={handleDelete}
                isDeleting={deletingId === kb.id}
              />
            ))}
          </AnimatePresence>
        </motion.div>
      )}

      {/* Create Dialog Modal */}
      <CreateKnowledgeBaseDialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        onSubmit={async (payload) => {
          await createMutation.mutateAsync(payload);
        }}
      />
    </div>
  );
}
