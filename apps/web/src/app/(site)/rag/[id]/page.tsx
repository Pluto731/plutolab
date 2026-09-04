"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import {
  deleteDocument,
  getKnowledgeBase,
  listDocuments,
  type DocumentPublic,
  type KnowledgeBasePublic,
} from "@/lib/rag";

import { DocumentTable } from "./components/document-table";
import { DocumentUploadZone } from "./components/document-upload-zone";
import { KBHeader } from "./components/kb-header";

export default function KnowledgeBaseDetailPage() {
  const router = useRouter();
  const params = useParams();
  const kbId = (params?.id as string) || "";
  const queryClient = useQueryClient();
  const { user, loading: authLoading, mounted } = useAuthUser();

  const [importModalOpen, setImportModalOpen] = useState(false);

  // Authentication check
  useEffect(() => {
    if (mounted && !authLoading && !user) {
      router.replace("/login");
    }
  }, [mounted, authLoading, user, router]);

  // Query Knowledge Base Details
  const {
    data: kb,
    isLoading: kbLoading,
    isError: kbError,
    error: kbErrorObj,
  } = useQuery<KnowledgeBasePublic>({
    queryKey: ["kb", kbId],
    queryFn: () => getKnowledgeBase(kbId),
    enabled: !!user && !!kbId,
    staleTime: 10 * 1000,
  });

  // Query Documents with Dynamic Auto-Polling
  const {
    data: documents = [],
    isLoading: docsLoading,
    refetch: refetchDocs,
  } = useQuery<DocumentPublic[]>({
    queryKey: ["kb-documents", kbId],
    queryFn: () => listDocuments(kbId),
    enabled: !!user && !!kbId,
    // Dynamic polling: poll every 2s while any document is in pending or parsing status
    refetchInterval: (query) => {
      const docs = query.state.data;
      if (!docs || docs.length === 0) return false;
      const hasProcessing = docs.some(
        (d) => d.status === "pending" || d.status === "parsing"
      );
      return hasProcessing ? 2000 : false;
    },
  });

  // Whenever documents transition or finish processing, keep KB summary in sync
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.status === "pending" || d.status === "parsing"
    );
    if (!hasProcessing && documents.length > 0) {
      // Invalidate KB metadata to reflect updated char_count, chunk_count, doc_count
      queryClient.invalidateQueries({ queryKey: ["kb", kbId] });
    }
  }, [documents, kbId, queryClient]);

  // Delete Document Mutation
  const deleteMutation = useMutation({
    mutationFn: (docId: string) => deleteDocument(kbId, docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["kb-documents", kbId] });
      queryClient.invalidateQueries({ queryKey: ["kb", kbId] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
    },
  });

  const handleDeleteDocument = async (docId: string) => {
    await deleteMutation.mutateAsync(docId);
  };

  const handleUploadSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ["kb-documents", kbId] });
    queryClient.invalidateQueries({ queryKey: ["kb", kbId] });
    queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
  };

  if (!mounted || authLoading || (kbLoading && !kb)) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3">
        <Loader2 className="size-8 animate-spin text-primary" />
        <p className="text-xs text-zinc-400">正在加载知识库资料...</p>
      </div>
    );
  }

  if (kbError || !kb) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <div className="rounded-2xl border border-destructive/20 bg-destructive/5 p-8">
          <h2 className="text-base font-semibold text-destructive">
            知识库未找到或加载失败
          </h2>
          <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
            {kbErrorObj instanceof Error
              ? kbErrorObj.message
              : "未能找到指定 ID 的知识库，可能已被删除或权限不足。"}
          </p>
          <div className="mt-6 flex justify-center">
            <Link href="/rag">
              <Button variant="outline" size="sm" className="flex items-center gap-1.5">
                <ArrowLeft className="size-3.5" />
                <span>返回知识库列表</span>
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6 lg:px-8">
      {/* KB Header */}
      <KBHeader
        kb={kb}
        onOpenImportModal={() => setImportModalOpen(true)}
      />

      {/* Document Upload Zone */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          上传资料文件
        </h3>
        <DocumentUploadZone
          kbId={kbId}
          onUploadSuccess={handleUploadSuccess}
        />
      </div>

      {/* Document Real-Time Status Table */}
      <DocumentTable
        documents={documents}
        isLoading={docsLoading}
        onDeleteDocument={handleDeleteDocument}
        onOpenImportModal={() => setImportModalOpen(true)}
      />

      {/* Placeholder note import prompt modal for 4.4.d */}
      {importModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-6 shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-center gap-2 text-primary font-semibold text-sm">
              <BookOpen className="size-4" />
              <span>导入 Markdown 笔记</span>
            </div>
            <p className="mt-3 text-xs text-zinc-600 dark:text-zinc-300 leading-relaxed">
              笔记多选导入模态框将在下一微切片 (Phase 4.4.d) 中完整实现。您可以先通过上方的拖拽上传区域上传本地 Markdown (.md)、文本 (.txt)、PDF (.pdf) 或 Word (.docx) 文档。
            </p>
            <div className="mt-5 flex justify-end">
              <Button size="sm" onClick={() => setImportModalOpen(false)}>
                知道了
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
