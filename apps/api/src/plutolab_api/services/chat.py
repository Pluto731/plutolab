"""RAG Chat Service with Streaming SSE and Citation Assembly (Phase 4.3.c).

Orchestrates:
- Hybrid document retrieval via HybridRetriever (Dense + Sparse + RRF)
- Structured CitationItem extraction and normalization
- RAG System Prompt construction with grounded context
- Multi-turn conversation history assembly
- LLM streaming generation (OpenAI, DeepSeek, Anthropic) with deterministic Mock fallback
- Assistant message persistence and automatic conversation title generation
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Literal
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from plutolab_api.core.crypto import decrypt
from plutolab_api.core.logging import get_logger
from plutolab_api.models.rag import RAGConversation, RAGMessage
from plutolab_api.models.user_api_key import UserApiKey
from plutolab_api.schemas.rag import (
    ChatStreamChunk,
    ChatStreamError,
    CitationItem,
    MessagePublic,
    SearchResultItem,
)
from plutolab_api.services.embedder import EmbeddingService
from plutolab_api.services.query_router import (
    QueryPlan,
    build_query_plan,
    retrieval_confidence,
    should_reflect,
)
from plutolab_api.services.retriever import HybridRetriever, SearchMode

logger = get_logger(__name__)

SYSTEM_PROMPT_TEMPLATE = """你是一个严谨专业的智能知识库问答助手。
请根据以下提供的参考文档片段回答用户问题。

回答规范：
1. 请优先基于给出的【参考文档】如实回答，回答条理清晰、专业准确。
2. 若参考文档中完全没有包含回答问题所需的信息，请诚实说明「未在知识库中找到相关信息」，严禁编造虚假事实。
3. 引用文档观点时，可以在对应句末标注角标，例如 [^1]、[^2]。

