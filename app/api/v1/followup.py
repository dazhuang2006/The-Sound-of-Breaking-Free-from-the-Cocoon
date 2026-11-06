"""家庭随访接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession, ServicesDep
from app.schemas.followup import (
    FollowupRecordCreate,
    FollowupRecordOut,
    FollowupSummaryOut,
    FollowupSummaryRequest,
    VoiceDraftRequest,
    VoiceDraftResponse,
)
from app.services.followup import DraftGenerationError

router = APIRouter(prefix="/followup", tags=["家庭随访"])


@router.post("/records", response_model=FollowupRecordOut, status_code=status.HTTP_201_CREATED)
async def create_record(
    payload: FollowupRecordCreate, db: DbSession, user: CurrentUser, services: ServicesDep
) -> FollowupRecordOut:
    try:
        record = await services.followup.create_record(db, user.id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(record)
    return FollowupRecordOut.model_validate(record)


@router.get("/records", response_model=list[FollowupRecordOut])
async def list_records(
    child_id: int, db: DbSession, user: CurrentUser, services: ServicesDep, days: int = 14
) -> list[FollowupRecordOut]:
    if not 1 <= days <= 90:
        raise HTTPException(status_code=422, detail="days 需在 1~90 之间")
    try:
        records = await services.followup.list_records(db, user.id, child_id, days)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [FollowupRecordOut.model_validate(item) for item in records]


@router.post("/voice-draft", response_model=VoiceDraftResponse)
async def voice_draft(
    payload: VoiceDraftRequest, db: DbSession, user: CurrentUser, services: ServicesDep
) -> VoiceDraftResponse:
    """把家长确认后的转写文本整理成结构化草稿；此接口不写数据库。"""
    text = payload.transcription.strip()
    if not text:
        raise HTTPException(status_code=422, detail="转写文本不能为空")
    if payload.child_id is not None:
        try:
            await services.followup.ensure_child(db, user.id, payload.child_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        draft, provider, mocked = await services.followup.draft_from_transcription(text)
    except DraftGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return VoiceDraftResponse(draft=draft, provider=provider, mocked=mocked)


@router.post("/summary", response_model=FollowupSummaryOut, status_code=status.HTTP_201_CREATED)
async def create_summary(
    payload: FollowupSummaryRequest, db: DbSession, user: CurrentUser, services: ServicesDep
) -> FollowupSummaryOut:
    try:
        result = await services.followup.summarize(db, user.id, payload.child_id, payload.days)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(result.summary)
    return FollowupSummaryOut.model_validate(result.summary)


@router.get("/summaries", response_model=list[FollowupSummaryOut])
async def list_summaries(
    child_id: int, db: DbSession, user: CurrentUser, services: ServicesDep, limit: int = 10
) -> list[FollowupSummaryOut]:
    try:
        rows = await services.followup.list_summaries(db, user.id, child_id, min(limit, 50))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [FollowupSummaryOut.model_validate(item) for item in rows]
