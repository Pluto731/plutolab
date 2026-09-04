/**
 * PlutoLab RAG Client & TypeScript Contracts (Phase 4.4.a).
 *
 * Provides complete type safety and API caller methods for:
 * - Knowledge Base CRUD
 * - Multi-file async upload & note batch import
 * - Document polling and deletion
 * - Hybrid vector + FTS search
 * - Conversation management (thread listing, details, renaming, cascade delete)
 * - Browser-native SSE typewriter streaming with Citation event extraction
 */

import { API_URL } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

// --- Enums & Literals ---

export type DocumentStatus = "pending" | "parsing" | "ready" | "failed";
export type DocumentFileType = "md" | "pdf" | "docx" | "txt" | "note";
export type DocumentSourceType = "upload" | "note";
export type MessageRole = "user" | "assistant" | "system";
export type RetrievalSource = "vector" | "fts" | "hybrid";
export type SearchMode = "vector" | "fts" | "hybrid";

// --- Citation & Search Types ---

export interface CitationItem {
  document_id: string;
  chunk_id: string;
  filename: string;
  chunk_index: number;
  content: string;
  similarity: number;
  metadata: Record<string, any>;
}

export interface SearchResultItem {
  chunk_id: string;
  document_id: string;
  filename: string;
  chunk_index: number;
  content: string;
  score: number;
  retrieval_source: RetrievalSource;
  metadata: Record<string, any>;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  mode?: SearchMode;
  vector_weight?: number;
  fts_weight?: number;
}

// --- Knowledge Base Types ---

export interface KnowledgeBaseCreate {
  title: string;
  description?: string | null;
  icon?: string | null;
  embedding_model?: string;
}

export interface KnowledgeBaseUpdate {
  title?: string | null;
  description?: string | null;
  icon?: string | null;
  embedding_model?: string | null;
}

export interface KnowledgeBasePublic {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  icon: string | null;
  embedding_model: string;
  created_at: string;
  updated_at: string;
  doc_count: number;
  char_count: number;
  chunk_count: number;
}

export interface KnowledgeBaseSummary {
  id: string;
  title: string;
  description: string | null;
  icon: string | null;
  embedding_model: string;
  doc_count: number;
  char_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

// --- Document Types ---

export interface DocumentPublic {
  id: string;
  kb_id: string;
  source_note_id: string | null;
  filename: string;
  file_type: DocumentFileType;
  source_type: DocumentSourceType;
  char_count: number;
  chunk_count: number;
  status: DocumentStatus;
  error_message: string | null;
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface DocumentImportNoteRequest {
  note_ids: string[];
}

// --- Conversation & Message Types ---

export interface ConversationCreate {
  title?: string;
}

export interface ConversationUpdate {
  title: string;
}

export interface MessageCreate {
  content: string;
  model?: string;
  stream?: boolean;
  top_k?: number;
  hybrid_search?: boolean;
}

export interface MessagePublic {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  citations: CitationItem[];
  created_at: string;
}

export interface ConversationPublic {
  id: string;
  kb_id: string;
  title: string;
  messages: MessagePublic[];
  created_at: string;
  updated_at: string;
}

export interface ConversationSummary {
  id: string;
  kb_id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatStreamChunk {
  delta?: string;
  citation?: CitationItem | null;
  finish_reason?: string | null;
}

export interface StreamCallbacks {
  onCitation?: (citation: CitationItem) => void;
  onDelta?: (delta: string) => void;
  onDone?: () => void;
  onError?: (err: Error) => void;
}

// --- Internal Auth & Error Helpers ---

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  const base: Record<string, string> = { "Content-Type": "application/json" };
  if (token) base.Authorization = `Bearer ${token}`;
  return base;
}

function detailMessage(data: unknown, fallback: string): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : fallback;
}

// --- Knowledge Base API Calls ---

export async function listKnowledgeBases(): Promise<KnowledgeBaseSummary[]> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to list knowledge bases (${res.status})`);
  return res.json() as Promise<KnowledgeBaseSummary[]>;
}

export async function getKnowledgeBase(kbId: string): Promise<KnowledgeBasePublic> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Knowledge base not found (${res.status})`);
  return res.json() as Promise<KnowledgeBasePublic>;
}

export async function createKnowledgeBase(
  payload: KnowledgeBaseCreate
): Promise<KnowledgeBasePublic> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(detailMessage(errorData, `Create knowledge base failed (${res.status})`));
  }
  return res.json() as Promise<KnowledgeBasePublic>;
}

export async function updateKnowledgeBase(
  kbId: string,
  payload: KnowledgeBaseUpdate
): Promise<KnowledgeBasePublic> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(detailMessage(errorData, `Update knowledge base failed (${res.status})`));
  }
  return res.json() as Promise<KnowledgeBasePublic>;
}

