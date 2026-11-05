"""安全事件审计接口（管理员）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DbSession, require_role
from app.db.models import SafetyEvent, User
from app.schemas.safety import SafetyEventOut

router = APIRouter(prefix="/safety", tags=["安全审计"])


@router.get("/events", response_model=list[SafetyEventOut])
async def list_events(
    db: DbSession,
    limit: int = 50,
    user: User = Depends(require_role("admin")),
) -> list[SafetyEventOut]:
    rows = await db.scalars(select(SafetyEvent).order_by(SafetyEvent.id.desc()).limit(min(limit, 200)))
    return [SafetyEventOut.model_validate(row) for row in rows]
