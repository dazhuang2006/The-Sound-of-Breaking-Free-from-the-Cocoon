"""2D 等距情景游戏接口。

只做三件事：
1. 下发世界配置（房间 / 角色 / 热点 / 任务绑定）；
2. 读写空间侧存档（房间、坐标、已观察热点、操作流水）；
3. 把孩子的回答交给 **原有 LangGraph 工作流**（analyze → 安全审核 → training_turn），
   由 TrainingService 完成评价、分层提示与推进 —— 游戏层不复制任何训练逻辑。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, DbSession, ServicesDep
from app.core.logging import get_logger
from app.db.models import SafetyEvent, TrainingSession, User
from app.schemas.game import (
    GameScenarioOut,
    GameSessionOut,
    GameStateIn,
    GameStateOut,
    GameTurnIn,
    GameTurnOut,
)
from app.schemas.training import TrainingTurn
from app.services.game_worlds import world_catalog, world_payload
from app.services.training import TrainingService
from app.services.training_world import TrainingWorldService

logger = get_logger(__name__)

router = APIRouter(prefix="/game", tags=["2D 情景游戏"])


async def _load_session(
    db: DbSession, user: User, training: TrainingService, training_id: str
) -> TrainingSession:
    try:
        return await training.get(db, user.id, training_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="训练会话不存在") from exc


def _turn(session: TrainingSession, training: TrainingService) -> TrainingTurn:
    return TrainingTurn(**training.serialize(session).to_dict())


@router.get("/scenarios", response_model=list[GameScenarioOut])
async def list_scenarios(user: CurrentUser) -> list[GameScenarioOut]:
    """六个关卡（严格来自既有训练配置，没有第七个）。"""
    return [GameScenarioOut(**item) for item in world_catalog()]


@router.get("/{training_id}", response_model=GameSessionOut)
async def get_session(
    training_id: str,
    db: DbSession,
    user: CurrentUser,
    services: ServicesDep,
) -> GameSessionOut:
    session = await _load_session(db, user, services.training, training_id)
    row = await services.training_world.get_or_create(db, session)
    await db.commit()
    return GameSessionOut(
        world=world_payload(session.scenario),
        training=_turn(session, services.training),
        state=GameStateOut(**TrainingWorldService.payload(row)),
    )


@router.put("/{training_id}/state", response_model=GameStateOut)
async def save_state(
    training_id: str,
    payload: GameStateIn,
    db: DbSession,
    user: CurrentUser,
    services: ServicesDep,
) -> GameStateOut:
    session = await _load_session(db, user, services.training, training_id)
    row = await services.training_world.save(
        db,
        session,
        scene=payload.scene,
        player=payload.player.model_dump() if payload.player else None,
        visited=payload.visited,
        actions=payload.actions,
    )
    await db.commit()
    return GameStateOut(**TrainingWorldService.payload(row))


@router.post("/{training_id}/turn", response_model=GameTurnOut)
async def game_turn(
    training_id: str,
    payload: GameTurnIn,
    db: DbSession,
    user: CurrentUser,
    services: ServicesDep,
) -> GameTurnOut:
    """孩子在游戏里说出/点出的一句话，走 LangGraph 主图推进训练。"""
    session = await _load_session(db, user, services.training, training_id)
    before = session.step_index

    state = {
        "user_id": user.id,
        "user_message": payload.answer,
        "training_id": training_id,
        "game_mode": True,
        "session_id": None,
        "history": [],
        "child_profile": {},
        "followup_context": "",
    }
    config = {
        "configurable": {"services": services, "db": db, "user": user},
        "recursion_limit": 15,
    }
    try:
        result = await services.graph.ainvoke(state, config=config)
    except Exception as exc:  # 图异常要留日志，但不能让孩子的这一轮静默丢失
        logger.exception("游戏回合执行失败 training=%s", training_id)
        raise HTTPException(status_code=500, detail="这一轮没能处理成功，请再说一次") from exc

    safety = result.get("safety") or {}
    blocked = safety.get("level") in ("redirect", "emergency")
    training_payload = result.get("training")
    view = TrainingTurn(**training_payload) if training_payload else _turn(session, services.training)

    if blocked:
        # 与聊天链路一致：安全事件单独落库，便于事后审计
        db.add(
            SafetyEvent(
                user_id=user.id,
                session_id=None,
                level=str(safety.get("level", "normal"))[:16],
                category=",".join(str(item) for item in (safety.get("categories") or ["game"]))[:32],
                excerpt=payload.answer.strip()[:255],
                matched=",".join(str(item) for item in (safety.get("matched") or []))[:255],
            )
        )
    await db.commit()

    reply = (result.get("answer") or "").strip()
    if not reply:
        reply = view.feedback or ""
    accepted = bool(view.last_correct) and view.step_index != before
    logger.info(
        "游戏回合 training=%s step=%s->%s accepted=%s via=%s blocked=%s",
        training_id,
        before,
        view.step_index,
        accepted,
        view.last_via,
        blocked,
    )
    return GameTurnOut(
        training=view,
        reply=reply,
        accepted=accepted,
        via=view.last_via,
        blocked=blocked,
        safety=safety,
        notice=(result.get("safety_message") or None) if blocked else None,
    )
