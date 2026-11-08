"""异步数据库引擎与会话管理。

引擎延迟创建，保证测试可以通过环境变量替换 DATABASE_URL 后再初始化。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _engine_kwargs(url: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"echo": get_settings().db_echo, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
    return kwargs


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = get_settings().database_url
        if url.startswith("sqlite"):
            # 确保 SQLite 文件所在目录存在
            raw = url.split("///", 1)[-1]
            if raw and raw != ":memory:":
                Path(raw).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(url, **_engine_kwargs(url))
        if url.startswith("sqlite"):

            @event.listens_for(_engine.sync_engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, _record):  # pragma: no cover - 驱动回调
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                # 并发写时最多等 5 秒而不是立刻抛 "database is locked"
                cursor.execute("PRAGMA busy_timeout=5000")
                # WAL 下用 NORMAL 兼顾安全与写入速度
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

        logger.info("数据库引擎已创建: %s", url)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    from app.db import models  # noqa: F401  确保模型已注册

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据表已就绪: %s", ", ".join(sorted(Base.metadata.tables)))


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