【参考文档片段】:
{context_text}
"""


class RAGChatService:
    """Coordinates retrieval, citation formatting, LLM streaming, and message persistence."""

    def __init__(
        self,
        embedder: EmbeddingService | None = None,
        retriever: HybridRetriever | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._embedder = embedder or EmbeddingService()
        self._retriever = retriever or HybridRetriever(embedder=self._embedder)
        self._http_client = http_client

    async def get_user_llm_key(self, db: AsyncSession, user_id: UUID, provider: str) -> str | None:
        """Fetch and Fernet-decrypt the user's latest API key for the requested provider."""
        stmt = (
            select(UserApiKey)
            .where(UserApiKey.user_id == user_id, UserApiKey.provider == provider)
            .order_by(UserApiKey.created_at.desc())
        )
        result = await db.execute(stmt)
        key_record = result.scalars().first()
        if key_record is None:
            return None
        try:
            ciphertext = key_record.key_ciphertext
            if not isinstance(ciphertext, bytes) or not ciphertext:
                raise ValueError("Missing or malformed ciphertext")
            key = decrypt(ciphertext)
            if not key.strip():
                raise ValueError("Stored key is empty")
            return key
        except Exception as exc:
            logger.warning(
                "rag_chat.key_decrypt_failed",
                user_id=str(user_id),
                error_type=type(exc).__name__,
            )
            raise ValueError("Stored provider API key could not be decrypted.") from exc

    def _build_context_and_citations(
        self, results: list[SearchResultItem]
    ) -> tuple[str, list[CitationItem]]:
        """Convert retrieval results into system prompt context text and structured citations."""
        citations: list[CitationItem] = []
        context_parts: list[str] = []

        for idx, res in enumerate(results, start=1):
            # Clamp similarity score to [0.0, 1.0]
            similarity = round(min(1.0, max(0.0, float(res.score))), 4)
            citation = CitationItem(
                document_id=res.document_id,
                chunk_id=res.chunk_id,
                filename=res.filename,
                chunk_index=res.chunk_index,
                content=res.content,
                similarity=similarity,
                metadata=res.metadata or {},
            )
            citations.append(citation)

            page_info = (
                f" (第 {citation.metadata.get('page_number')} 页)"
                if citation.metadata.get("page_number")
                else ""
            )
            context_parts.append(
                f"[{idx}] 来源: 《{res.filename}》{page_info}\n{res.content.strip()}"
            )

        context_text = "\n\n".join(context_parts) if context_parts else "（未检索到相关文档切片）"
        return context_text, citations

    async def _get_chat_history(
        self, db: AsyncSession, conversation_id: UUID, max_messages: int = 8
    ) -> list[dict[str, str]]:
        """Retrieve recent conversation history for multi-turn context."""
        stmt = (
            select(RAGMessage)
            .where(RAGMessage.conversation_id == conversation_id)
            .order_by(RAGMessage.created_at.desc())
            .limit(max_messages)
        )
        result = await db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()

        formatted: list[dict[str, str]] = []
        for msg in messages:
            if msg.role in {"user", "assistant"}:
                formatted.append({"role": msg.role, "content": msg.content})
        return formatted

    async def _retrieve_with_reflection(
        self,
        db: AsyncSession,
        conversation: RAGConversation,
        query: str,
        history: list[dict[str, str]],
        top_k: int,
        search_mode: SearchMode,
        api_key: str | None,
    ) -> tuple[list[SearchResultItem], QueryPlan]:
        """Run one query rewrite plus at most one bounded low-confidence retry."""
        plan = build_query_plan(query, history)
        results = await self._retriever.search(
            db=db,
            kb_id=conversation.kb_id,
            query=plan.semantic_query,
            top_k=top_k,
            mode=search_mode,
            api_key=api_key,
            vector_query=plan.semantic_query,
            fts_query=plan.keyword_query,
        )
        confidence = retrieval_confidence(results, plan.semantic_query)
        retry_performed = False

        if (
            should_reflect(results, plan.semantic_query)
            and plan.keyword_query
            and plan.keyword_query != plan.semantic_query
        ):
            retry_performed = True
            retry_results = await self._retriever.search(
                db=db,
                kb_id=conversation.kb_id,
                query=plan.keyword_query,
                top_k=top_k,
                mode=search_mode,
                api_key=api_key,
                vector_query=plan.keyword_query,
                fts_query=plan.keyword_query,
            )
            merged_results = {result.chunk_id: result for result in results}
            for result in retry_results:
                current = merged_results.get(result.chunk_id)
                if current is None or result.score > current.score:
                    merged_results[result.chunk_id] = result
            results = sorted(
                merged_results.values(), key=lambda result: result.score, reverse=True
            )[:top_k]

        logger.info(
            "agentic_retrieval_completed",
            kb_id=str(conversation.kb_id),
            confidence=confidence,
            retry_performed=retry_performed,
            semantic_query=plan.semantic_query,
            keyword_query=plan.keyword_query,
            result_count=len(results),
        )
        return results, plan

    async def _stream_mock_response(
        self, query: str, citations: list[CitationItem]
    ) -> AsyncIterator[str]:
        """Generate a deterministic streaming mock response for testing and keyless offline setups."""
        if citations:
            first_c = citations[0]
            lead = f"根据知识库文档《{first_c.filename}》的记载，"
            body = f"关于「{query}」，相关内容指出：\n\n> {first_c.content[:120]}... [^1]\n\n"
            if len(citations) > 1:
                sec_c = citations[1]
                body += f"此外，《{sec_c.filename}》还补充了以下关键点：{sec_c.content[:80]}... [^2]\n\n"
            tail = "如需了解更多细节，可点击引用角标查看原文片段高亮。"
            full_text = lead + body + tail
        else:
            full_text = f"抱歉，在当前知识库中未检索到与「{query}」明确相关的参考内容。您可以尝试补充更多背景或上传相关文档后再进行提问。"

        # Split into word/punctuation chunks to simulate real-time token stream
        words = []
        cur = ""
        for char in full_text:
            cur += char
            if char in {" ", "，", "。", "！", "？", "\n", "：", "、"} or len(cur) >= 4:
                words.append(cur)
                cur = ""
        if cur:
            words.append(cur)

        for word in words:
            yield word
            # Yield control to event loop to simulate realistic streaming
            await asyncio.sleep(0.005)

    async def _stream_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        """Stream chat completions from OpenAI or DeepSeek API."""
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.2,
        }

        client = self._http_client or httpx.AsyncClient(timeout=60.0)
        close_client = self._http_client is None

        try:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                    except json.JSONDecodeError as exc:
                        raise ValueError("Provider returned malformed streaming data") from exc
                raise ValueError("Provider stream ended before completion")
        finally:
            if close_client:
                await client.aclose()

    async def stream_chat(
        self,
        db: AsyncSession,
        conversation: RAGConversation,
        user_id: UUID,
        query: str,
        model: str = "gpt-4o-mini",
        top_k: int = 5,
        hybrid_search: bool = True,
    ) -> AsyncIterator[str]:
        """Execute RAG retrieval and stream SSE events with citations and token deltas."""
        error_code: Literal["preparation_failed", "generation_failed", "persistence_failed"] = (
            "preparation_failed"
        )
        try:
            # 1. Build conversation context and retrieve knowledge chunks
            search_mode: SearchMode = "hybrid" if hybrid_search else "vector"
            user_openai_key = await self._embedder.get_user_openai_key(db, user_id)
            history = await self._get_chat_history(db, conversation.id, max_messages=6)
            results, _query_plan = await self._retrieve_with_reflection(
                db=db,
                conversation=conversation,
                query=query,
                history=history,
                top_k=top_k,
                api_key=user_openai_key,
                search_mode=search_mode,
            )

            # 2. Build citations & prompt context
            context_text, citations = self._build_context_and_citations(results)

            # 3. Emit Citation events as first SSE messages
            for citation in citations:
                chunk_event = ChatStreamChunk(citation=citation)
                yield f"data: {chunk_event.model_dump_json()}\n\n"

            # 4. Prepare conversation prompt
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context_text=context_text)
            # Exclude the latest user message from history if already inserted
            if history and history[-1]["role"] == "user" and history[-1]["content"] == query:
                history = history[:-1]

            llm_messages = [{"role": "system", "content": system_prompt}]
            llm_messages.extend(history)
            llm_messages.append({"role": "user", "content": query})

            # 5. Resolve LLM provider & API Key
            provider = "deepseek" if "deepseek" in model.lower() else "openai"
            base_url = (
                "https://api.deepseek.com"
                if provider == "deepseek"
                else "https://api.openai.com/v1"
            )
            api_key = await self.get_user_llm_key(db, user_id, provider)

            # 6. Stream tokens (from remote LLM if key present, else deterministic mock)
            full_response_text = ""
            token_stream: AsyncIterator[str]
            if api_key:
                token_stream = self._stream_openai_compatible(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    messages=llm_messages,
                )
            else:
                token_stream = self._stream_mock_response(query, citations)

            error_code = "generation_failed"
            async for token in token_stream:
                full_response_text += token
                delta_event = ChatStreamChunk(delta=token)
                yield f"data: {delta_event.model_dump_json()}\n\n"

            # 7. Persist Assistant message before acknowledging success
            error_code = "persistence_failed"
            assistant_msg = RAGMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=full_response_text or "（无响应）",
                citations=[c.model_dump(mode="json") for c in citations],
            )
            db.add(assistant_msg)

            # Auto-title conversation if it still has default title
            if conversation.title in {"新对话", "New Chat"} and query.strip():
                clean_title = query.strip().split("\n")[0][:40]
                conversation.title = clean_title

            conversation.updated_at = func.clock_timestamp()
            await db.commit()

            # 8. Emit final termination events
            finish_event = ChatStreamChunk(finish_reason="stop")
            yield f"data: {finish_event.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("rag_chat.failed", phase=error_code, error_type=type(exc).__name__)
            try:
                await db.rollback()
            except Exception as rollback_exc:
                logger.error("rag_chat.rollback_failed", error_type=type(rollback_exc).__name__)
            messages = {
                "preparation_failed": "Unable to prepare the answer. Check your provider key and retry.",
                "generation_failed": "Answer generation was interrupted. Please retry.",
                "persistence_failed": "The answer could not be saved. Please retry.",
            }
            event = ChatStreamChunk(
                finish_reason="error",
                error=ChatStreamError(code=error_code, message=messages[error_code])
            )
            yield f"data: {event.model_dump_json()}\n\n"

    async def sync_chat(
        self,
        db: AsyncSession,
        conversation: RAGConversation,
        user_id: UUID,
        query: str,
        model: str = "gpt-4o-mini",
        top_k: int = 5,
        hybrid_search: bool = True,
    ) -> MessagePublic:
        """Execute non-streaming RAG chat and return the persisted MessagePublic."""
        # 1. Build conversation context and retrieve knowledge chunks
        search_mode: SearchMode = "hybrid" if hybrid_search else "vector"
        user_openai_key = await self._embedder.get_user_openai_key(db, user_id)
        history = await self._get_chat_history(db, conversation.id, max_messages=6)
        results, _query_plan = await self._retrieve_with_reflection(
            db=db,
            conversation=conversation,
            query=query,
            history=history,
            top_k=top_k,
            api_key=user_openai_key,
            search_mode=search_mode,
        )

        # 2. Build citations & prompt
        _context_text, citations = self._build_context_and_citations(results)

        # 3. Simulate or generate full response
        response_parts = []
        async for token in self._stream_mock_response(query, citations):
            response_parts.append(token)
        full_content = "".join(response_parts)

        # 4. Save Assistant message
        assistant_msg = RAGMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=full_content,
            citations=[c.model_dump(mode="json") for c in citations],
        )
        db.add(assistant_msg)

        if conversation.title in {"新对话", "New Chat"} and query.strip():
            conversation.title = query.strip().split("\n")[0][:40]

        conversation.updated_at = func.clock_timestamp()
        await db.commit()
        await db.refresh(assistant_msg)

        return MessagePublic(
            id=assistant_msg.id,
            conversation_id=assistant_msg.conversation_id,
            role="assistant",
            content=assistant_msg.content,
            citations=citations,
            created_at=assistant_msg.created_at,
        )
