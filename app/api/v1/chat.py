"""对话接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, ServicesDep
from app.db.models import ChatMessage, ChatSession
from app.schemas.chat import ChatRequest, ChatResponse, MessageOut, SessionDetail, SessionOut
from app.schemas.common import MessageResponse
from app.services.chat import chat_service

router = APIRouter(prefix="/chat", tags=["对话"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest, db: DbSession, user: CurrentUser, services: ServicesDep
) -> ChatResponse:
    try:
        return await chat_service.handle(
            db,
            user,
            services,
            message=payload.message,
            session_id=payload.session_id,
            child_id=payload.child_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(db: DbSession, user: CurrentUser) -> list[SessionOut]:
    rows = await db.scalars(
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .limit(50)
    )
    return [SessionOut.model_validate(row) for row in rows]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: DbSession, user: CurrentUser) -> SessionDetail:
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.asc())
        .limit(300)
    )
    detail = SessionDetail(
        id=session.id,
        title=session.title,
        mode=session.mode,
        child_id=session.child_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[MessageOut.model_validate(item) for item in messages],
    )
    return detail


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: str, db: DbSession, user: CurrentUser, services: ServicesDep
) -> MessageResponse:
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.delete(session)
    await services.cache.delete(f"pojian:session:{session_id}:recent")
    return MessageResponse(message="会话已删除")


@router.get("/intents", response_model=list[str], include_in_schema=False)
async def intents() -> list[str]:
    return ["qa", "training_start", "training_turn", "training_end", "followup_record", "followup_summary", "chat", "safety"]
