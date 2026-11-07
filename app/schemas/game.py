"""2D 情景游戏接口模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.training import TrainingTurn


class GameScenarioOut(BaseModel):
    scenario: str
    name: str
    goal: str
    intro: str
    steps: int
    scene: str
    scene_name: str
    env: str
    art: str
    accent: str
    casts: list[str] = Field(default_factory=list)
    scenes: list[str] = Field(default_factory=list)


class GamePlayer(BaseModel):
    # 越界坐标不报错，交给服务层夹回房间内（孩子乱点也不该 422）
    x: float
    y: float


class GameStateIn(BaseModel):
    scene: str | None = Field(default=None, max_length=32)
    player: GamePlayer | None = None
    visited: list[str] | None = None
    actions: list[dict[str, Any]] | None = None


class GameStateOut(BaseModel):
    scene: str
    player: dict[str, float] = Field(default_factory=dict)
    visited: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: str | None = None


class GameSessionOut(BaseModel):
    world: dict[str, Any]
    training: TrainingTurn
    state: GameStateOut


class GameTurnIn(BaseModel):
    answer: str = Field(min_length=1, max_length=500)
    source: Literal["text", "voice", "gesture"] = "text"


class GameTurnOut(BaseModel):
    training: TrainingTurn
    reply: str = ""
    accepted: bool = False
    via: str | None = None
    blocked: bool = False
    safety: dict[str, Any] = Field(default_factory=dict)
    notice: str | None = None
