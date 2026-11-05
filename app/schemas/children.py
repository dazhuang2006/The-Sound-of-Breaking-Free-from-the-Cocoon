"""孩子档案模型。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ChildCreate(BaseModel):
    nickname: str = Field(min_length=1, max_length=32)
    birth_date: date | None = None
    profile_note: str = Field(default="", max_length=1000, description="家长自述，如语言、兴趣、敏感点")


class ChildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    birth_date: date | None
    profile_note: str
    created_at: datetime
