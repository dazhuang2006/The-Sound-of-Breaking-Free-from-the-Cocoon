"""知识库管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DbSession, ServicesDep, require_role
from app.db.models import KnowledgeDoc, User
from app.schemas.knowledge import (
    IngestReportOut,
    KnowledgeDocOut,
    KnowledgeHit,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.get("/docs", response_model=list[KnowledgeDocOut])
async def list_docs(db: DbSession, services: ServicesDep) -> list[KnowledgeDocOut]:
    rows = await db.scalars(select(KnowledgeDoc).order_by(KnowledgeDoc.title))
    return [KnowledgeDocOut.model_validate(row) for row in rows]


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search(
    payload: KnowledgeSearchRequest, services: ServicesDep
) -> KnowledgeSearchResponse:
    hits = await services.kb.search(payload.query, top_k=payload.top_k)
    return KnowledgeSearchResponse(
        query=payload.query,
        backend=services.store.name,
        embedder=services.embedder.name,
        hits=[
            KnowledgeHit(
                index=index,
                doc_id=hit.chunk.doc_id,
                title=hit.chunk.title,
                section=hit.chunk.section,
                source=hit.chunk.source,
                content=hit.chunk.content,
                vector_score=round(hit.vector_score, 4),
                lexical_score=round(hit.lexical_score, 4),
                score=round(hit.score, 4),
            )
            for index, hit in enumerate(hits, start=1)
        ],
    )


@router.post("/ingest", response_model=IngestReportOut)
async def ingest(
    services: ServicesDep,
    db: DbSession,
    user: User = Depends(require_role("professional", "admin")),
) -> IngestReportOut:
    """重新入库 knowledge/ 目录下的全部文档（专业角色可用）。"""
    from app.services.container import sync_knowledge_docs
    from app.services.knowledge import load_markdown_documents

    report = await services.kb.ingest_directory(services.settings.kb_dir, replace=True)
    documents = load_markdown_documents(services.settings.kb_dir)
    await sync_knowledge_docs(services, documents)
    return IngestReportOut(**report.to_dict())
