"""2D 游戏存档服务。

存档只记录「空间侧」的进度：当前房间、角色坐标、已观察热点、操作流水。
训练推进（第几步、提示层级、正确次数）仍然只由 TrainingSession + TrainingService 负责，
因此文字训练页和游戏页看到的是同一份训练状态。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TrainingSession, TrainingWorldState
from app.services.game_worlds import GRID_H, GRID_W, get_world

_MAX_VISITED = 64
_MAX_ACTIONS = 120
_MARGIN = 0.7


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _clean_player(player: Any, fallback: tuple[float, float]) -> dict[str, float]:
    if not isinstance(player, dict):
        return {"x": fallback[0], "y": fallback[1]}
    try:
        x = _clamp(player.get("x", fallback[0]), _MARGIN, GRID_W - _MARGIN)
        y = _clamp(player.get("y", fallback[1]), _MARGIN, GRID_H - _MARGIN)
    except (TypeError, ValueError):
        return {"x": fallback[0], "y": fallback[1]}
    return {"x": round(x, 2), "y": round(y, 2)}


def _clean_visited(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        item = item.strip()[:32]
        if item and item not in seen:
            seen.append(item)
    return seen[-_MAX_VISITED:]


def _clean_actions(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        entry: dict[str, Any] = {}
        for key in ("kind", "target", "at"):
            value = item.get(key)
            if isinstance(value, (str, int, float)) or value is None:
                entry[key] = value if not isinstance(value, str) else value[:32]
        if isinstance(item.get("step"), int):
            entry["step"] = max(0, min(item["step"], 32))
        if entry.get("kind"):
            cleaned.append(entry)
    return cleaned[-_MAX_ACTIONS:]


class TrainingWorldService:
    """读写 TrainingWorldState，并保证与训练步骤同步。"""

    async def get(self, db: AsyncSession, training_id: str) -> TrainingWorldState | None:
        return await db.get(TrainingWorldState, training_id)

    async def get_or_create(
        self, db: AsyncSession, session: TrainingSession
    ) -> TrainingWorldState:
        world = get_world(session.scenario)
        index = max(0, min(session.step_index, len(world.steps) - 1))
        step = world.steps[index]
        scene = world.scenes[step.scene]
        spawn = scene.spawn

        row = await db.get(TrainingWorldState, session.id)
        if row is None:
            row = TrainingWorldState(
                training_id=session.id,
                user_id=session.user_id,
                scenario=session.scenario,
                scene=scene.id,
                player={"x": spawn[0], "y": spawn[1]},
                visited=[],
                actions=[],
            )
            db.add(row)
            await db.flush()
            return row

        # 训练可能在文字页被推进（换了一步、换了房间），以 TrainingSession 为准
        if row.scene != scene.id:
            row.scene = scene.id
            row.player = {"x": spawn[0], "y": spawn[1]}
            await db.flush()
        return row

    async def save(
        self,
        db: AsyncSession,
        session: TrainingSession,
        *,
        scene: str | None = None,
        player: dict[str, Any] | None = None,
        visited: list[str] | None = None,
        actions: list[dict[str, Any]] | None = None,
    ) -> TrainingWorldState:
        row = await self.get_or_create(db, session)
        world = get_world(session.scenario)

        if scene and scene in world.scenes:
            changed = scene != row.scene
            row.scene = scene
            if changed:
                spawn = world.scenes[scene].spawn
                row.player = {"x": spawn[0], "y": spawn[1]}

        if row.scene in world.scenes:
            fallback = world.scenes[row.scene].spawn
            row.player = _clean_player(player if player is not None else row.player, fallback)

        if visited is not None:
            row.visited = _clean_visited(visited)
        if actions is not None:
            row.actions = _clean_actions(actions)

        await db.flush()
        return row

    @staticmethod
    def payload(row: TrainingWorldState) -> dict[str, Any]:
        return {
            "scene": row.scene,
            "player": row.player or {},
            "visited": list(row.visited or []),
            "actions": list(row.actions or []),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


training_world_service = TrainingWorldService()
