"""LangGraph 节点实现。

节点只依赖注入进来的服务（LLM / 知识库 / 训练 / 随访）与请求级 DB 会话，
不直接读全局变量，便于单测与替换。
"""

from __future__ import annotations

import time
from typing import Any

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import CAUTION_INSTRUCTION, QA_USER_TEMPLATE, ROLE_SYSTEM
from app.agents.state import AgentState
from app.core.logging import get_logger
from app.db.models import User
from app.schemas.followup import FollowupRecordCreate
from app.services.followup import parse_record_message
from app.services.knowledge import build_citations, format_context
from app.services.llm import LLMError
from app.services.safety import (
    CAUTION_BANNER,
    append_banner,
    assess_input,
    ensure_disclaimer,
    review_output,
)
from app.services.training import extract_scenario

logger = get_logger(__name__)

_TRAINING_START = ("开始训练", "开始练习", "情景训练", "练一练", "练习一下", "开始情景", "换个场景")
_TRAINING_END = ("结束训练", "结束练习", "不练了", "停止训练", "退出训练")
_SUMMARY_WORDS = ("阶段总结", "随访总结", "周总结", "总结一下", "生成总结", "生成报告", "阶段报告")
_QA_COMMAND = ("答疑", "回到答疑", "问个问题", "换个话题")
_GREETING = ("你好", "您好", "在吗", "hi", "hello", "嗨")


def _deps(config: RunnableConfig | None) -> tuple[Any, AsyncSession, User]:
    configurable = (config or {}).get("configurable", {})
    return configurable["services"], configurable["db"], configurable["user"]


def _empty_meta() -> dict[str, Any]:
    return {
        "llm_provider": "rules",
        "llm_model": "rule-engine",
        "mocked": False,
        "latency_ms": 0,
        "retrieved": 0,
    }


