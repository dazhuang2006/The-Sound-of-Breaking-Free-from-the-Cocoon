"""情景训练接口模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScenarioOut(BaseModel):
    key: str
    name: str
    goal: str
    steps: int
    intro: str


class StartTrainingRequest(BaseModel):
    scenario: str = Field(description="场景 key，见 GET /training/scenarios")
    child_id: int | None = None
    chat_session_id: str | None = None


class TrainingAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=500)


class TrainingTurn(BaseModel):
    id: str
    scenario: str
    scenario_name: str
    goal: str
    status: Literal["active", "completed", "aborted"]
    step_index: int
    total_steps: int
    hint_level: int
    correct_count: int
    progress: int = 0
    feedback: str = ""
    prompt: str | None = None
    summary: str | None = None
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    # 最近一轮的评价来源：speech（口语命中）/ aac（手势图片）/ llm（语义复判）
    last_via: str | None = None
    last_correct: bool | None = None
    last_stuck: bool = False


class TrainingSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    scenario: str
    status: str
    step_index: int
    hint_level: int
    correct_count: int
    total_steps: int
    child_id: int | None
    created_at: datetime
    ended_at: datetime | None
    summary: str | None
