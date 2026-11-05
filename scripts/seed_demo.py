"""生成演示数据：账号 demo / demo123456、孩子档案、近 7 天随访记录与一份阶段小结。

用法：python -m scripts.seed_demo
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import dispose_engine, get_session_factory, init_db
from app.db.models import Child, FollowupRecord, User
from app.services.container import build_services, close_services

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123456"

SAMPLE_DAYS = [
    # (mood, sleep, completion, behavior, interaction, items)
    (2, 7.5, 40, "入睡拖延约 40 分钟，反复要求再讲一本书", "睡前一起看了绘本，情绪逐渐平稳", ["睡前流程", "图片时间表"]),
    (3, 8.0, 55, "早上出门前抗拒换鞋，哭闹 5 分钟", "用倒计时提示后愿意配合", ["图片时间表", "道谢练习"]),
    (2, 8.5, 50, "商场里听到广播声捂耳朵", "提前戴降噪耳罩，停留时间缩短", ["感官适应", "求助练习"]),
    (3, 9.0, 65, "晚饭时拒绝青椒，但没有掀碗", "把青椒放到旁边，保留其他菜", ["进食渐进", "拒绝练习"]),
    (4, 9.5, 75, "主动把饼干图片递给妈妈", "立即回应并说出“饼干”，孩子重复了一次", ["图片沟通", "道谢练习"]),
    (4, 9.0, 80, "和表姐平行搭积木约 10 分钟", "没有强迫轮流，只在结束时提示说再见", ["同伴游戏", "邀约练习"]),
    (3, 8.5, 70, "下午情绪波动，持续约 15 分钟", "降低环境声音，带到安静角休息", ["情绪调节", "表达不适"]),
]


async def main() -> None:
    settings = get_settings()
    await init_db()
    services = await build_services(settings)
    factory = get_session_factory()
    async with factory() as db:
        user = await db.scalar(select(User).where(User.username == DEMO_USERNAME))
        if user is None:
            user = User(
                username=DEMO_USERNAME,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name="示例家长",
                role="parent",
            )
            db.add(user)
            await db.flush()
            print(f"已创建演示账号：{DEMO_USERNAME} / {DEMO_PASSWORD}")

        child = await db.scalar(select(Child).where(Child.user_id == user.id))
        if child is None:
            child = Child(
                user_id=user.id,
                nickname="小星",
                birth_date=date(2022, 5, 12),
                profile_note="4 岁半，能说少量单词，喜欢拼图和转轮子；对广播声和吸尘器声音敏感。",
            )
            db.add(child)
            await db.flush()
            print("已创建孩子档案：小星")

        count = await db.scalar(
            select(func.count()).select_from(FollowupRecord).where(FollowupRecord.child_id == child.id)
        )
        if not count:
            today = datetime.now(UTC).date()
            for offset, (mood, sleep, completion, behavior, interaction, items) in enumerate(SAMPLE_DAYS):
                db.add(
                    FollowupRecord(
                        user_id=user.id,
                        child_id=child.id,
                        record_date=today - timedelta(days=len(SAMPLE_DAYS) - 1 - offset),
                        mood=mood,
                        sleep_hours=sleep,
                        behavior=behavior,
                        completion=completion,
                        interaction=interaction,
                        training_items=items,
                    )
                )
            await db.flush()
            print(f"已写入 {len(SAMPLE_DAYS)} 天随访记录")

        await db.commit()

        summaries = await services.followup.list_summaries(db, user.id, child.id, 1)
        if not summaries:
            result = await services.followup.summarize(db, user.id, child.id, days=7)
            await db.commit()
            print("\n已生成阶段小结：\n" + result.summary.content)

    await close_services(services)
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
