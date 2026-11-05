"""知识库接口模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source: str
    chunk_count: int
    checksum: str
    ingested_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=4, ge=1, le=10)


class KnowledgeHit(BaseModel):
    index: int
    doc_id: str
    title: str
    section: str
    source: str
    content: str
    vector_score: float
    lexical_score: float
    score: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    backend: str
    embedder: str
    hits: list[KnowledgeHit]


class IngestReportOut(BaseModel):
    documents: int
    chunks: int
    skipped: int
    embedder: str
    backend: str
