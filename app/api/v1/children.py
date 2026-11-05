"""孩子档案接口。"""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.db.models import Child
from app.schemas.children import ChildCreate, ChildOut

router = APIRouter(prefix="/children", tags=["孩子档案"])


@router.post("", response_model=ChildOut, status_code=status.HTTP_201_CREATED)
async def create_child(payload: ChildCreate, db: DbSession, user: CurrentUser) -> ChildOut:
    child = Child(
        user_id=user.id,
        nickname=payload.nickname.strip(),
        birth_date=payload.birth_date,
        profile_note=payload.profile_note,
    )
    db.add(child)
    await db.flush()
    await db.refresh(child)
    await db.commit()
    return ChildOut.model_validate(child)


@router.get("", response_model=list[ChildOut])
async def list_children(db: DbSession, user: CurrentUser) -> list[ChildOut]:
    rows = await db.scalars(select(Child).where(Child.user_id == user.id).order_by(Child.id))
    return [ChildOut.model_validate(row) for row in rows]
