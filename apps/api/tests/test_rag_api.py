"""Integration tests for /api/v1/rag endpoints (Phase 4.3.b)."""

from uuid import uuid4

from httpx import AsyncClient
import pytest

REGISTER = "/api/v1/auth/register"
RAG_KB = "/api/v1/rag/knowledge-bases"
NOTES = "/api/v1/notes"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(REGISTER, json={"email": email, "password": "supersecretpassword123"})
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestKnowledgeBaseCRUD:
    async def test_create_and_get_kb(self, client: AsyncClient) -> None:
        h = await _auth(client, "kb_tester_1@example.com")

        # 1. Create
        create_resp = await client.post(
            RAG_KB,
            headers=h,
            json={
                "title": "深度学习论文库",
                "description": "存放大模型前沿架构论文",
                "icon": "brain",
            },
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["title"] == "深度学习论文库"
        assert data["icon"] == "brain"
        kb_id = data["id"]

        # 2. Get detail
        get_resp = await client.get(f"{RAG_KB}/{kb_id}", headers=h)
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["id"] == kb_id
        assert get_data["doc_count"] == 0
        assert get_data["char_count"] == 0

    async def test_list_knowledge_bases_with_stats(self, client: AsyncClient) -> None:
        h = await _auth(client, "kb_tester_2@example.com")
        # Empty list initially
        list_resp = await client.get(RAG_KB, headers=h)
        assert list_resp.status_code == 200
        assert list_resp.json() == []

        # Create two KBs
        await client.post(RAG_KB, headers=h, json={"title": "KB 1"})
        await client.post(RAG_KB, headers=h, json={"title": "KB 2"})

        list_resp2 = await client.get(RAG_KB, headers=h)
        assert list_resp2.status_code == 200
        items = list_resp2.json()
        assert len(items) == 2
        assert items[0]["title"] == "KB 2"  # ordered by created_at desc

    async def test_update_knowledge_base(self, client: AsyncClient) -> None:
        h = await _auth(client, "kb_tester_3@example.com")
        create_resp = await client.post(RAG_KB, headers=h, json={"title": "初始标题"})
        kb_id = create_resp.json()["id"]

        update_resp = await client.patch(
            f"{RAG_KB}/{kb_id}",
            headers=h,
            json={"title": "更新后的标题", "description": "新描述"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "更新后的标题"
        assert update_resp.json()["description"] == "新描述"

    async def test_delete_knowledge_base(self, client: AsyncClient) -> None:
        h = await _auth(client, "kb_tester_4@example.com")
        create_resp = await client.post(RAG_KB, headers=h, json={"title": "待删除知识库"})
        kb_id = create_resp.json()["id"]

        del_resp = await client.delete(f"{RAG_KB}/{kb_id}", headers=h)
        assert del_resp.status_code == 204

        # Verify 404 after deletion
        get_resp = await client.get(f"{RAG_KB}/{kb_id}", headers=h)
        assert get_resp.status_code == 404

    async def test_kb_cross_user_isolation(self, client: AsyncClient) -> None:
        h_alice = await _auth(client, "alice_kb@example.com")
        h_bob = await _auth(client, "bob_kb@example.com")

        # Alice creates a KB
        create_resp = await client.post(RAG_KB, headers=h_alice, json={"title": "Alice 的私有库"})
        alice_kb_id = create_resp.json()["id"]

        # Bob tries to access Alice's KB -> 404 Not Found
        get_resp = await client.get(f"{RAG_KB}/{alice_kb_id}", headers=h_bob)
        assert get_resp.status_code == 404

        # Bob tries to delete Alice's KB -> 404 Not Found
        del_resp = await client.delete(f"{RAG_KB}/{alice_kb_id}", headers=h_bob)
        assert del_resp.status_code == 404


class TestDocumentIngestionAndSearch:
    async def test_upload_document_and_pipeline(self, client: AsyncClient) -> None:
        h = await _auth(client, "doc_tester_1@example.com")
        kb_resp = await client.post(RAG_KB, headers=h, json={"title": "文档上传测试库"})
        kb_id = kb_resp.json()["id"]

        # 1. Upload Markdown file
        files = [
            (
                "files",
                (
                    "rag_spec.md",
                    b"# RAG Architecture\n\nRetrieval Augmented Generation with pgvector and FastAPI.\n\nSemantic chunking ensures high precision.",
                    "text/markdown",
                ),
            )
        ]
        upload_resp = await client.post(f"{RAG_KB}/{kb_id}/documents/upload", headers=h, files=files)
        assert upload_resp.status_code == 202
        docs = upload_resp.json()
        assert len(docs) == 1
        assert docs[0]["filename"] == "rag_spec.md"
        doc_id = docs[0]["id"]

        # 2. Check document status (BackgroundTasks runs in ASGI test client)
        doc_resp = await client.get(f"{RAG_KB}/{kb_id}/documents/{doc_id}", headers=h)
        assert doc_resp.status_code == 200
        doc_data = doc_resp.json()
        assert doc_data["status"] == "ready"
        assert doc_data["chunk_count"] >= 1
        assert doc_data["char_count"] > 0

        # 3. Search in this KB
        search_resp = await client.post(
            f"{RAG_KB}/{kb_id}/search",
            headers=h,
            json={"query": "RAG Architecture pgvector", "top_k": 3, "mode": "hybrid"},
        )
        assert search_resp.status_code == 200
        results = search_resp.json()
        assert len(results) >= 1
        assert results[0]["filename"] == "rag_spec.md"
        assert results[0]["score"] > 0

    async def test_upload_unsupported_file_format_rejected(self, client: AsyncClient) -> None:
        h = await _auth(client, "doc_tester_2@example.com")
        kb_resp = await client.post(RAG_KB, headers=h, json={"title": "格式校验库"})
        kb_id = kb_resp.json()["id"]

        files = [("files", ("virus.exe", b"malicious executable", "application/octet-stream"))]
        resp = await client.post(f"{RAG_KB}/{kb_id}/documents/upload", headers=h, files=files)
        assert resp.status_code == 400
        assert "not supported" in resp.json()["detail"]

    async def test_import_notes_to_knowledge_base(self, client: AsyncClient) -> None:
        h = await _auth(client, "doc_tester_3@example.com")
        kb_resp = await client.post(RAG_KB, headers=h, json={"title": "笔记导入库"})
        kb_id = kb_resp.json()["id"]

        # 1. Create a note in Phase 3.1
        note_resp = await client.post(
            NOTES,
            headers=h,
            json={
                "title": "量子计算笔记",
                "content": "量子叠加与量子纠缠是量子计算的两大核心物理机制。\nShor 算法在质因数分解上具有指数级优势。",
            },
        )
        assert note_resp.status_code == 201
        note_id = note_resp.json()["id"]

        # 2. Import note into knowledge base
        import_resp = await client.post(
            f"{RAG_KB}/{kb_id}/documents/import-notes",
            headers=h,
            json={"note_ids": [note_id]},
        )
        assert import_resp.status_code == 202
        imported_docs = import_resp.json()
        assert len(imported_docs) == 1
        assert imported_docs[0]["source_type"] == "note"
        doc_id = imported_docs[0]["id"]

        # 3. Verify status becomes ready
        doc_resp = await client.get(f"{RAG_KB}/{kb_id}/documents/{doc_id}", headers=h)
        assert doc_resp.status_code == 200
        assert doc_resp.json()["status"] == "ready"

        # 4. Search imported note content
        search_resp = await client.post(
            f"{RAG_KB}/{kb_id}/search",
            headers=h,
            json={"query": "量子计算 叠加 纠缠", "top_k": 2},
        )
        assert search_resp.status_code == 200
        assert len(search_resp.json()) >= 1
        assert "量子" in search_resp.json()[0]["content"]

    async def test_delete_document(self, client: AsyncClient) -> None:
        h = await _auth(client, "doc_tester_4@example.com")
        kb_resp = await client.post(RAG_KB, headers=h, json={"title": "文档删除库"})
        kb_id = kb_resp.json()["id"]

        files = [("files", ("delete_me.txt", b"Sample text to delete", "text/plain"))]
        upload_resp = await client.post(f"{RAG_KB}/{kb_id}/documents/upload", headers=h, files=files)
        doc_id = upload_resp.json()[0]["id"]

        del_resp = await client.delete(f"{RAG_KB}/{kb_id}/documents/{doc_id}", headers=h)
        assert del_resp.status_code == 204

        # Verify document is gone
        get_resp = await client.get(f"{RAG_KB}/{kb_id}/documents/{doc_id}", headers=h)
        assert get_resp.status_code == 404
