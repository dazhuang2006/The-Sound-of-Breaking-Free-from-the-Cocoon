"""RAG 链路测试：切分、入库、混合检索、引用生成。"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.embeddings import HashEmbedder
from app.services.knowledge import (
    KnowledgeBase,
    build_citations,
    load_markdown_documents,
    split_document,
)
from app.services.vectorstore import MemoryVectorStore


@pytest.mark.asyncio
async def test_markdown_loading_and_splitting():
    documents = load_markdown_documents("knowledge")
    assert len(documents) >= 8
    first = documents[0]
    assert first.title
    chunks = split_document(first, chunk_size=300, overlap=40)
    assert chunks
    assert len({chunk.id for chunk in chunks}) == len(chunks)
    assert all(chunk.content.strip() for chunk in chunks)


@pytest.mark.asyncio
async def test_ingest_and_search(tmp_path):
    settings = get_settings()
    store = MemoryVectorStore(tmp_path / "index.json")
    kb = KnowledgeBase(store, HashEmbedder(256), settings)

    report = await kb.ingest_documents(load_markdown_documents("knowledge"))
    assert report.documents >= 8
    assert report.chunks >= 20
    assert await store.count() == report.chunks

    hits = await kb.search("孩子晚上不肯睡觉，睡前总是很兴奋", top_k=3, min_score=0.0)
    assert hits
    titles = [hit.chunk.title for hit in hits]
    assert any("睡眠" in title for title in titles)


@pytest.mark.asyncio
async def test_search_returns_nothing_for_empty_query(tmp_path):
    settings = get_settings()
    kb = KnowledgeBase(MemoryVectorStore(tmp_path / "index.json"), HashEmbedder(256), settings)
    assert await kb.search("   ") == []


@pytest.mark.asyncio
async def test_retrieval_filters_by_threshold(tmp_path):
    settings = get_settings()
    kb = KnowledgeBase(MemoryVectorStore(tmp_path / "index.json"), HashEmbedder(256), settings)
    await kb.ingest_documents(load_markdown_documents("knowledge"))
    strict = await kb.search("量子计算机的芯片制程", top_k=3, min_score=0.95)
    assert strict == []


@pytest.mark.asyncio
async def test_citations_are_numbered_and_deduped(tmp_path):
    settings = get_settings()
    kb = KnowledgeBase(MemoryVectorStore(tmp_path / "index.json"), HashEmbedder(256), settings)
    await kb.ingest_documents(load_markdown_documents("knowledge"))
    hits = await kb.search("情绪崩溃时怎么处理", top_k=4, min_score=0.0)
    citations = build_citations(hits)
    assert citations
    assert citations[0]["index"] == 1
    keys = [(item["doc_id"], item["section"]) for item in citations]
    assert len(keys) == len(set(keys))
