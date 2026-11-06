"""LangGraph 状态定义。

一次用户消息 = 一次图执行；跨轮上下文由 MySQL（事实）+ Redis（加速）承载，
因此图本身不需要持久化 checkpoint，状态结构保持扁平、可调试。
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # 请求上下文
    session_id: str
    user_id: int
    child_id: int | None
    user_message: str
    history: list[dict[str, str]]
    child_profile: dict[str, Any]
    followup_context: str

    # 2D 游戏入口：直接指定训练会话，复用同一条「安全审核 → 训练推进」链路
    training_id: str | None
    game_mode: bool

    # 路由与安全
    mode: str
    intent: str
    scenario: str | None
    safety: dict[str, Any]
    safety_message: str
    blocked: bool

    # 输出
    answer: str
    citations: list[dict[str, Any]]
    training: dict[str, Any] | None
    followup: dict[str, Any] | None
    meta: dict[str, Any]
