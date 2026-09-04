/**
 * PlutoLab RAG Domain TypeScript Contracts (Phase 4.4.a).
 * Strict 1:1 mapping with backend Pydantic models (plutolab_api.schemas.rag).
 */

export type DocumentStatus = "pending" | "parsing" | "ready" | "failed";
export type DocumentFileType = "md" | "pdf" | "docx" | "txt" | "note";
export type DocumentSourceType = "upload" | "note";
export type MessageRole = "user" | "assistant" | "system";
export type RetrievalSource = "vector" | "fts" | "hybrid";
export type SearchMode = "vector" | "fts" | "hybrid";

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
