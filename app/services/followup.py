"""家庭随访：每日记录、指标聚合、阶段性小结。

聚合全部由代码计算（可复核、可测试），LLM 只负责把指标写成家长看得懂的叙述；
小结落库保存，便于医生/康复师回看。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.models import Child, FollowupRecord, FollowupSummary
from app.schemas.followup import FollowupRecordCreate
from app.services.llm import LLMClient, LLMError
from app.services.safety import ensure_disclaimer, review_output

logger = get_logger(__name__)


@dataclass
class SummaryResult:
    summary: FollowupSummary
    metrics: dict[str, Any]


class FollowupService:
    def __init__(self, llm: LLMClient, settings: Settings | None = None) -> None:
        self.llm = llm
        self.settings = settings or get_settings()

    # ------------------------------------------------------------ 记录
    async def create_record(
        self, db: AsyncSession, user_id: int, payload: FollowupRecordCreate
    ) -> FollowupRecord:
        child = await self._require_child(db, user_id, payload.child_id)
        record = FollowupRecord(
            user_id=user_id,
            child_id=child.id,
            record_date=payload.record_date or datetime.now(UTC).date(),
            mood=payload.mood,
            sleep_hours=payload.sleep_hours,
            behavior=payload.behavior,
            training_items=payload.training_items,
            completion=payload.completion,
            interaction=payload.interaction,
        )
        db.add(record)
        await db.flush()
        return record

    async def list_records(
        self, db: AsyncSession, user_id: int, child_id: int, days: int = 14
    ) -> list[FollowupRecord]:
        await self._require_child(db, user_id, child_id)
        since = datetime.now(UTC).date() - timedelta(days=days)
        stmt = (
            select(FollowupRecord)
            .where(FollowupRecord.child_id == child_id, FollowupRecord.record_date >= since)
            .order_by(FollowupRecord.record_date.asc(), FollowupRecord.id.asc())
        )
        return list((await db.execute(stmt)).scalars())

    async def list_summaries(
        self, db: AsyncSession, user_id: int, child_id: int, limit: int = 10
    ) -> list[FollowupSummary]:
        await self._require_child(db, user_id, child_id)
        stmt = (
            select(FollowupSummary)
            .where(FollowupSummary.child_id == child_id)
            .order_by(FollowupSummary.created_at.desc())
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars())

    # ------------------------------------------------------------ 聚合
    @staticmethod
    def aggregate(records: list[FollowupRecord]) -> dict[str, Any]:
        if not records:
            return {
                "record_count": 0,
                "days": 0,
                "avg_mood": None,
                "avg_sleep_hours": None,
                "avg_completion": None,
                "mood_trend": "无数据",
                "training_items": {},
            }
        count = len(records)
        moods = [record.mood for record in records]
        sleeps = [record.sleep_hours for record in records]
        completions = [record.completion for record in records]
        half = max(count // 2, 1)
        first_half = sum(moods[:half]) / len(moods[:half])
        second_half = sum(moods[half:]) / len(moods[half:]) if moods[half:] else first_half
        delta = second_half - first_half
        if abs(delta) < 0.3:
            trend = "基本平稳"
        elif delta > 0:
            trend = f"略有上升（{delta:+.1f}）"
        else:
            trend = f"略有下降（{delta:+.1f}）"

        items: dict[str, int] = {}
        for record in records:
            for item in record.training_items or []:
                items[item] = items.get(item, 0) + 1

        span = (records[-1].record_date - records[0].record_date).days + 1
        return {
            "record_count": count,
            "days": max(span, 1),
            "period_start": records[0].record_date.isoformat(),
            "period_end": records[-1].record_date.isoformat(),
            "avg_mood": round(sum(moods) / count, 1),
            "avg_sleep_hours": round(sum(sleeps) / count, 1),
            "avg_completion": round(sum(completions) / count),
            "min_sleep_hours": round(min(sleeps), 1),
            "max_sleep_hours": round(max(sleeps), 1),
            "mood_trend": trend,
            "training_items": dict(sorted(items.items(), key=lambda kv: -kv[1])[:5]),
        }

    # ------------------------------------------------------------ 小结
    async def summarize(
        self, db: AsyncSession, user_id: int, child_id: int, days: int | None = None
    ) -> SummaryResult:
        days = days or self.settings.followup_window_days
        records = await self.list_records(db, user_id, child_id, days)
        if not records:
            raise ValueError("该时间段内还没有随访记录，先记录几天数据再来生成小结吧。")
        child = await self._require_child(db, user_id, child_id)
        metrics = self.aggregate(records)
        records_text = "\n".join(
            f"{record.record_date.isoformat()}｜情绪 {record.mood}/5｜睡眠 {record.sleep_hours}h｜"
            f"训练完成度 {record.completion}%｜行为：{record.behavior or '未填写'}｜"
            f"互动：{record.interaction or '未填写'}"
            for record in records
        )
        prompt = self._build_prompt(child, metrics, records_text, days)
        try:
            response = await self.llm.chat(
                [{"role": "user", "content": prompt}],
                task="summary",
                context={
                    "nickname": child.nickname,
                    "metrics": metrics,
                    "records": [record.behavior for record in records],
                },
                temperature=0.3,
            )
            content = review_output(response.text).text
        except LLMError as exc:
            logger.warning("随访小结生成失败，使用规则模板: %s", exc)
            content = self._fallback_summary(child, metrics)

        content = ensure_disclaimer(content)
        summary = FollowupSummary(
            user_id=user_id,
            child_id=child_id,
            period_start=date.fromisoformat(metrics["period_start"]),
            period_end=date.fromisoformat(metrics["period_end"]),
            content=content,
            metrics=metrics,
        )
        db.add(summary)
        await db.flush()
        return SummaryResult(summary=summary, metrics=metrics)

    async def recent_context(self, db: AsyncSession, child_id: int, days: int = 7) -> str:
        since = datetime.now(UTC).date() - timedelta(days=days)
        stmt = (
            select(FollowupRecord)
            .where(FollowupRecord.child_id == child_id, FollowupRecord.record_date >= since)
            .order_by(FollowupRecord.record_date.desc())
            .limit(10)
        )
        records = list((await db.execute(stmt)).scalars())
        if not records:
            return "（最近没有居家记录）"
        return "\n".join(
            f"- {record.record_date.isoformat()}：情绪 {record.mood}/5，睡眠 {record.sleep_hours}h，"
            f"训练完成度 {record.completion}%，行为：{record.behavior or '未填写'}"
            for record in records
        )

    # ------------------------------------------------------------ 内部
    @staticmethod
    def _build_prompt(
        child: Child, metrics: dict[str, Any], records_text: str, days: int
    ) -> str:
        from app.agents.prompts import SUMMARY_SYSTEM, SUMMARY_USER_TEMPLATE

        return (
            SUMMARY_SYSTEM
            + "\n\n"
            + SUMMARY_USER_TEMPLATE.format(
                nickname=child.nickname,
                period=f"近 {days} 天（{metrics['period_start']} ~ {metrics['period_end']}）",
                metrics="\n".join(f"- {key}: {value}" for key, value in metrics.items()),
                records=records_text,
            )
        )

    @staticmethod
    def _fallback_summary(child: Child, metrics: dict[str, Any]) -> str:
        items = "、".join(metrics.get("training_items", {}).keys()) or "暂无固定项目"
        return (
            f"【阶段性随访小结】\n"
            f"{child.nickname}近 {metrics['days']} 天共记录 {metrics['record_count']} 条。\n"
            f"- 情绪状态均值 {metrics['avg_mood']}/5，整体{metrics['mood_trend']}；\n"
            f"- 平均睡眠 {metrics['avg_sleep_hours']} 小时（{metrics['min_sleep_hours']}~{metrics['max_sleep_hours']}）；\n"
            f"- 居家训练完成度均值 {metrics['avg_completion']}%，主要项目：{items}。\n"
            "下周可以继续保持固定作息与短时高频的练习节奏，记录情绪波动前发生了什么。\n"
            "如出现持续睡眠紊乱、明显退行或自伤行为，建议尽快联系儿童保健科／发育行为科。"
        )

    @staticmethod
    async def _require_child(db: AsyncSession, user_id: int, child_id: int) -> Child:
        child = await db.get(Child, child_id)
        if child is None or child.user_id != user_id:
            raise LookupError("孩子档案不存在或无权访问")
        return child


def age_desc(birth_date: date | None) -> str:
    if not birth_date:
        return "年龄未填写"
    today = datetime.now(UTC).date()
    months = (today.year - birth_date.year) * 12 + (today.month - birth_date.month)
    if today.day < birth_date.day:
        months -= 1
    years, remain = divmod(max(months, 0), 12)
    if years <= 0:
        return f"{remain} 个月"
    return f"{years} 岁 {remain} 个月" if remain else f"{years} 岁"


_RECORD_PATTERNS = {
    "mood": re.compile(r"(?:情绪|心情)\D{0,6}([1-5一二三四五])"),
    "sleep": re.compile(r"(?:睡眠|睡了|睡觉)\D{0,6}(\d+(?:\.\d+)?)\s*(?:小时|h|H)"),
    "completion": re.compile(r"(?:完成|做完|完成度)\D{0,6}(\d{1,3})\s*(?:%|％|百分)"),
}


def parse_record_message(message: str) -> dict[str, Any] | None:
    """从自然语言中抽取随访记录，至少命中两项才认为是一次有效记录。"""
    text = message.strip()
    if not any(word in text for word in ("记录", "打卡", "今天")):
        return None
    result: dict[str, Any] = {}
    mood = _RECORD_PATTERNS["mood"].search(text)
    if mood:
        mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
        value = mood.group(1)
        result["mood"] = mapping.get(value, int(value) if value.isdigit() else 3)
    sleep = _RECORD_PATTERNS["sleep"].search(text)
    if sleep:
        result["sleep_hours"] = float(sleep.group(1))
    completion = _RECORD_PATTERNS["completion"].search(text)
    if completion:
        result["completion"] = int(completion.group(1))
    if len(result) < 2:
        return None
    return result