export async function deleteKnowledgeBase(kbId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Delete knowledge base failed (${res.status})`);
}

// --- Document Operations ---

export async function uploadDocuments(
  kbId: string,
  files: File[]
): Promise<DocumentPublic[]> {
  const token = getAccessToken();
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}/documents/upload`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(detailMessage(errorData, `Upload documents failed (${res.status})`));
  }
  return res.json() as Promise<DocumentPublic[]>;
}

export async function importNotesToKnowledgeBase(
  kbId: string,
  noteIds: string[]
): Promise<DocumentPublic[]> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}/documents/import-notes`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ note_ids: noteIds }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(detailMessage(errorData, `Import notes failed (${res.status})`));
  }
  return res.json() as Promise<DocumentPublic[]>;
}

export async function listDocuments(
  kbId: string,
  statusFilter?: DocumentStatus
): Promise<DocumentPublic[]> {
  const qs = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}/documents${qs}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`List documents failed (${res.status})`);
  return res.json() as Promise<DocumentPublic[]>;
}

export async function getDocument(kbId: string, docId: string): Promise<DocumentPublic> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}/documents/${docId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Get document failed (${res.status})`);
  return res.json() as Promise<DocumentPublic>;
}

export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}/documents/${docId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Delete document failed (${res.status})`);
}

export async function searchKnowledgeBase(
  kbId: string,
  payload: SearchRequest
): Promise<SearchResultItem[]> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}/search`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Search knowledge base failed (${res.status})`);
  return res.json() as Promise<SearchResultItem[]>;
}

// --- Conversation Management ---

export async function listConversations(kbId: string): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}/conversations`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`List conversations failed (${res.status})`);
  return res.json() as Promise<ConversationSummary[]>;
}

export async function getConversation(conversationId: string): Promise<ConversationPublic> {
  const res = await fetch(`${API_URL}/api/v1/rag/conversations/${conversationId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Get conversation failed (${res.status})`);
  return res.json() as Promise<ConversationPublic>;
}

export async function createConversation(
  kbId: string,
  payload?: ConversationCreate
): Promise<ConversationPublic> {
  const res = await fetch(`${API_URL}/api/v1/rag/knowledge-bases/${kbId}/conversations`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload ?? {}),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(detailMessage(errorData, `Create conversation failed (${res.status})`));
  }
  return res.json() as Promise<ConversationPublic>;
}

export async function updateConversation(
  conversationId: string,
  payload: ConversationUpdate
): Promise<ConversationPublic> {
  const res = await fetch(`${API_URL}/api/v1/rag/conversations/${conversationId}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(detailMessage(errorData, `Update conversation failed (${res.status})`));
  }
  return res.json() as Promise<ConversationPublic>;
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/rag/conversations/${conversationId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`Delete conversation failed (${res.status})`);
}

// --- Synchronous & Streaming Chat Calls ---

export async function sendSyncMessage(
  conversationId: string,
  payload: Omit<MessageCreate, "stream">
): Promise<MessagePublic> {
  const res = await fetch(`${API_URL}/api/v1/rag/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ ...payload, stream: false }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw new Error(detailMessage(errorData, `Send message failed (${res.status})`));
  }
  return res.json() as Promise<MessagePublic>;
}

export async function streamRAGMessage(
  conversationId: string,
  payload: MessageCreate,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const headers = authHeaders();
  const res = await fetch(`${API_URL}/api/v1/rag/conversations/${conversationId}/messages`, {
    method: "POST",
    headers,
    body: JSON.stringify({ ...payload, stream: true }),
    signal,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    const msg = detailMessage(errorData, `HTTP ${res.status}: ${res.statusText}`);
    const err = new Error(msg);
    callbacks.onError?.(err);
    throw err;
  }

  if (!res.body) {
    const err = new Error("Response body is null or streaming unsupported");
    callbacks.onError?.(err);
    throw err;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;

        const dataStr = trimmed.slice(5).trim();
        if (dataStr === "[DONE]") {
          callbacks.onDone?.();
          return;
        }

        try {
          const chunk = JSON.parse(dataStr) as ChatStreamChunk;
          if (chunk.citation) {
            callbacks.onCitation?.(chunk.citation);
          }
          if (chunk.delta) {
            callbacks.onDelta?.(chunk.delta);
          }
        } catch {
          // Ignore malformed partial chunks
        }
      }
    }

    if (buffer.trim().startsWith("data:")) {
      const dataStr = buffer.trim().slice(5).trim();
      if (dataStr === "[DONE]") {
        callbacks.onDone?.();
        return;
      }
    }

    callbacks.onDone?.();
  } catch (error: any) {
    if (error?.name === "AbortError") {
      return;
    }
    callbacks.onError?.(error instanceof Error ? error : new Error(String(error)));
    throw error;
  } finally {
    reader.releaseLock();
  }
}
