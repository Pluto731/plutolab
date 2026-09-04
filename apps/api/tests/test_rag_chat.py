"""Integration tests for RAG conversation management and streaming SSE chat (Phase 4.3.c)."""

import json
from uuid import uuid4

from httpx import AsyncClient
import pytest

REGISTER = "/api/v1/auth/register"
RAG_KB = "/api/v1/rag/knowledge-bases"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(REGISTER, json={"email": email, "password": "supersecretpassword123"})
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestRAGConversationAndChat:
    async def test_conversation_lifecycle_and_listing(self, client: AsyncClient) -> None:
        """Test conversation creation, listing, updating, and cascade deletion."""
        h = await _auth(client, "chat_user_1@example.com")

        # 1. Create Knowledge Base
        kb_resp = await client.post(RAG_KB, headers=h, json={"title": "量子物理库"})
        assert kb_resp.status_code == 201
        kb_id = kb_resp.json()["id"]

        # 2. Create conversation 1 with custom title
        c1_resp = await client.post(
            f"{RAG_KB}/{kb_id}/conversations",
            headers=h,
            json={"title": "量子纠缠研究讨论"},
        )
        assert c1_resp.status_code == 201
        c1 = c1_resp.json()
        assert c1["title"] == "量子纠缠研究讨论"
        assert c1["kb_id"] == kb_id
        assert c1["messages"] == []
        c1_id = c1["id"]

        # 3. Create conversation 2 with default title
        c2_resp = await client.post(
            f"{RAG_KB}/{kb_id}/conversations",
            headers=h,
            json={},
        )
        assert c2_resp.status_code == 201
        assert c2_resp.json()["title"] == "新对话"

        # 4. List conversations
        list_resp = await client.get(f"{RAG_KB}/{kb_id}/conversations", headers=h)
        assert list_resp.status_code == 200
        summaries = list_resp.json()
        assert len(summaries) == 2
        titles = [s["title"] for s in summaries]
        assert "量子纠缠研究讨论" in titles
        assert "新对话" in titles
        assert summaries[0]["message_count"] == 0

        # 5. Get conversation detail
        get_resp = await client.get(f"/api/v1/rag/conversations/{c1_id}", headers=h)
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "量子纠缠研究讨论"

        # 6. Update conversation title
        patch_resp = await client.patch(
            f"/api/v1/rag/conversations/{c1_id}",
            headers=h,
            json={"title": "量子纠缠实验最新进展"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["title"] == "量子纠缠实验最新进展"

        # 7. Delete conversation
        del_resp = await client.delete(f"/api/v1/rag/conversations/{c1_id}", headers=h)
        assert del_resp.status_code == 204

        # 8. Verify 404 after deletion
        get_again = await client.get(f"/api/v1/rag/conversations/{c1_id}", headers=h)
        assert get_again.status_code == 404

    async def test_conversation_multi_tenant_isolation(self, client: AsyncClient) -> None:
        """Test multi-tenant authorization security: users cannot access each other's conversations."""
        h_alice = await _auth(client, "alice_chat@example.com")
        h_bob = await _auth(client, "bob_chat@example.com")

        # Alice creates KB and conversation
        kb_resp = await client.post(RAG_KB, headers=h_alice, json={"title": "Alice 的机密库"})
        alice_kb_id = kb_resp.json()["id"]

        conv_resp = await client.post(
            f"{RAG_KB}/{alice_kb_id}/conversations",
            headers=h_alice,
            json={"title": "Alice 对话"},
        )
        alice_conv_id = conv_resp.json()["id"]

        # Bob tries to access Alice's conversation resources -> all 404
        assert (await client.get(f"{RAG_KB}/{alice_kb_id}/conversations", headers=h_bob)).status_code == 404
        assert (await client.get(f"/api/v1/rag/conversations/{alice_conv_id}", headers=h_bob)).status_code == 404
        assert (await client.patch(f"/api/v1/rag/conversations/{alice_conv_id}", headers=h_bob, json={"title": "黑客入侵"})).status_code == 404
        assert (await client.delete(f"/api/v1/rag/conversations/{alice_conv_id}", headers=h_bob)).status_code == 404
        assert (await client.post(f"/api/v1/rag/conversations/{alice_conv_id}/messages", headers=h_bob, json={"content": "非法提问"})).status_code == 404

    async def test_sync_chat_with_citations(self, client: AsyncClient) -> None:
        """Test sending message with stream=False returning synchronous MessagePublic with citations."""
        h = await _auth(client, "sync_chat_user@example.com")

        # 1. Create KB and upload document
        kb_resp = await client.post(RAG_KB, headers=h, json={"title": "分布式系统库"})
        kb_id = kb_resp.json()["id"]

        files = [
            (
                "files",
                (
                    "distributed_db.md",
                    b"# Distributed DB\n\nDistributed database uses Raft consensus protocol to ensure multi-replica strong consistency.",
                    "text/markdown",
                ),
            )
        ]
        upload_resp = await client.post(f"{RAG_KB}/{kb_id}/documents/upload", headers=h, files=files)
        assert upload_resp.status_code == 202

        # 2. Create conversation
        conv_resp = await client.post(f"{RAG_KB}/{kb_id}/conversations", headers=h, json={"title": "新对话"})
        conv_id = conv_resp.json()["id"]

        # 3. Send message with stream=False
        msg_resp = await client.post(
            f"/api/v1/rag/conversations/{conv_id}/messages",
            headers=h,
            json={
                "content": "分布式数据库如何保障多副本一致性？",
                "stream": False,
                "top_k": 3,
                "hybrid_search": True,
            },
        )
        assert msg_resp.status_code == 200
        msg_data = msg_resp.json()
        assert msg_data["role"] == "assistant"
        assert len(msg_data["citations"]) >= 1
        first_citation = msg_data["citations"][0]
        assert first_citation["filename"] == "distributed_db.md"
        assert first_citation["similarity"] > 0

        # 4. Verify message history in conversation detail
        conv_detail = await client.get(f"/api/v1/rag/conversations/{conv_id}", headers=h)
        assert conv_detail.status_code == 200
        history = conv_detail.json()["messages"]
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    async def test_stream_chat_sse_protocol(self, client: AsyncClient) -> None:
        """Test sending message with stream=True returning SSE stream with Citation and delta packets."""
        h = await _auth(client, "sse_chat_user@example.com")

        # 1. Create KB and upload document
        kb_resp = await client.post(RAG_KB, headers=h, json={"title": "天文学知识库"})
        kb_id = kb_resp.json()["id"]

        files = [
            (
                "files",
                (
                    "astronomy.md",
                    b"# Pluto Astronomy\n\nPluto is a dwarf planet in the Kuiper belt with five known natural satellites.",
                    "text/markdown",
                ),
            )
        ]
        upload_resp = await client.post(f"{RAG_KB}/{kb_id}/documents/upload", headers=h, files=files)
        assert upload_resp.status_code == 202

        # 2. Create conversation
        conv_resp = await client.post(f"{RAG_KB}/{kb_id}/conversations", headers=h, json={"title": "新对话"})
        conv_id = conv_resp.json()["id"]

        # 3. Send message with stream=True (default)
        msg_resp = await client.post(
            f"/api/v1/rag/conversations/{conv_id}/messages",
            headers=h,
            json={
                "content": "冥王星位于哪里？有几颗已知卫星？",
                "stream": True,
                "top_k": 3,
            },
        )
        assert msg_resp.status_code == 200
        assert "text/event-stream" in msg_resp.headers.get("content-type", "")

        # Parse SSE data events
        lines = msg_resp.text.split("\n")
        data_lines = [l[6:].strip() for l in lines if l.startswith("data: ")]
        assert len(data_lines) > 0
        assert data_lines[-1] == "[DONE]"

        citations_received = []
        deltas_received = []
        finish_reason = None

        for line in data_lines[:-1]:
            chunk = json.loads(line)
            if chunk.get("citation"):
                citations_received.append(chunk["citation"])
            if chunk.get("delta"):
                deltas_received.append(chunk["delta"])
            if chunk.get("finish_reason"):
                finish_reason = chunk["finish_reason"]

        assert len(citations_received) >= 1
        assert citations_received[0]["filename"] == "astronomy.md"
        assert len(deltas_received) > 0
        assert finish_reason == "stop"

        # 4. Check conversation detail: verify messages stored & title auto-updated
        conv_detail = await client.get(f"/api/v1/rag/conversations/{conv_id}", headers=h)
        assert conv_detail.status_code == 200
        detail_data = conv_detail.json()
        assert len(detail_data["messages"]) == 2
        assert detail_data["messages"][0]["role"] == "user"
        assert detail_data["messages"][1]["role"] == "assistant"
        assert len(detail_data["messages"][1]["citations"]) >= 1
        assert detail_data["title"] != "新对话"
        assert "冥王星" in detail_data["title"]
