"""FastAPI 依赖：数据库会话、当前用户、服务容器。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenError, decode_access_token
from app.db.base import get_db
from app.db.models import User
from app.services.container import Services

bearer = HTTPBearer(auto_error=False, description="Bearer <access_token>")

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_services(request: Request) -> Services:
    services = getattr(request.app.state, "services", None)
    if services is None:  # 理论上不会发生：lifespan 已构建
        raise HTTPException(status_code=503, detail="服务尚未初始化")
    return services


ServicesDep = Annotated[Services, Depends(get_services)]


async def get_current_user(
    db: DbSession,
    services: ServicesDep,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials, secret_key=services.settings.secret_key)
    except TokenError:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录") from None
    subject = payload.get("sub")
    user = await db.get(User, int(subject)) if subject and str(subject).isdigit() else None
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):
    async def _checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return user

    return _checker
