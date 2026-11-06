"""情景训练接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession, ServicesDep
from app.schemas.training import (
    ScenarioOut,
    StartTrainingRequest,
    TrainingAnswerRequest,
    TrainingSessionOut,
    TrainingTurn,
)
from app.services.training import TrainingView

router = APIRouter(prefix="/training", tags=["情景训练"])


def _turn(view: TrainingView) -> TrainingTurn:
    return TrainingTurn(**view.to_dict())


@router.get("/scenarios", response_model=list[ScenarioOut])
async def list_scenarios(services: ServicesDep) -> list[ScenarioOut]:
    return [ScenarioOut(**item) for item in services.training.scenario_catalog()]


@router.post("/start", response_model=TrainingTurn, status_code=status.HTTP_201_CREATED)
async def start_training(
    payload: StartTrainingRequest, db: DbSession, user: CurrentUser, services: ServicesDep
) -> TrainingTurn:
    try:
        view = await services.training.start(
            db,
            user.id,
            payload.scenario,
            child_id=payload.child_id,
            chat_session_id=payload.chat_session_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"不支持的训练场景: {exc}") from exc
    await db.commit()
    return _turn(view)


@router.get("/sessions", response_model=list[TrainingSessionOut])
async def list_training_sessions(db: DbSession, user: CurrentUser, services: ServicesDep):
    rows = await services.training.list_sessions(db, user.id)
    return [TrainingSessionOut.model_validate(row) for row in rows]


@router.get("/{training_id}", response_model=TrainingTurn)
async def get_training(
    training_id: str, db: DbSession, user: CurrentUser, services: ServicesDep
) -> TrainingTurn:
    try:
        session = await services.training.get(db, user.id, training_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    view = services.training.serialize(session)
    return _turn(view)


@router.post("/{training_id}/answer", response_model=TrainingTurn)
async def answer(
    training_id: str,
    payload: TrainingAnswerRequest,
    db: DbSession,
    user: CurrentUser,
    services: ServicesDep,
) -> TrainingTurn:
    try:
        session = await services.training.get(db, user.id, training_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    view = await services.training.respond(db, session, payload.answer)
    await db.commit()
    return _turn(view)


@router.post("/{training_id}/end", response_model=TrainingTurn)
async def end_training(
    training_id: str, db: DbSession, user: CurrentUser, services: ServicesDep
) -> TrainingTurn:
    try:
        session = await services.training.get(db, user.id, training_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    view = await services.training.finish(db, session)
    await db.commit()
    return _turn(view)


@router.post("/{training_id}/abort", response_model=TrainingTurn)
async def abort_training(
    training_id: str, db: DbSession, user: CurrentUser, services: ServicesDep
) -> TrainingTurn:
    """放弃一次训练（例如刚进场景就退出、什么都没练）。

    与 /end 的区别：不生成小结，状态记为 aborted，不会在「继续上次」里出现。
    """
    try:
        session = await services.training.get(db, user.id, training_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    view = await services.training.abort(db, session, "家长退出了本次训练")
    await db.commit()
    return _turn(view)
