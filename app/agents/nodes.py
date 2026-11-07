"""LangGraph 节点实现。

节点只依赖注入进来的服务（LLM / 知识库 / 训练 / 随访）与请求级 DB 会话，
不直接读全局变量，便于单测与替换。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import (
    CAUTION_INSTRUCTION,
    PLAN_SYSTEM,
    PLAN_USER_TEMPLATE,
    QA_USER_TEMPLATE,
    REVISE_SYSTEM,
    REVISE_USER_TEMPLATE,
    ROLE_SYSTEM,
)
from app.agents.state import AgentState
from app.core.logging import get_logger
from app.db.models import User
from app.schemas.followup import FollowupRecordCreate
from app.services.followup import parse_record_message
from app.services.knowledge import (
    build_citations,
    expand_query,
    format_context,
    lexical_score,
)
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

    # 2D 游戏：由前端指定训练会话，安全审核仍然先跑一遍，然后直接进入训练推进。
    # 游戏里孩子说的可能是「谢谢」「我不想吃」，不能按聊天指令解析（否则会被路由成答疑）。
    if state.get("training_id"):
        return {
            **base,
            "intent": "training_turn",
            "mode": "training",
            "scenario": None,
            "blocked": False,
        }

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
    training_id = state.get("training_id")
    if training_id:
        try:
            active = await services.training.get(db, user.id, training_id)
        except LookupError:
            return {
                "answer": "这次训练的存档找不到了，可以重新选一个场景开始。",
                "training": None,
                "meta": _empty_meta(),
                "citations": [],
            }
    else:
        active = await services.training.get_active(db, user.id, state.get("session_id"))
    if active is None:
        return {
            "answer": "当前没有进行中的训练。可以说「开始训练」，我会带你进入情景练习。",
            "training": None,
            "meta": _empty_meta(),
            "citations": [],
        }
    evaluation = None
    if state.get("game_mode"):
        # 可选：DeepSeek 语义复判（规则未通过时才真的调用模型）
        evaluation = await services.training_judge.evaluate(active, state["user_message"])
    view = await services.training.respond(
        db, active, state["user_message"], evaluation=evaluation
    )
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


# ---------------------------------------------------------------- 自反思答疑子图
# Plan → Retrieve（并行）→ Grade ──证据不足──> Rewrite ──┐
#                        │                              │
#                        └──证据充足──> Draft → Critique ──不达标──> Revise ──┐
#                                            │                              │
#                                            └──────────> Finalize <─────────┘
_QA_MAX_ATTEMPTS = 2      # 检索轮次上限：防止「一直找不到就无限重试」
_QA_MAX_REVISIONS = 1     # 自修订轮次上限：一次不达标就只改一版


def _trace_step(state: AgentState, node: str, **extra: Any) -> list[dict[str, Any]]:
    """追加一条执行轨迹。LangGraph 默认按值覆盖，这里显式累积。"""
    steps = list(state.get("trace") or [])
    steps.append({"node": node, **extra})
    return steps


def _rule_queries(message: str) -> list[str]:
    """无模型时的查询规划：原句 + 同义扩展 + 分句。"""
    base = (message or "").strip()
    if not base:
        return []
    candidates: list[str] = [base[:80]]
    expanded = expand_query(base)
    if expanded and expanded != base:
        candidates.append(expanded[:120])
    for clause in re.split(r"[，,。；;！!？?\s]+", base):
        clause = clause.strip()
        if 4 <= len(clause) <= 40:
            candidates.append(clause)
    deduped: list[str] = []
    for item in candidates:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:3]


def _serialize_hits(hits: list[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for hit in hits:
        payload.append(
            {
                "id": hit.chunk.id,
                "doc_id": hit.chunk.doc_id,
                "title": hit.chunk.title,
                "section": hit.chunk.section,
                "source": hit.chunk.source,
                "score": round(float(hit.score), 4),
                "vector_score": round(float(hit.vector_score), 4),
                "lexical_score": round(float(hit.lexical_score), 4),
                "snippet": hit.chunk.content[:120],
            }
        )
    return payload


async def plan_queries(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """把家长问题拆成 2-3 条检索式；有真实模型时用模型规划，否则用规则拆句。"""
    services, _db, _user = _deps(config)
    started = state.get("started_at") or time.monotonic()
    question = state.get("user_message") or ""
    queries = _rule_queries(question)
    planner = "rule"

    if services.llm.provider != "mock":
        try:
            profile = state.get("child_profile") or {}
            profile_desc = (
                f"{profile.get('nickname') or '孩子'}，"
                f"{profile.get('age_desc') or '年龄未填写'}；"
                f"{profile.get('profile_note') or '（无）'}"
            )
            response = await services.llm.chat(
                [
                    {"role": "system", "content": PLAN_SYSTEM},
                    {
                        "role": "user",
                        "content": PLAN_USER_TEMPLATE.format(
                            question=question,
                            profile=profile_desc,
                            context=state.get("followup_context") or "（暂无记录）",
                        ),
                    },
                ],
                task="intent",
                json_mode=True,
                temperature=0.1,
                max_tokens=200,
            )
            payload = json.loads(response.text)
            planned = [str(item).strip() for item in (payload.get("queries") or []) if str(item).strip()]
            if planned:
                merged: list[str] = []
                for item in planned + queries:
                    if item not in merged:
                        merged.append(item)
                queries = merged[:3]
                planner = "llm"
        except (LLMError, ValueError, AttributeError, TypeError) as exc:
            logger.debug("查询规划降级为规则: %s", exc)

    return {
        "sub_queries": queries or [question],
        "attempts": 0,
        "revisions": 0,
        "started_at": started,
        "trace": _trace_step(state, "plan_queries", planner=planner, queries=queries),
    }


async def retrieve_evidence(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """多条检索式并行召回，按 chunk 去重、取最高分。"""
    services, _db, _user = _deps(config)
    queries = list(state.get("sub_queries") or []) or [state.get("user_message") or ""]
    attempts = int(state.get("attempts") or 0) + 1
    # 每多检索一轮就放宽一点阈值，避免「一次没命中就永远空手」
    min_score = max(0.1, services.settings.rag_min_score - 0.08 * (attempts - 1))

    results = await asyncio.gather(
        *(services.kb.search(query, min_score=min_score) for query in queries),
        return_exceptions=True,
    )
    merged: dict[str, Any] = {}
    failed = 0
    for result in results:
        if isinstance(result, BaseException):
            failed += 1
            logger.warning("检索子任务失败: %s", result)
            continue
        for hit in result:
            key = hit.chunk.id
            current = merged.get(key)
            if current is None or hit.score > current.score:
                merged[key] = hit

    limit = max(int(services.settings.rag_top_k), 4)
    hits = sorted(merged.values(), key=lambda item: item.score, reverse=True)[:limit]
    return {
        "evidence_hits": hits,
        "evidence": _serialize_hits(hits),
        "attempts": attempts,
        "trace": _trace_step(
            state,
            "retrieve_evidence",
            queries=queries,
            hits=len(hits),
            failed=failed,
            min_score=round(min_score, 3),
        ),
    }


async def grade_evidence(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """给证据打分：查全率（每个子问题是否都有命中）+ 最高分。"""
    services, _db, _user = _deps(config)
    hits = state.get("evidence") or []
    queries = state.get("sub_queries") or []
    threshold = services.settings.rag_min_score

    covered = 0
    for query in queries:
        best = 0.0
        for item in hits:
            best = max(best, float(item["score"]), lexical_score(query, item["snippet"]))
        if best >= threshold * 0.8:
            covered += 1
    coverage = covered / max(len(queries), 1)
    top = max((float(item["score"]) for item in hits), default=0.0)
    enough = bool(hits) and len(hits) >= 2 and (coverage >= 0.5 or top >= threshold * 1.2)
    score = round(0.6 * coverage + 0.4 * min(top, 1.0), 4)
    return {
        "evidence_ok": enough,
        "evidence_score": score,
        "trace": _trace_step(
            state,
            "grade_evidence",
            coverage=round(coverage, 2),
            top=round(top, 3),
            enough=enough,
        ),
    }


def route_after_grade(state: AgentState) -> str:
    if state.get("evidence_ok"):
        return "draft_answer"
    if int(state.get("attempts") or 0) >= _QA_MAX_ATTEMPTS:
        return "draft_answer"
    return "rewrite_query"


async def rewrite_query(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """证据不足时换一批检索式再来一轮。"""
    question = state.get("user_message") or ""
    previous = list(state.get("sub_queries") or [])
    candidates = [
        expand_query(f"{question} 居家 训练 方法")[:120],
        question[:80],
        "居家康复 日常支持 具体做法",
    ]
    rewritten: list[str] = []
    for item in candidates:
        item = (item or "").strip()
        if item and item not in rewritten and item not in previous:
            rewritten.append(item)
    queries = (rewritten[:2] + previous)[:3]
    return {
        "sub_queries": queries,
        "trace": _trace_step(state, "rewrite_query", queries=queries),
    }


async def draft_answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """基于合并后的证据生成草稿（这一步也可能来自检索兜底）。"""
    services, _db, _user = _deps(config)
    hits = state.get("evidence_hits") or []
    message = state.get("user_message") or ""
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
        draft = review_output(response.text).text
        meta.update(
            {
                "llm_provider": response.provider,
                "llm_model": response.model,
                "mocked": response.mocked,
                "latency_ms": response.latency_ms,
            }
        )
    except LLMError as exc:
        logger.warning("答疑生成失败，使用检索兜底: %s", exc)
        draft = _fallback_answer(hits, message)
        meta.update({"llm_provider": "fallback", "llm_model": "retrieval-only", "mocked": False})

    return {
        "draft": draft,
        "meta": meta,
        "trace": _trace_step(
            state,
            "draft_answer",
            chars=len(draft),
            provider=meta.get("llm_provider"),
            retrieved=len(hits),
        ),
    }


async def self_critique(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """确定性自审：长度、引用、与问题的相关性、是否有证据，四条硬规则。"""
    draft = (state.get("draft") or "").strip()
    evidence = state.get("evidence") or []
    question = state.get("user_message") or ""
    issues: list[str] = []

    if len(draft) < 80:
        issues.append("回答过短，可能没有给出可执行建议")
    if evidence and not any(f"[{index}]" in draft for index in range(1, len(evidence) + 1)):
        issues.append("未标注知识库引用编号")
    if lexical_score(question, draft) < 0.08:
        issues.append("与提问的关键词重合度低")
    if not evidence:
        issues.append("没有检索到知识库依据")

    needs_revision = bool(issues) and int(state.get("revisions") or 0) < _QA_MAX_REVISIONS
    critique = {"issues": issues, "needs_revision": needs_revision, "draft_chars": len(draft)}
    return {
        "critique": critique,
        "trace": _trace_step(
            state,
            "self_critique",
            issues=len(issues),
            needs_revision=needs_revision,
        ),
    }


def route_after_critique(state: AgentState) -> str:
    critique = state.get("critique") or {}
    if critique.get("needs_revision"):
        return "revise_answer"
    return "finalize_answer"


async def revise_answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """按自审意见改一版：有真实模型让模型改，否则用确定性补丁。"""
    services, _db, _user = _deps(config)
    draft = state.get("draft") or ""
    issues = (state.get("critique") or {}).get("issues") or []
    revised = draft
    strategy = "rule"

    if services.llm.provider != "mock":
        try:
            response = await services.llm.chat(
                [
                    {"role": "system", "content": REVISE_SYSTEM},
                    {
                        "role": "user",
                        "content": REVISE_USER_TEMPLATE.format(
                            draft=draft,
                            issues="；".join(issues) or "（无）",
                        ),
                    },
                ],
                task="qa",
                temperature=0.3,
                max_tokens=900,
            )
            candidate = review_output(response.text).text.strip()
            if len(candidate) >= 40:
                revised = candidate
                strategy = "llm"
        except LLMError as exc:
            logger.debug("自我修订降级为规则: %s", exc)

    if strategy == "rule":
        if "未标注知识库引用编号" in issues and state.get("evidence"):
            revised = f"{revised}\n\n依据：见下方引用来源第 [1] 条起。"
        if "回答过短" in issues:
            revised = (
                f"{revised}\n\n可以先把目标拆成三步：① 记录行为发生的具体情境；"
                "② 每次只练一个小步骤；③ 做到后立刻给出具体反馈。"
            )
        if "没有检索到知识库依据" in issues:
            revised = (
                f"{revised}\n\n（本次知识库没有检索到直接依据，以上为通用居家建议，"
                "具体情况请咨询专业人员。）"
            )

    return {
        "draft": revised,
        "revisions": int(state.get("revisions") or 0) + 1,
        "trace": _trace_step(state, "revise_answer", strategy=strategy, chars=len(revised)),
    }


async def finalize_answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """定稿：统一加免责声明、警示横幅、引用，并把轨迹写进 meta。"""
    hits = state.get("evidence_hits") or []
    answer = (state.get("draft") or "").strip() or _fallback_answer(
        hits, state.get("user_message") or ""
    )
    citations = build_citations(hits)
    verdict = state.get("safety") or {}
    caution = verdict.get("level") == "caution"

    answer = review_output(answer).text
    if not hits:
        answer = f"{answer}\n\n（本次未检索到知识库条目，以上为通用居家建议。）"
    if caution:
        answer = append_banner(answer, CAUTION_BANNER)

    meta = dict(state.get("meta") or _empty_meta())
    started = state.get("started_at") or time.monotonic()
    trace = _trace_step(state, "finalize_answer", citations=len(citations), caution=caution)
    meta.update(
        {
            "retrieved": len(hits),
            "latency_ms": int((time.monotonic() - started) * 1000),
            "evidence_score": state.get("evidence_score", 0.0),
            "retrieval_rounds": int(state.get("attempts") or 0),
            "revisions": int(state.get("revisions") or 0),
            "agent_steps": len(trace),
            "agent_trace": trace,
        }
    )
    return {"answer": answer, "citations": citations, "meta": meta, "trace": trace}


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
    # 自反思答疑子图
    "plan_queries",
    "retrieve_evidence",
    "grade_evidence",
    "route_after_grade",
    "rewrite_query",
    "draft_answer",
    "self_critique",
    "route_after_critique",
    "revise_answer",
    "finalize_answer",
]
