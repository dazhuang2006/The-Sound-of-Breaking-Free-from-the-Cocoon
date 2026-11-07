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

    # ---- 自反思答疑子图（Plan → Retrieve → Grade → Draft → Critique → Revise）----
    sub_queries: list[str]              # 规划出的检索式
    evidence_hits: list[Any]            # 原始 SearchHit，供引用/拼接上下文
    evidence: list[dict[str, Any]]      # 序列化后的证据，供前端展示与轨迹留痕
    evidence_score: float               # 证据覆盖度得分
    evidence_ok: bool                   # 证据是否足够，决定是否回环重检索
    attempts: int                       # 检索轮次（有上限，防死循环）
    revisions: int                      # 自我修订轮次（有上限）
    draft: str                          # 待审草稿
    critique: dict[str, Any]            # 自审结论
    trace: list[dict[str, Any]]         # 每个节点的执行轨迹
    started_at: float                   # 请求开始时间，用于统计总耗时
