"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import React, { useEffect, useState } from "react";

import { useAuthUser } from "@/components/auth/use-auth";
import { Button } from "@/components/ui/button";
import {
  createConversation,
  deleteConversation,
  getConversation,
  getKnowledgeBase,
  listConversations,
  sendSyncMessage,
  updateConversation,
  type ConversationPublic,
  type ConversationSummary,
  type KnowledgeBasePublic,
} from "@/lib/rag";

import { ChatHeader } from "./components/chat-header";
import { ChatInput } from "./components/chat-input";
import { ChatMessages } from "./components/chat-messages";
import { ConversationSidebar } from "./components/conversation-sidebar";

export default function RAGChatPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const kbId = (params?.id as string) || "";
  const queryConversationId = searchParams.get("c");

  const queryClient = useQueryClient();
  const { user, loading: authLoading, mounted } = useAuthUser();

  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    queryConversationId
  );
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isSending, setIsSending] = useState(false);

  // Authentication check
  useEffect(() => {
    if (mounted && !authLoading && !user) {
      router.replace("/login");
    }
  }, [mounted, authLoading, user, router]);

  // Query Knowledge Base info
  const {
    data: kb,
    isLoading: kbLoading,
    isError: kbError,
    error: kbErrorObj,
  } = useQuery<KnowledgeBasePublic>({
    queryKey: ["kb", kbId],
    queryFn: () => getKnowledgeBase(kbId),
    enabled: !!user && !!kbId,
    staleTime: 60 * 1000,
  });

  // Query Conversations List
  const {
    data: conversations = [],
    isLoading: convsLoading,
  } = useQuery<ConversationSummary[]>({
    queryKey: ["kb-conversations", kbId],
    queryFn: () => listConversations(kbId),
    enabled: !!user && !!kbId,
    staleTime: 10 * 1000,
  });

  // Automatically select the most recent conversation if none is selected
  useEffect(() => {
    if (conversations.length > 0) {
      if (!activeConversationId || !conversations.some((c) => c.id === activeConversationId)) {
        setActiveConversationId(conversations[0].id);
      }
    }
  }, [conversations, activeConversationId]);

  // Query Active Conversation Detail
  const {
    data: activeConversation,
    isLoading: activeConvLoading,
  } = useQuery<ConversationPublic>({
    queryKey: ["conversation", activeConversationId],
    queryFn: () => getConversation(activeConversationId!),
    enabled: !!user && !!activeConversationId,
  });

  // Select conversation & sync URL query
  const handleSelectConversation = (id: string) => {
    setActiveConversationId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("c", id);
    window.history.replaceState({}, "", url.toString());
  };

  // Create Conversation Mutation
  const createMutation = useMutation({
    mutationFn: () => createConversation(kbId, { title: "新会话" }),
    onSuccess: (newConv) => {
      queryClient.invalidateQueries({ queryKey: ["kb-conversations", kbId] });
      handleSelectConversation(newConv.id);
    },
  });

  // Rename Conversation Mutation
  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      updateConversation(id, { title }),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["kb-conversations", kbId] });
      queryClient.invalidateQueries({ queryKey: ["conversation", vars.id] });
    },
  });

  // Delete Conversation Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["kb-conversations", kbId] });
      if (activeConversationId === deletedId) {
        const remaining = conversations.filter((c) => c.id !== deletedId);
        if (remaining.length > 0) {
          handleSelectConversation(remaining[0].id);
        } else {
          setActiveConversationId(null);
        }
      }
    },
  });

  // Send message mutation (synchronous fallback for 4.5.a, streaming will be added in 4.5.b)
  const handleSendMessage = async (content: string) => {
    let convId = activeConversationId;

    // If no conversation exists yet, automatically create one first
    if (!convId) {
      try {
        const created = await createMutation.mutateAsync();
        convId = created.id;
      } catch (err) {
        console.error("Failed to auto-create conversation", err);
        return;
      }
    }

    try {
      setIsSending(true);
      await sendSyncMessage(convId, { content });
      queryClient.invalidateQueries({ queryKey: ["conversation", convId] });
      queryClient.invalidateQueries({ queryKey: ["kb-conversations", kbId] });
    } catch (err) {
      console.error("Failed to send message", err);
    } finally {
      setIsSending(false);
    }
  };

  if (!mounted || authLoading || (kbLoading && !kb)) {
    return (
      <div className="flex h-[80vh] flex-col items-center justify-center gap-3">
        <Loader2 className="size-8 animate-spin text-primary" />
        <p className="text-xs text-zinc-400">正在载入知识库对话工作台...</p>
      </div>
    );
  }

  if (kbError || !kb) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <div className="rounded-2xl border border-destructive/20 bg-destructive/5 p-8">
          <h3 className="text-base font-semibold text-destructive">知识库未找到</h3>
          <p className="mt-2 text-xs text-zinc-500">
            {kbErrorObj instanceof Error ? kbErrorObj.message : "知识库不存在或无访问权限"}
          </p>
          <div className="mt-5">
            <Link href="/rag">
              <Button size="sm" variant="outline">
                <ArrowLeft className="size-3.5 mr-1.5" />
                返回列表
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)] md:h-[100dvh] overflow-hidden bg-zinc-50/50 dark:bg-zinc-950/50">
      {/* Left Double-Column: Conversation Tree Sidebar */}
      <ConversationSidebar
        kb={kb}
        conversations={conversations}
        selectedId={activeConversationId}
        onSelect={handleSelectConversation}
        onCreate={async () => {
          await createMutation.mutateAsync();
        }}
        onRename={async (id, title) => {
          await renameMutation.mutateAsync({ id, title });
        }}
        onDelete={async (id) => {
          await deleteMutation.mutateAsync(id);
        }}
        isCreating={createMutation.isPending}
        isOpenMobile={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />

      {/* Right Column: Chat Workspace Main Area */}
      <main className="flex flex-1 flex-col overflow-hidden min-w-0 bg-transparent">
        {/* Workspace Header */}
        <ChatHeader
          kb={kb}
          conversation={activeConversation}
          onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
        />

        {/* Message Stream Viewport */}
        <ChatMessages
          kb={kb}
          conversation={activeConversation || null}
          isLoading={activeConvLoading}
          onSendPresetQuery={handleSendMessage}
        />

        {/* Bottom Input Area */}
        <ChatInput
          onSend={handleSendMessage}
          isLoading={isSending}
        />
      </main>
    </div>
  );
}