# ---------------------------------------------------------------- 分析
async def analyze(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    services, db, user = _deps(config)
    message = (state.get("user_message") or "").strip()
    verdict = assess_input(message)
    base: dict[str, Any] = {"safety": verdict.to_dict(), "safety_message": verdict.message}

    if verdict.blocked:
        return {**base, "intent": "safety", "blocked": True, "mode": state.get("mode", "qa")}

    active = await services.training.get_active(db, user.id, state.get("session_id"))
    mode = "training" if active else "qa"
    scenario: str | None = None

    if any(word in message for word in _TRAINING_END):
        intent = "training_end"
    elif any(word in message for word in _QA_COMMAND):
        if active is not None:
            await services.training.abort(db, active, "家长切换到答疑模式")
        intent = "chat"
        mode = "qa"
    elif any(word in message for word in _TRAINING_START):
        intent = "training_start"
        scenario = extract_scenario(message) or (active.scenario if active else None) or "thanks"
        if active is not None and "换" in message and extract_scenario(message) is None:
            scenario = "thanks"
        mode = "training"
    elif active is not None:
        intent = "training_turn"
        scenario = active.scenario
    elif any(word in message for word in _SUMMARY_WORDS):
        intent = "followup_summary"
    elif parse_record_message(message) is not None:
        intent = "followup_record"
    elif any(word in message.lower() for word in _GREETING) and len(message) <= 12:
        intent = "chat"
    else:
        intent = "qa"

    return {**base, "intent": intent, "mode": mode, "scenario": scenario, "blocked": False}


def route_after_analyze(state: AgentState) -> str:
    if state.get("blocked") or state.get("intent") == "safety":
        return "safety_response"
    intent = state.get("intent", "qa")
    if intent in (
        "qa",
        "training_start",
        "training_turn",
        "training_end",
        "followup_record",
        "followup_summary",
        "chat",
    ):
        return intent
    return "qa"


# ---------------------------------------------------------------- 安全拦截
async def safety_response(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    verdict = state.get("safety") or {}
    message = state.get("safety_message") or verdict.get("message") or ""
    if verdict.get("level") == "emergency":
        answer = message
    else:
        answer = ensure_disclaimer(message)
    return {"answer": answer, "meta": _empty_meta(), "citations": []}


# ---------------------------------------------------------------- 答疑
async def qa_answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    services, db, user = _deps(config)
    message = state["user_message"]
    started = time.monotonic()

    hits = await services.kb.search(message)
    citations = build_citations(hits)
    profile = state.get("child_profile") or {}
    verdict = state.get("safety") or {}
    caution = verdict.get("level") == "caution"

    prompt = QA_USER_TEMPLATE.format(
        nickname=profile.get("nickname") or "孩子",
        age_desc=profile.get("age_desc") or "年龄未填写",
        profile_note=profile.get("profile_note") or "（无）",
        followup_context=state.get("followup_context") or "（暂无记录）",
        knowledge=format_context(hits),
        question=message,
    )
    system_prompt = ROLE_SYSTEM + (f"\n\n{CAUTION_INSTRUCTION}" if caution else "")
    history = (state.get("history") or [])[-6:]
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": item["role"], "content": item["content"]} for item in history)
    messages.append({"role": "user", "content": prompt})

    meta = _empty_meta()
    meta["retrieved"] = len(hits)
    try:
        response = await services.llm.chat(
            messages,
            task="qa",
            context={
                "question": message,
                "snippets": [
                    {
                        "title": hit.chunk.title,
                        "section": hit.chunk.section,
                        "content": hit.chunk.content,
                    }
                    for hit in hits
                ],
                "caution": CAUTION_BANNER if caution else "",
            },
        )
        answer = review_output(response.text).text
        meta.update(
            {
                "llm_provider": response.provider,
                "llm_model": response.model,
                "mocked": response.mocked,
                "latency_ms": response.latency_ms,
            }
        )
        if not hits:
            answer = f"{answer}\n\n（本次未检索到知识库条目，以上为通用居家建议。）"
    except LLMError as exc:
        logger.warning("答疑生成失败，使用检索兜底: %s", exc)
        answer = _fallback_answer(hits, message)
        meta.update({"llm_provider": "fallback", "llm_model": "retrieval-only", "mocked": False})

    if caution:
        answer = append_banner(answer, CAUTION_BANNER)
    meta["latency_ms"] = meta.get("latency_ms") or int((time.monotonic() - started) * 1000)
    return {"answer": answer, "citations": citations, "meta": meta, "training": None}


def _fallback_answer(hits: list[Any], question: str) -> str:
    if not hits:
        body = (
            "知识库暂时无法检索到可靠内容，我不想凭空给出医学建议。"
            "可以先把孩子最近的表现记录下来，再咨询儿童保健科或发育行为科医生。"
        )
    else:
        lines = [f"关于「{question[:40]}」，知识库中有以下内容可供参考："]
        for index, hit in enumerate(hits[:3], start=1):
            lines.append(f"[{index}] 《{hit.chunk.title}》：{hit.chunk.content[:150]}")
        lines.append("如需更具体的建议，可以补充孩子的年龄与当前困扰。")
        body = "\n".join(lines)
    return ensure_disclaimer(body)


# ---------------------------------------------------------------- 训练
async def training_start(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    services, db, user = _deps(config)
    scenario = state.get("scenario") or "thanks"
    try:
        view = await services.training.start(
            db,
            user.id,
            scenario,
            child_id=state.get("child_id"),
            chat_session_id=state.get("session_id"),
        )
    except KeyError:
        return {
            "answer": "这个场景我还不支持。目前可以练习：日常道谢、礼貌求助、表达不适、礼貌拒绝、同伴邀约、简单购物。",
            "meta": _empty_meta(),
            "citations": [],
        }
    answer = (
        f"我们开始「{view.scenario_name}」的情景练习。\n\n{view.feedback}\n\n{view.prompt or ''}"
        "\n\n（想停下来时说「结束训练」；想换场景可以说「换个场景：购物」。）"
    )
    return {"answer": answer, "training": view.to_dict(), "meta": _empty_meta(), "citations": []}


async def training_turn(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    services, db, user = _deps(config)
    active = await services.training.get_active(db, user.id, state.get("session_id"))
    if active is None:
        return {
            "answer": "当前没有进行中的训练。可以说「开始训练」，我会带你进入情景练习。",
            "training": None,
            "meta": _empty_meta(),
            "citations": [],
        }
    view = await services.training.respond(db, active, state["user_message"])
    answer = view.feedback
    if view.prompt and view.prompt not in answer:
        answer = f"{answer}\n\n{view.prompt}"
    return {"answer": answer, "training": view.to_dict(), "meta": _empty_meta(), "citations": []}


async def training_end(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    services, db, user = _deps(config)
    active = await services.training.get_active(db, user.id, state.get("session_id"))
    if active is None:
        return {
            "answer": "现在没有进行中的训练。可以随时说「开始训练」进入情景练习。",
            "training": None,
            "meta": _empty_meta(),
            "citations": [],
        }
    view = await services.training.finish(db, active)
    return {
        "answer": view.summary or view.feedback,
        "training": view.to_dict(),
        "meta": _empty_meta(),
        "citations": [],
    }


# ---------------------------------------------------------------- 随访
async def followup_record(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    services, db, user = _deps(config)
    message = state["user_message"]
    parsed = parse_record_message(message) or {}
    child_id = state.get("child_id")
    if not child_id:
        return {
            "answer": "要先在「孩子档案」里添加孩子，我才能把记录归到对应档案下。添加后再说一次就好。",
            "meta": _empty_meta(),
            "citations": [],
        }
    try:
        record = await services.followup.create_record(
            db,
            user.id,
            FollowupRecordCreate(child_id=child_id, behavior=message[:500], **parsed),
        )
    except (LookupError, ValueError) as exc:
        return {
            "answer": f"这条记录没能保存：{exc}。可以在「随访」页面用表单填写，会更稳妥。",
            "meta": _empty_meta(),
            "citations": [],
        }
    parts = [f"已记录 {record.record_date.isoformat()} 的情况："]
    if "mood" in parsed:
        parts.append(f"- 情绪 {record.mood}/5")
    if "sleep_hours" in parsed:
        parts.append(f"- 睡眠 {record.sleep_hours} 小时")
    if "completion" in parsed:
        parts.append(f"- 训练完成度 {record.completion}%")
    parts.append("想生成阶段小结时，说「生成阶段总结」就可以。")
    return {
        "answer": "\n".join(parts),
        "followup": {"record_id": record.id, "parsed": parsed},
        "meta": _empty_meta(),
        "citations": [],
    }


async def followup_summary(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    services, db, user = _deps(config)
    child_id = state.get("child_id")
    if not child_id:
        return {
            "answer": "生成阶段总结需要先选择孩子档案。可以在「随访」页面添加记录并生成，或者先在档案里添加孩子。",
            "meta": _empty_meta(),
            "citations": [],
        }
    try:
        result = await services.followup.summarize(db, user.id, child_id)
    except (ValueError, LookupError) as exc:
        return {"answer": str(exc), "meta": _empty_meta(), "citations": []}
    return {
        "answer": result.summary.content,
        "followup": {"summary_id": result.summary.id, "metrics": result.metrics},
        "meta": _empty_meta(),
        "citations": [],
    }


# ---------------------------------------------------------------- 闲聊
async def smalltalk(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    message = state["user_message"]
    if any(word in message for word in _QA_COMMAND):
        answer = (
            "已回到居家康复答疑模式，刚才的情景训练已经结束。\n\n"
            "你可以直接问具体问题，比如「孩子在超市里突然躺地上怎么办」；"
            "想继续练习时再说「开始训练」就可以。"
        )
    elif any(word in message.lower() for word in _GREETING):
        answer = (
            "你好，我在。\n\n"
            "你可以直接问我居家康复中的具体问题，比如「孩子一写作业就尖叫怎么办」；"
            "也可以说「开始训练」，陪孩子做一次情景沟通练习。"
        )
    else:
        answer = (
            "我在听。你可以把具体情境说得再细一点（孩子多大、当时发生了什么、你怎么处理的），"
            "我会结合知识库给出更适合的建议。"
        )
    return {"answer": ensure_disclaimer(answer), "meta": _empty_meta(), "citations": []}


__all__ = [
    "analyze",
    "route_after_analyze",
    "safety_response",
    "qa_answer",
    "training_start",
    "training_turn",
    "training_end",
    "followup_record",
    "followup_summary",
    "smalltalk",
]
