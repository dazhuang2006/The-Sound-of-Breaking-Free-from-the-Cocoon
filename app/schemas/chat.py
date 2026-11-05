"""对话接口模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.training import TrainingTurn


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, description="为空则新建会话")
    child_id: int | None = None


class SafetyPayload(BaseModel):
    level: str = "normal"
    categories: list[str] = Field(default_factory=list)
    matched: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    index: int
    doc_id: str
    title: str
    section: str = ""
    source: str = ""
    snippet: str = ""
    score: float = 0.0


class ChatMeta(BaseModel):
    llm_provider: str
    llm_model: str
    mocked: bool = False
    latency_ms: int = 0
    retrieved: int = 0


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    mode: str
    safety: SafetyPayload = Field(default_factory=SafetyPayload)
    citations: list[Citation] = Field(default_factory=list)
    training: TrainingTurn | None = None
    meta: ChatMeta


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    intent: str
    safety_level: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    mode: str
    child_id: int | None
    created_at: datetime
    updated_at: datetime


class SessionDetail(SessionOut):
    messages: list[MessageOut] = Field(default_factory=list)
