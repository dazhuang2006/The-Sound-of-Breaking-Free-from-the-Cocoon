"""随访接口模型。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FollowupRecordCreate(BaseModel):
    child_id: int
    record_date: date | None = None
    mood: int = Field(default=3, ge=1, le=5, description="情绪评分 1-5")
    sleep_hours: float = Field(default=9.0, ge=0, le=24)
    behavior: str = Field(default="", max_length=2000)
    training_items: list[str] = Field(default_factory=list, max_length=20)
    completion: int = Field(default=0, ge=0, le=100, description="训练完成度百分比")
    interaction: str = Field(default="", max_length=2000)


class FollowupRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    child_id: int
    record_date: date
    mood: int
    sleep_hours: float
    behavior: str
    training_items: list[str]
    completion: int
    interaction: str
    created_at: datetime


class FollowupSummaryRequest(BaseModel):
    child_id: int
    days: int = Field(default=7, ge=1, le=90)


class FollowupSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    child_id: int
    period_start: date
    period_end: date
    content: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class VoiceDraft(BaseModel):
    """家长口述整理出的结构化草稿；未提及的字段保持 null。"""

    date: str | None = None
    daily_activities: str | None = None
    training_content: str | None = None
    behavior_observations: str | None = None
    emotional_state: str | None = None
    communication_performance: str | None = None
    parent_notes: str | None = None


class VoiceDraftRequest(BaseModel):
    transcription: str = Field(min_length=1, max_length=5000)
    child_id: int | None = None


class VoiceDraftResponse(BaseModel):
    draft: VoiceDraft
    provider: str
    mocked: bool = False
