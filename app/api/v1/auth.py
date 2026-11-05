"""认证接口。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, ServicesDep
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["认证"])


def _token_response(user: User, services) -> TokenResponse:
    minutes = services.settings.access_token_expire_minutes
    token = create_access_token(user.id, secret_key=services.settings.secret_key, expires_minutes=minutes)
    return TokenResponse(
        access_token=token,
        expires_in=minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: DbSession, services: ServicesDep) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.username == payload.username))
    if existing is not None:
        raise HTTPException(status_code=409, detail="该用户名已被注册")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip() or "家长",
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    await db.commit()
    return _token_response(user, services)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: DbSession, services: ServicesDep) -> TokenResponse:
    user = await db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return _token_response(user, services)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
