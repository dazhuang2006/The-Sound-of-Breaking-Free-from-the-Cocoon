"""医疗安全规则引擎（不依赖 LLM 的硬约束层）。

两层结构：
1. 输入侧 `assess_input()`：识别急症、诊断诉求、用药诉求、未经验证疗法；
2. 输出侧 `review_output()`：检查模型是否越界（下诊断、给剂量、承诺疗效），
   命中即按句删除并追加合规提示。

LLM 只负责语言表达，安全边界必须由确定性规则兜底 —— 这是医疗类 Agent 的底线。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

DISCLAIMER = "仅供居家辅助参考，不构成医疗诊断与治疗方案。"

SafetyLevel = Literal["normal", "caution", "redirect", "emergency"]


@dataclass(frozen=True)
class _Rule:
    category: str
    level: SafetyLevel
    pattern: re.Pattern[str]
    reason: str
    message: str | None = None


def _p(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# ---------------------------------------------------------------- 固定话术
EMERGENCY_MESSAGE = (
    "你描述的情况可能需要立即处理。请先确保孩子和现场的安全：移开可能造成伤害的物品，"
    "并立刻拨打 120 或前往最近的医院急诊；如果孩子正在伤害自己或他人，请先寻求家人协助控制现场。\n\n"
    "紧急情况处理完之后，我可以继续帮你梳理日常居家支持与随访记录。"
)

DIAGNOSIS_MESSAGE = (
    "我无法进行疾病诊断与专业评估。若您对孩子的发育情况存在疑虑，"
    "建议前往正规医院儿童保健科或发育行为科进行专业测评与诊断。\n\n"
    "在就诊前，我可以帮你整理观察记录（例如出现频率、发生情境、持续时长），"
    "这些信息对医生判断会更有帮助。"
)

MEDICATION_MESSAGE = (
    "我不能提供具体用药建议，也不建议自行调整药物剂量或停药。"
    "用药相关问题请咨询为孩子开具处方的医生或儿童精神科／发育行为科医师。\n\n"
    "如果你愿意，我可以帮你整理用药期间想向医生确认的问题清单。"
)

UNVERIFIED_MESSAGE = (
    "这类疗法目前缺乏可靠证据支持，我不建议采用，也不建议用它替代正规的康复训练与医疗随访。\n\n"
    "如果机构向你推荐了此类项目，建议先向儿童保健科或发育行为科医生核实其必要性与风险。"
)

CAUTION_BANNER = (
    "如果孩子出现自伤、攻击或明显的情绪失控，请优先保证安全，并尽快联系儿童保健科／"
    "发育行为科或专业康复机构评估；存在即时危险时请直接拨打 120。"
)

# ---------------------------------------------------------------- 规则集合
_RULES: tuple[_Rule, ...] = (
    # 急症 / 即时危险
    _Rule(
        "emergency",
        "emergency",
        _p(r"(自杀|想死|不想活|活着没意思|割腕|跳楼|服毒|喝农药)"),
        "自伤自杀风险表述",
        EMERGENCY_MESSAGE,
    ),
    _Rule(
        "emergency",
        "emergency",
        _p(r"(抽搐|惊厥|翻白眼|口吐白沫|呼吸困难|喘不上气|窒息|卡喉|呛住|昏迷|叫不醒|意识不清)"),
        "可能危及生命的躯体症状",
        EMERGENCY_MESSAGE,
    ),
    _Rule(
        "emergency",
        "emergency",
        _p(r"(误吞|吞了.{0,6}(药|电池|磁力珠|硬币|纽扣)|大出血|流血不止|严重烫伤|烧伤|从.{0,4}楼.{0,4}(掉|摔))"),
        "意外伤害",
        EMERGENCY_MESSAGE,
    ),
    _Rule(
        "emergency",
        "emergency",
        _p(r"(走失|走丢|找不到孩子|孩子不见了|跑丢了)"),
        "儿童走失",
        EMERGENCY_MESSAGE,
    ),
    # 诊断诉求
    _Rule(
        "diagnosis",
        "redirect",
        _p(r"((是不是|是否|会不会|像不像|算不算).{0,6}(自闭症|孤独症|asd|多动症|adhd|智力低下|发育迟缓))"),
        "要求判断是否患病",
        DIAGNOSIS_MESSAGE,
    ),
    _Rule(
        "diagnosis",
        "redirect",
        _p(r"((确诊|诊断|判断|评估).{0,4}(一下|孩子|是不是|是否|为))|(帮我.{0,3}(诊断|确诊))"),
        "要求诊断",
        DIAGNOSIS_MESSAGE,
    ),
    _Rule(
        "diagnosis",
        "redirect",
        _p(r"(能治好|能治愈|会不会好|能不能恢复|长大了会好吗|是不是终身)"),
        "要求预后判断",
        DIAGNOSIS_MESSAGE,
    ),
    # 用药诉求
    _Rule(
        "medication",
        "redirect",
        _p(r"(吃什么药|用啥药|用什么药|药物|药量|剂量|mg|毫克|片剂|利他林|哌甲酯|专注达|舍曲林|氟哌啶醇|阿立哌唑|褪黑素|益生菌|中药|停药|加药|减药)"),
        "用药与剂量咨询",
        MEDICATION_MESSAGE,
    ),
    # 未经验证疗法
    _Rule(
        "unverified_therapy",
        "redirect",
        _p(r"(排毒|螯合|干细胞|高压氧|针灸|经络|生物疗法|禁食疗法|偏方|秘方|特效药|包治|灵丹)"),
        "未经验证的疗法",
        UNVERIFIED_MESSAGE,
    ),
    # 需警示但可以继续答疑的行为描述
    _Rule(
        "self_injury_behavior",
        "caution",
        _p(r"(打自己|打头|撞墙|咬自己|掐自己|抓自己|抠自己|扯头发|伤害自己|自伤|自残|打人|咬人|掐人|推人|踢人)"),
        "自伤或攻击行为描述",
        None,
    ),
)

# 输出侧检查：命中即视为越界
_OUTPUT_VIOLATIONS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("diagnosis_assertion", _p(r"(确诊|诊断|判断).{0,6}(为|是|属于).{0,8}(自闭症|孤独症|多动症|智力低下|发育迟缓)")),
    ("diagnosis_assertion", _p(r"(孩子|宝宝|他|她).{0,4}(就是|肯定是|一定是).{0,6}(自闭症|孤独症|多动症)")),
    ("dosage", _p(r"(\d+(\.\d+)?\s*(mg|毫克|ml|毫升|片|粒|滴))")),
    ("medication_advice", _p(r"(建议|可以|应该).{0,8}(服用|吃|用).{0,8}(药|利他林|哌甲酯|舍曲林|褪黑素)")),
    ("guarantee", _p(r"(保证|包治|一定能|一定能好|百分之百|100%|彻底治愈|根治|完全恢复|恢复正常)")),
    ("unverified", _p(r"(推荐|建议|试试).{0,8}(针灸|螯合|干细胞|高压氧|排毒|偏方|秘方)")),
)

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")


@dataclass
class SafetyVerdict:
    level: SafetyLevel = "normal"
    categories: list[str] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    message: str = ""
    reasons: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        """是否需要绕过 LLM，直接返回固定安全话术。"""
        return self.level in ("redirect", "emergency")

    @property
    def needs_caution(self) -> bool:
        return self.level == "caution"

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "categories": self.categories,
            "matched": self.matched,
            "reasons": self.reasons,
        }


@dataclass
class OutputReview:
    text: str
    violations: list[str]
    sanitized: bool

    @property
    def passed(self) -> bool:
        return not self.violations


_LEVEL_ORDER: dict[str, int] = {"normal": 0, "caution": 1, "redirect": 2, "emergency": 3}


def assess_input(text: str) -> SafetyVerdict:
    """对用户输入做确定性安全评估。"""
    if not text or not text.strip():
        return SafetyVerdict()

    verdict = SafetyVerdict()
    for rule in _RULES:
        match = rule.pattern.search(text)
        if not match:
            continue
        if rule.category not in verdict.categories:
            verdict.categories.append(rule.category)
        snippet = match.group(0)[:32]
        if snippet not in verdict.matched:
            verdict.matched.append(snippet)
        verdict.reasons.append(rule.reason)
        if _LEVEL_ORDER[rule.level] > _LEVEL_ORDER[verdict.level]:
            verdict.level = rule.level
        if rule.message and not verdict.message:
            verdict.message = rule.message

    # 同时命中急症与其它类别时，急症话术优先
    if verdict.level == "emergency":
        verdict.message = EMERGENCY_MESSAGE
    return verdict


SAFE_FALLBACK = (
    "抱歉，这部分内容涉及医疗判断，我不能给出结论。"
    "建议带着观察记录咨询儿童保健科或发育行为科医生；"
    "我可以帮你整理居家可执行的观察与陪伴建议。"
)


def review_output(text: str) -> OutputReview:
    """检查并清洗模型输出中的越界内容。"""
    if not text.strip():
        return OutputReview(
            text=ensure_disclaimer(SAFE_FALLBACK), violations=["empty"], sanitized=True
        )

    violations: list[str] = []
    kept: list[str] = []
    for sentence in _SENTENCE_SPLIT.split(text):
        if not sentence:
            continue
        if not sentence.strip():
            # 纯换行/空白分片要保留，否则段落结构会被破坏
            kept.append(sentence)
            continue
        hit = False
        for name, pattern in _OUTPUT_VIOLATIONS:
            if pattern.search(sentence):
                violations.append(name)
                hit = True
                break
        if not hit:
            kept.append(sentence)

    cleaned = re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip()
    sanitized = bool(violations)
    if not cleaned:
        cleaned = SAFE_FALLBACK
    cleaned = ensure_disclaimer(cleaned)
    return OutputReview(text=cleaned, violations=violations, sanitized=sanitized)


def ensure_disclaimer(text: str) -> str:
    text = text.rstrip()
    if DISCLAIMER in text:
        return text
    return f"{text}\n\n{DISCLAIMER}"


def append_banner(text: str, banner: str) -> str:
    if banner in text:
        return text
    return f"{text.rstrip()}\n\n> {banner}"
