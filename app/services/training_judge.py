"""儿童回答的语义复判（可选，DeepSeek）。

为什么需要它：既有训练用确定性规则（关键词 + 替代沟通线索）判定，优点是离线、可测、
不会被模型幻觉带偏；缺点是孩子换一种说法（"我不太想抱，我们握个手好吗"）容易判定失败。

因此这里加一层**只增不减**的语义复判：
1. 规则先跑：已经通过、或孩子明显卡住（"不会/不知道"）时直接返回，不调模型；
2. 只有 `llm_provider=deepseek` 且 `GAME_LLM_JUDGE=true` 时才请求一次；
3. 模型超时、返回非 JSON、或判定不通过 → 返回 None，交回原有分层提示；
4. 模型**只能把未通过的答案判为通过**，永远不能让孩子退步或跳步。
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.models import TrainingSession
from app.services.llm import LLMClient, LLMError
from app.services.training import Evaluation, TrainingService, normalize
from app.services.training_scripts import get_scenario

logger = get_logger(__name__)

_SYSTEM = (
    "你是儿童社交沟通训练的评价助手。"
    "你会看到一次角色扮演的情境、孩子实际说出的话，以及这个情境希望孩子表达的沟通功能。"
    "请判断：孩子这句话是否在语义上完成了该沟通功能（可以换说法、可以很短、可以口语化）。"
    "只根据孩子的原话判断，不脑补孩子没说出口的意思；如果孩子只是说「不知道」「不会」或答非所问，判为不通过。"
    '只输出 JSON：{"accept": true 或 false, "reason": "不超过 20 字的理由"}'
)

_MAX_ANSWER = 200


class TrainingJudge:
    def __init__(self, llm: LLMClient, settings: Settings) -> None:
        self.llm = llm
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings.game_llm_judge) and self.llm.provider == "deepseek"

    async def evaluate(self, session: TrainingSession, answer: str) -> Evaluation | None:
        """返回 Evaluation 表示「已给出结论」；None 表示交回确定性规则。"""
        if not self.enabled:
            return None
        text = (answer or "").strip()
        if not text or len(text) > _MAX_ANSWER or not normalize(text):
            return None

        try:
            scenario = get_scenario(session.scenario)
        except KeyError:
            return None
        index = max(0, min(session.step_index, len(scenario.steps) - 1))
        step = scenario.steps[index]

        deterministic = TrainingService.evaluate(answer, step)
        if deterministic.correct or deterministic.stuck:
            return deterministic

        messages = [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": (
                    f"训练主题：{scenario.name}（总目标：{scenario.goal}）\n"
                    f"当前情境：{step.prompt}\n"
                    f"本步训练目标：{step.goal}\n"
                    f"孩子原话：{text}"
                ),
            },
        ]
        try:
            response = await self.llm.chat(
                messages,
                task="assess",
                json_mode=True,
                temperature=0.0,
                max_tokens=120,
                context={"appropriate": False},
            )
            data: Any = json.loads(response.text)
            accept = bool(data.get("accept")) if isinstance(data, dict) else False
        except (LLMError, ValueError, TypeError) as exc:
            logger.info("语义复判跳过（%s），回退分层提示", exc)
            return deterministic

        if not accept:
            return deterministic
        logger.info("语义复判通过 scenario=%s step=%d chars=%d", session.scenario, index, len(text))
        return Evaluation(correct=True, via="llm")


__all__ = ["TrainingJudge"]
