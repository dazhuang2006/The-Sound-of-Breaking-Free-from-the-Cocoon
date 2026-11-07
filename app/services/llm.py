"""LLM 客户端：DeepSeek（OpenAI 兼容）与离线 Mock。

Mock 不是"假装有 AI"：它按任务类型返回结构化、可读的模板文本，
让整条链路（路由 → 检索 → 生成 → 安全审核 → 落库）在无 API Key 时也能完整跑通，
并在响应元数据里明确标记 `provider=mock`，避免误把模板当成模型能力。
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

LLMTask = Literal["qa", "summary", "assess", "intent", "chat"]
Message = dict[str, str]


class LLMError(RuntimeError):
    """模型调用失败（超时、鉴权、配额等）。"""


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    latency_ms: int = 0
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def mocked(self) -> bool:
        return self.provider == "mock"


class LLMClient(ABC):
    provider: str = "base"
    model: str = "unknown"

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        task: LLMTask = "chat",
        context: dict[str, Any] | None = None,
    ) -> LLMResponse: ...

    async def aclose(self) -> None:  # pragma: no cover
        return None


class DeepSeekLLM(LLMClient):
    provider = "deepseek"

    def __init__(self, settings: Settings) -> None:
        from openai import AsyncOpenAI

        if not settings.deepseek_api_key:
            raise LLMError("DEEPSEEK_API_KEY 未配置")
        self.model = settings.deepseek_model
        self._default_temperature = settings.llm_temperature
        self._default_max_tokens = settings.llm_max_tokens
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=2,
        )

    async def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        task: LLMTask = "chat",
        context: dict[str, Any] | None = None,
    ) -> LLMResponse:
        started = time.monotonic()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self._default_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self._default_max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            completion = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            raise LLMError(f"DeepSeek 调用失败: {exc}") from exc
        choice = completion.choices[0].message.content or ""
        usage = completion.usage.model_dump() if completion.usage else {}
        return LLMResponse(
            text=choice.strip(),
            provider=self.provider,
            model=self.model,
            latency_ms=int((time.monotonic() - started) * 1000),
            usage=usage,
        )

    async def aclose(self) -> None:
        await self._client.close()


class MockLLM(LLMClient):
    """确定性模板生成器，供离线演示与测试使用。"""

    provider = "mock"
    model = "mock-template-v1"

    async def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
        task: LLMTask = "chat",
        context: dict[str, Any] | None = None,
    ) -> LLMResponse:
        context = context or {}
        if task == "qa":
            text = _mock_qa(context)
        elif task == "summary":
            text = _mock_summary(context)
        elif task == "followup_draft":
            text = _mock_followup_draft(context)
        elif task == "assess":
            text = json.dumps(
                {"appropriate": bool(context.get("appropriate", False)), "reason": "规则评估"},
                ensure_ascii=False,
            )
        elif task == "intent":
            text = json.dumps({"intent": context.get("intent", "qa")}, ensure_ascii=False)
        else:
            text = "我在这里，可以继续聊聊孩子今天的情况。"
        return LLMResponse(text=text, provider=self.provider, model=self.model, latency_ms=0)


def _trim(text: str, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _mock_qa(context: dict[str, Any]) -> str:
    question = context.get("question", "")
    snippets: list[dict[str, Any]] = context.get("snippets", []) or []
    caution = context.get("caution", "")

    if not snippets:
        return (
            "关于这个问题，知识库里暂时没有足够可靠的资料，我不想凭空给你编一个答案。\n\n"
            "可以先做两件事：\n"
            "1. 记录孩子最近一周的具体表现（发生时间、当时情境、你的处理方式）；\n"
            "2. 带着这些记录咨询儿童保健科或发育行为科医生，或联系当地残联定点康复机构。\n\n"
            "如果你愿意，我也可以先帮你把观察记录整理成一份就诊时能用的一页纸。"
        )

    lines = [f"关于「{_trim(question, 40)}」，知识库里有这些可以参考的内容：", ""]
    for index, snippet in enumerate(snippets[:3], start=1):
        title = snippet.get("title", "")
        section = snippet.get("section", "")
        content = _trim(snippet.get("content", ""), 160)
        label = f"《{title}》" + (f"·{section}" if section else "")
        lines.append(f"[{index}] {label}：{content}")
    lines.append("")
    lines.append("可以这样落到日常：")
    lines.append("- 先观察并记录行为出现的情境，找出可预测的触发点；")
    lines.append("- 把训练拆成很小的步骤，每一步做到就给具体、即时的反馈；")
    lines.append("- 保持指令简短、固定，必要时配图片或手势提示；")
    lines.append("- 每天固定时段练 5～10 分钟，比一次练很久更容易坚持。")
    if caution:
        lines.append("")
        lines.append(f"另外提醒：{caution}")
    return "\n".join(lines)


def _mock_followup_draft(context: dict[str, Any]) -> str:
    """离线模板：只按关键词把家长原话分桶，不推断任何未说出的信息。"""
    raw = str(context.get("transcription") or "").strip()
    buckets: dict[str, list[str]] = {
        "daily_activities": [],
        "training_content": [],
        "behavior_observations": [],
        "emotional_state": [],
        "communication_performance": [],
        "parent_notes": [],
    }
    rules = (
        ("training_content", ("训练", "练习", "完成", "卡片", "拼图", "任务")),
        ("emotional_state", ("情绪", "开心", "高兴", "哭", "生气", "焦虑", "平静", "崩溃", "烦躁")),
        (
            "communication_performance",
            ("说", "表达", "沟通", "回应", "指", "语言", "打招呼", "再见", "谢谢"),
        ),
        ("behavior_observations", ("行为", "刻板", "重复", "打", "咬", "跑", "躺", "捂耳", "尖叫")),
        ("daily_activities", ("今天", "去了", "玩", "吃饭", "睡", "出门", "幼儿园", "公园", "超市")),
    )
    for sentence in re.split(r"[。！？!?；;\n]+", raw):
        sentence = sentence.strip()
        if not sentence:
            continue
        for key, keywords in rules:
            if any(word in sentence for word in keywords):
                buckets[key].append(sentence)
                break
        else:
            buckets["parent_notes"].append(sentence)
    payload = {
        "date": None,
        **{
            key: ("。".join(values) + "。" if values else None)
            for key, values in buckets.items()
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def _mock_summary(context: dict[str, Any]) -> str:
    nickname = context.get("nickname") or "孩子"
    metrics = context.get("metrics", {}) or {}
    records = context.get("records", []) or []
    scenario = context.get("scenario")
    if scenario:
        return (
            f"本次「{scenario}」情景训练已完成，共 {context.get('total_steps', 0)} 个回合，"
            f"其中 {context.get('correct_count', 0)} 个回合孩子给出了符合情境的回应，"
            f"使用了 {context.get('hint_count', 0)} 次提示。\n\n"
            "训练中值得保留的做法：一次只问一个问题、给足等待时间、孩子用手势或图片回应也算完成。"
        )
    avg_mood = metrics.get("avg_mood")
    avg_sleep = metrics.get("avg_sleep_hours")
    completion = metrics.get("avg_completion")
    items = "、".join((metrics.get("training_items") or {}).keys()) or "暂无固定项目"
    days = metrics.get("days") or len(records)
    parts = [
        "【总体情况】",
        f"{nickname}近 {days} 天共记录 {metrics.get('record_count', len(records))} 条。"
        + (f"情绪状态均值 {avg_mood}/5，" if avg_mood is not None else "")
        + (f"平均睡眠 {avg_sleep} 小时，" if avg_sleep is not None else "")
        + (f"居家训练完成度均值 {completion}%。" if completion is not None else ""),
        "",
        "【值得注意的变化】",
        f"- 情绪趋势：{metrics.get('mood_trend', '数据不足')}",
        f"- 训练项目：{items}",
        "- 本摘要只基于家长填写的记录，不包含临床观察；记录之外的变化建议在就诊时补充说明。",
        "",
        "【下周可尝试的做法】",
        "- 保持固定作息与睡前流程，把训练拆成每天 5～10 分钟的小段；",
        "- 在孩子做到时立刻给出具体反馈，例如说出他刚刚做到了什么；",
        "- 继续记录情绪波动前发生了什么，一周后回看更容易找到规律。",
        "",
        "【建议就医的情形】",
        "如出现持续睡眠紊乱、明显能力退行、自伤或攻击行为加重，建议尽快联系儿童保健科／发育行为科。",
    ]
    return "\n".join(parts)


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "deepseek" and settings.deepseek_api_key:
        try:
            return DeepSeekLLM(settings)
        except LLMError as exc:
            logger.warning("DeepSeek 初始化失败，降级为 Mock: %s", exc)
    elif settings.llm_provider == "deepseek":
        logger.warning("未配置 DEEPSEEK_API_KEY，使用 Mock LLM")
    return MockLLM()
