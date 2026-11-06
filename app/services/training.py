"""情景化沟通训练引擎。

状态机：每个 TrainingSession 记录当前步骤、提示层级、正确次数与完整对话。
设计要点：
- 一次只推进一步，不做"连问三个问题"；
- 答错先给分层提示（线索 → 开头 → 示范），提示用尽才推进，避免孩子卡住失去信心；
- 手势、图片、文字等替代沟通方式与口语同等有效；
- 所有评价只描述训练中发生了什么，不作能力或医学判断。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.models import TrainingSession
from app.services.safety import DISCLAIMER
from app.services.training_scripts import (
    AAC_CUES,
    SCENARIOS,
    Scenario,
    ScenarioStep,
    get_scenario,
    resolve_scenario,
)

logger = get_logger(__name__)

_PUNCT = re.compile(r"[\s，。！？、,.!?；;：:\"'“”‘’（）()\[\]【】~\-]+")
_STUCK_WORDS = ("不会", "不知道", "不想说", "我不说", "不懂", "沉默", "随便")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    return _PUNCT.sub("", text)


@dataclass
class Evaluation:
    correct: bool
    via: str = "speech"  # speech/aac/llm
    stuck: bool = False


@dataclass
class TrainingView:
    id: str
    scenario: str
    scenario_name: str
    goal: str
    status: str
    step_index: int
    total_steps: int
    hint_level: int
    correct_count: int
    feedback: str
    prompt: str | None
    summary: str | None
    transcript: list[dict[str, Any]]
    last_via: str | None = None
    last_correct: bool | None = None
    last_stuck: bool = False

    def to_dict(self) -> dict[str, Any]:
        percent = 100 if self.total_steps == 0 else round(self.step_index / self.total_steps * 100)
        return {
            "id": self.id,
            "scenario": self.scenario,
            "scenario_name": self.scenario_name,
            "goal": self.goal,
            "status": self.status,
            "step_index": self.step_index,
            "total_steps": self.total_steps,
            "hint_level": self.hint_level,
            "correct_count": self.correct_count,
            "progress": min(percent, 100),
            "feedback": self.feedback,
            "prompt": self.prompt,
            "summary": self.summary,
            "transcript": self.transcript,
            "last_via": self.last_via,
            "last_correct": self.last_correct,
            "last_stuck": self.last_stuck,
        }


class TrainingService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # ------------------------------------------------------------ 查询
    async def get_active(
        self,
        db: AsyncSession,
        user_id: int,
        chat_session_id: str | None = None,
    ) -> TrainingSession | None:
        """查询进行中的训练。

        训练绑定到发起它的聊天会话：不同会话之间互不劫持。
        `chat_session_id=None` 表示查找独立训练页发起的训练（未绑定聊天会话）。
        """
        stmt = select(TrainingSession).where(
            TrainingSession.user_id == user_id, TrainingSession.status == "active"
        )
        if chat_session_id is None:
            stmt = stmt.where(TrainingSession.chat_session_id.is_(None))
        else:
            stmt = stmt.where(TrainingSession.chat_session_id == chat_session_id)
        stmt = stmt.order_by(TrainingSession.created_at.desc()).limit(1)
        return (await db.execute(stmt)).scalar_one_or_none()

    async def get(self, db: AsyncSession, user_id: int, training_id: str) -> TrainingSession:
        session = await db.get(TrainingSession, training_id)
        if session is None or session.user_id != user_id:
            raise LookupError("训练会话不存在")
        return session

    async def list_sessions(self, db: AsyncSession, user_id: int, limit: int = 20) -> list[TrainingSession]:
        stmt = (
            select(TrainingSession)
            .where(TrainingSession.user_id == user_id)
            .order_by(TrainingSession.created_at.desc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars())

    # ------------------------------------------------------------ 开始
    async def start(
        self,
        db: AsyncSession,
        user_id: int,
        scenario_key: str,
        child_id: int | None = None,
        chat_session_id: str | None = None,
    ) -> TrainingView:
        scenario = get_scenario(scenario_key)
        previous = await self.get_active(db, user_id, chat_session_id)
        if previous is not None:
            previous.status = "aborted"
            previous.ended_at = _now()
            previous.transcript = [
                *previous.transcript,
                {"role": "system", "content": "家长开始了新的训练，本次训练已结束。"},
            ]

        session = TrainingSession(
            user_id=user_id,
            child_id=child_id,
            chat_session_id=chat_session_id,
            scenario=scenario.key,
            status="active",
            step_index=0,
            hint_level=0,
            correct_count=0,
            total_steps=len(scenario.steps),
            transcript=[],
        )
        db.add(session)
        await db.flush()
        session.transcript = [
            {"role": "coach", "content": scenario.intro},
            {"role": "coach", "content": scenario.steps[0].prompt, "step": 0},
        ]
        return self._view(session, feedback=scenario.intro, prompt=scenario.steps[0].prompt)

    # ------------------------------------------------------------ 单轮互动
    async def respond(
        self,
        db: AsyncSession,
        session: TrainingSession,
        answer: str,
        evaluation: Evaluation | None = None,
    ) -> TrainingView:
        """推进一轮。

        `evaluation` 允许调用方（2D 游戏服务器）先做一次语义复判，再交回状态机推进；
        传 None 时行为与原来完全一致（确定性规则：关键词 + 替代沟通线索）。
        """
        scenario = get_scenario(session.scenario)
        if session.status != "active":
            return self._view(
                session, feedback="本次训练已经结束了。可以说「开始训练」重新选一个场景。", prompt=None
            )

        step_index = min(session.step_index, len(scenario.steps) - 1)
        step = scenario.steps[step_index]
        evaluation = evaluation or self.evaluate(answer, step)
        transcript = [
            *session.transcript,
            {"role": "child", "content": answer.strip()[:300], "step": step_index, "via": evaluation.via},
        ]

        if evaluation.correct:
            session.correct_count += 1
            session.step_index = step_index + 1
            session.hint_level = 0
            praise = step.praise
            if evaluation.via == "aac":
                praise = f"{praise}（用手势/图片表达同样算完成。）"
            if session.step_index >= len(scenario.steps):
                return await self._complete(
                    db, session, scenario, transcript, praise, step_index, evaluation
                )
            next_step = scenario.steps[session.step_index]
            transcript.append({"role": "coach", "content": praise, "step": step_index})
            transcript.append({"role": "coach", "content": next_step.prompt, "step": session.step_index})
            session.transcript = transcript
            return self._view(
                session,
                feedback=praise,
                prompt=next_step.prompt,
                last_via=evaluation.via,
                last_correct=True,
            )

        # 未达成：分层提示
        session.hint_level += 1
        max_level = self.settings.training_max_hint_level
        if session.hint_level <= max_level:
            hint = step.hints[min(session.hint_level - 1, len(step.hints) - 1)]
            lead = "没关系，我们慢慢来。" if evaluation.stuck else "很接近了，我们一起看看。"
            feedback = f"{lead}{hint}"
            transcript.append({"role": "hint", "content": hint, "step": step_index, "level": session.hint_level})
            transcript.append({"role": "coach", "content": feedback, "step": step_index})
            session.transcript = transcript
            return self._view(
                session,
                feedback=feedback,
                prompt=step.prompt,
                last_via=evaluation.via,
                last_correct=False,
                last_stuck=evaluation.stuck,
            )

        # 提示用尽：完整示范后推进，不纠缠
        demo = step.hints[-1]
        transcript.append({"role": "hint", "content": demo, "step": step_index, "level": max_level + 1})
        session.hint_level = 0
        session.step_index = step_index + 1
        feedback = f"我给你示范一次：{demo} 我们可以先跳过这一步，继续往下。"
        if session.step_index >= len(scenario.steps):
            return await self._complete(
                db, session, scenario, transcript, feedback, step_index, evaluation
            )
        next_step = scenario.steps[session.step_index]
        transcript.append({"role": "coach", "content": feedback, "step": step_index})
        transcript.append({"role": "coach", "content": next_step.prompt, "step": session.step_index})
        session.transcript = transcript
        return self._view(
            session,
            feedback=feedback,
            prompt=next_step.prompt,
            last_via=evaluation.via,
            last_correct=False,
            last_stuck=evaluation.stuck,
        )

    # ------------------------------------------------------------ 结束
    async def abort(
        self, db: AsyncSession, session: TrainingSession, reason: str = "家长退出训练"
    ) -> TrainingView:
        if session.status == "active":
            session.status = "aborted"
            session.ended_at = _now()
            session.transcript = [*session.transcript, {"role": "system", "content": reason}]
        return self.serialize(session)

    async def finish(self, db: AsyncSession, session: TrainingSession) -> TrainingView:
        scenario = get_scenario(session.scenario)
        if session.status == "completed":
            return self._view(session, feedback=session.summary or "训练已结束。", prompt=None)
        transcript = [
            *session.transcript,
            {"role": "system", "content": "家长结束了本次训练。"},
        ]
        return await self._complete(db, session, scenario, transcript, "好，今天先练到这里。")

    # ------------------------------------------------------------ 内部
    @staticmethod
    def evaluate(answer: str, step: ScenarioStep) -> Evaluation:
        """确定性评价：口语关键词 + 替代沟通线索。

        2D 游戏会在这一步之后追加一次可选的 DeepSeek 语义复判，
        但确定性规则始终先执行，保证离线、可测试、不依赖模型。
        """
        text = normalize(answer)
        if not text or any(word in text for word in _STUCK_WORDS):
            return Evaluation(correct=False, stuck=True)
        if len(text) <= 8 and any(cue in text for cue in AAC_CUES):
            return Evaluation(correct=True, via="aac")
        for keyword in step.expected:
            if normalize(keyword) and normalize(keyword) in text:
                return Evaluation(correct=True)
        return Evaluation(correct=False)

    async def _complete(
        self,
        db: AsyncSession,
        session: TrainingSession,
        scenario: Scenario,
        transcript: list[dict[str, Any]],
        feedback: str,
        step_index: int | None = None,
        evaluation: Evaluation | None = None,
    ) -> TrainingView:
        session.status = "completed"
        session.ended_at = _now()
        hint_count = sum(1 for item in transcript if item.get("role") == "hint")
        # 用本轮最新的 transcript 生成小结：否则最后一句话不会出现在小结里
        summary = self._build_summary(session, scenario, hint_count, transcript)
        session.summary = summary
        transcript.append(
            {
                "role": "summary",
                "content": summary,
                "correct_count": session.correct_count,
                "hint_count": hint_count,
            }
        )
        session.transcript = transcript
        return self._view(
            session,
            feedback=feedback,
            prompt=None,
            summary=summary,
            last_via=evaluation.via if evaluation else None,
            last_correct=evaluation.correct if evaluation else None,
        )

    @staticmethod
    def _build_summary(
        session: TrainingSession,
        scenario: Scenario,
        hint_count: int,
        transcript: list[dict[str, Any]] | None = None,
    ) -> str:
        reached = min(session.step_index, len(scenario.steps))
        lines = [
            f"【{scenario.name}·训练小结】",
            f"目标：{scenario.goal}",
            f"完成情况：完成 {reached}/{len(scenario.steps)} 个情境，"
            f"{session.correct_count} 次给出了符合情境的回应，使用提示 {hint_count} 次。",
            "过程记录：",
        ]
        for item in transcript if transcript is not None else session.transcript:
            if item.get("role") == "child":
                lines.append(f"- 孩子回应：{item.get('content', '')}")
            elif item.get("role") == "hint":
                lines.append(f"- 使用提示（第 {item.get('level', 1)} 层）：{item.get('content', '')}")
        lines.append(
            "家长可以这样做：把练习放回真实生活场景，在孩子做到时立刻给出具体反馈；"
            "如果孩子用点头、指图片或递卡片回应，也同样算完成。"
        )
        lines.append("训练记录仅描述本次互动过程，不代表能力评定。")
        lines.append(DISCLAIMER)
        return "\n".join(lines)

    def serialize(self, session: TrainingSession) -> TrainingView:
        """把数据库中的训练会话还原为可直接返回给前端的视图。"""
        if session.status == "active":
            scenario = get_scenario(session.scenario)
            step = scenario.steps[min(session.step_index, len(scenario.steps) - 1)]
            return self._view(session, feedback="", prompt=step.prompt)
        return self._view(session, feedback=session.summary or "训练已结束。", prompt=None)

    @staticmethod
    def _view(
        session: TrainingSession,
        *,
        feedback: str,
        prompt: str | None,
        summary: str | None = None,
        last_via: str | None = None,
        last_correct: bool | None = None,
        last_stuck: bool = False,
    ) -> TrainingView:
        scenario = SCENARIOS.get(session.scenario)
        return TrainingView(
            id=session.id,
            scenario=session.scenario,
            scenario_name=scenario.name if scenario else session.scenario,
            goal=scenario.goal if scenario else "",
            status=session.status,
            step_index=session.step_index,
            total_steps=session.total_steps,
            hint_level=session.hint_level,
            correct_count=session.correct_count,
            feedback=feedback,
            prompt=prompt,
            summary=summary if summary is not None else session.summary,
            transcript=list(session.transcript),
            last_via=last_via,
            last_correct=last_correct,
            last_stuck=last_stuck,
        )

    @staticmethod
    def scenario_catalog() -> list[dict[str, Any]]:
        return [
            {
                "key": item.key,
                "name": item.name,
                "goal": item.goal,
                "steps": len(item.steps),
                "intro": item.intro,
            }
            for item in SCENARIOS.values()
        ]


def _now() -> datetime:
    return datetime.now(UTC)


def extract_scenario(message: str) -> str | None:
    return resolve_scenario(message)
