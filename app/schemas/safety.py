"""安全审计模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SafetyEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    session_id: str | None
    level: str
    category: str
    excerpt: str
    matched: str
    created_at: datetime
