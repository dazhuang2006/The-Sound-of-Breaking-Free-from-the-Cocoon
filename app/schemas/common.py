"""通用响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str
    components: dict[str, Any] = Field(default_factory=dict)
