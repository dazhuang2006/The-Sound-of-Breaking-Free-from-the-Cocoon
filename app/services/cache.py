"""会话缓存：Redis 优先，进程内 TTL 缓存兜底。

缓存只用于加速（最近对话、当前模式、训练进度快照），
事实数据始终以 MySQL/SQLite 为准，缓存丢失不影响正确性。
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheBackend(ABC):
    name: str = "base"

    @abstractmethod
    async def get(self, key: str) -> str | None: ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self.set(key, json.dumps(value, ensure_ascii=False, default=str), ttl)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:  # pragma: no cover
        return None


class MemoryCache(CacheBackend):
    name = "memory"

    def __init__(self, default_ttl: int = 1800) -> None:
        self._data: dict[str, tuple[float, str]] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    def _purge(self) -> None:
        now = time.monotonic()
        expired = [key for key, (exp, _) in self._data.items() if exp < now]
        for key in expired:
            self._data.pop(key, None)

    async def get(self, key: str) -> str | None:
        async with self._lock:
            self._purge()
            item = self._data.get(key)
            return item[1] if item else None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        async with self._lock:
            self._data[key] = (time.monotonic() + (ttl or self._default_ttl), value)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)


class RedisCache(CacheBackend):
    name = "redis"

    def __init__(self, client: Any, default_ttl: int = 1800) -> None:
        self._client = client
        self._default_ttl = default_ttl

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self._client.set(key, value, ex=ttl or self._default_ttl)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def aclose(self) -> None:
        await self._client.aclose()


async def build_cache(settings: Settings) -> CacheBackend:
    if not settings.cache_enabled:
        return MemoryCache(settings.cache_ttl_seconds)
    try:
        import redis.asyncio as redis

        client = redis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True, socket_connect_timeout=1.5
        )
        await client.ping()
        logger.info("Redis 缓存已连接: %s", settings.redis_url)
        return RedisCache(client, settings.cache_ttl_seconds)
    except Exception as exc:
        logger.warning("Redis 不可用，降级为进程内缓存: %s", exc)
        return MemoryCache(settings.cache_ttl_seconds)


def session_cache_key(session_id: str) -> str:
    return f"pojian:session:{session_id}:recent"
