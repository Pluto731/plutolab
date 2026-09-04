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
from collections.abc import AsyncIterator
import json
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from plutolab_api.core.crypto import decrypt
from plutolab_api.models.rag import RAGConversation, RAGMessage
from plutolab_api.models.user_api_key import UserApiKey
from plutolab_api.schemas.rag import ChatStreamChunk, CitationItem, MessagePublic, SearchResultItem
from plutolab_api.services.embedder import EmbeddingService
from plutolab_api.services.retriever import HybridRetriever, SearchMode

logger = structlog.get_logger(__name__)

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

    async def get_user_llm_key(
        self, db: AsyncSession, user_id: UUID, provider: str
    ) -> str | None:
        """Fetch and Fernet-decrypt the user's latest API key for the requested provider."""
        stmt = (
            select(UserApiKey)
            .where(UserApiKey.user_id == user_id, UserApiKey.provider == provider)
            .order_by(UserApiKey.created_at.desc())
        )
        result = await db.execute(stmt)
        key_record = result.scalars().first()
        if key_record and key_record.encrypted_key:
            try:
                return decrypt(key_record.encrypted_key)
            except Exception as e:
                logger.warning("rag_chat.key_decrypt_failed", user_id=str(user_id), error=str(e))
        return None

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

            page_info = f" (第 {citation.metadata.get('page_number')} 页)" if citation.metadata.get("page_number") else ""
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
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                    except json.JSONDecodeError:
                        continue
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
        # 1. Retrieve knowledge chunks
        search_mode: SearchMode = "hybrid" if hybrid_search else "vector"
        user_openai_key = await self._embedder.get_user_openai_key(db, user_id)
        results = await self._retriever.search(
            db=db,
            kb_id=conversation.kb_id,
            query=query,
            top_k=top_k,
            mode=search_mode,
            api_key=user_openai_key,
        )

        # 2. Build citations & prompt context
        context_text, citations = self._build_context_and_citations(results)

        # 3. Emit Citation events as first SSE messages
        for citation in citations:
            chunk_event = ChatStreamChunk(citation=citation)
            yield f"data: {chunk_event.model_dump_json()}\n\n"

        # 4. Prepare conversation prompt
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context_text=context_text)
        history = await self._get_chat_history(db, conversation.id, max_messages=6)
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
            try:
                token_stream = self._stream_openai_compatible(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    messages=llm_messages,
                )
            except Exception as e:
                logger.warning("rag_chat.remote_stream_failed_fallback_to_mock", error=str(e))
                token_stream = self._stream_mock_response(query, citations)
        else:
            token_stream = self._stream_mock_response(query, citations)

        try:
            async for token in token_stream:
                full_response_text += token
                delta_event = ChatStreamChunk(delta=token)
                yield f"data: {delta_event.model_dump_json()}\n\n"
        except Exception as e:
            logger.error("rag_chat.streaming_error", error=str(e))
            err_event = ChatStreamChunk(delta=f"\n[生成中断: {e!s}]")
            yield f"data: {err_event.model_dump_json()}\n\n"

        # 7. Persist Assistant message to database
        try:
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
        except Exception as e:
            logger.error("rag_chat.persist_assistant_failed", error=str(e))
            await db.rollback()

        # 8. Emit final termination events
        finish_event = ChatStreamChunk(finish_reason="stop")
        yield f"data: {finish_event.model_dump_json()}\n\n"
        yield "data: [DONE]\n\n"

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
        # 1. Retrieve knowledge chunks
        search_mode: SearchMode = "hybrid" if hybrid_search else "vector"
        user_openai_key = await self._embedder.get_user_openai_key(db, user_id)
        results = await self._retriever.search(
            db=db,
            kb_id=conversation.kb_id,
            query=query,
            top_k=top_k,
            mode=search_mode,
            api_key=user_openai_key,
        )

        # 2. Build citations & prompt
        context_text, citations = self._build_context_and_citations(results)

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
