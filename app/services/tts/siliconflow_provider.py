"""硅基流动 CosyVoice2 文本转语音。

实测延迟主要来自服务端推理（1–3.5 秒，与文本长度基本无关），网络本身只占 ~80ms。
所以这里做两件在服务器侧能控制的事：

1. **复用 httpx.AsyncClient**：keep-alive，省掉每次请求 70–80ms 的 TLS 握手；
2. **进程内 LRU 缓存**：相同（文本, 音色, 语速）直接返回上次的音频，毫秒级命中。

缓存按条数与总字节双重上限淘汰，避免长会话把内存吃满。
"""

from __future__ import annotations

import asyncio
import hashlib
from collections import OrderedDict
from pathlib import Path

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.tts.base import SpeechResult, TTSError, TTSProvider, TTSUnavailableError

logger = get_logger(__name__)

# 一次演示里反复朗读的多半是同一批句子，48 条 × ~100KB ≈ 5MB，足够覆盖
_CACHE_MAX_ITEMS = 48
_CACHE_MAX_BYTES = 8 * 1024 * 1024


class _AudioCache:
    """带字节上限的 LRU，缓存的是已经合成好的 mp3。"""

    def __init__(self) -> None:
        self._items: OrderedDict[str, SpeechResult] = OrderedDict()
        self._bytes = 0
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> SpeechResult | None:
        async with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            self._items.move_to_end(key)
            return item

    async def put(self, key: str, result: SpeechResult) -> None:
        async with self._lock:
            if key in self._items:
                self._items.move_to_end(key)
                return
            self._items[key] = result
            self._bytes += len(result.audio)
            while self._items and (
                len(self._items) > _CACHE_MAX_ITEMS or self._bytes > _CACHE_MAX_BYTES
            ):
                _, dropped = self._items.popitem(last=False)
                self._bytes -= len(dropped.audio)

    async def stats(self) -> dict[str, int]:
        async with self._lock:
            return {"entries": len(self._items), "bytes": self._bytes}


class SiliconFlowTTSProvider(TTSProvider):
    name = "siliconflow"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache = _AudioCache()
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    def _api_key(self) -> str:
        return self.settings.tts_api_key or self.settings.asr_http_api_key

    def available(self) -> bool:
        return bool(self.settings.tts_base_url and self._api_key())

    def voices(self) -> list[str]:
        return [
            "FunAudioLLM/CosyVoice2-0.5B:diana",
            "FunAudioLLM/CosyVoice2-0.5B:claire",
            "FunAudioLLM/CosyVoice2-0.5B:alex",
        ]

    async def cache_stats(self) -> dict[str, int]:
        return await self._cache.stats()

    async def _get_client(self) -> httpx.AsyncClient:
        """懒加载并复用连接池；不设 total 超时，读超时单独控制。"""
        if self._client is not None and not self._client.is_closed:
            return self._client
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=5.0,
                        read=min(self.settings.tts_timeout_seconds, 30.0),
                        write=10.0,
                        pool=5.0,
                    ),
                    limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
                    trust_env=self.settings.tts_trust_env,
                )
        return self._client

    def _cache_key(self, text: str, voice: str) -> str:
        raw = f"{self.settings.tts_model}|{voice}|{self.settings.tts_speed}|{text}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    async def synthesize(self, text: str, voice: str | None = None) -> SpeechResult:
        if not self.available():
            raise TTSUnavailableError("未配置 TTS_API_KEY（或 ASR_HTTP_API_KEY）")
        voice = voice or self.settings.tts_voice
        key = self._cache_key(text, voice)

        cached = await self._cache.get(key)
        if cached is not None:
            logger.info("TTS 命中内存缓存 voice=%s chars=%d", voice, len(text))
            return SpeechResult(
                audio=cached.audio,
                media_type=cached.media_type,
                provider=self.name,
                cached=True,
            )

        disk = await self._read_disk(key)
        if disk is not None:
            logger.info("TTS 命中磁盘缓存 voice=%s chars=%d", voice, len(text))
            await self._cache.put(key, disk)
            return disk

        payload = {
            "model": self.settings.tts_model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
            "speed": self.settings.tts_speed,
        }
        client = await self._get_client()
        try:
            response = await client.post(
                self.settings.tts_base_url,
                headers={"Authorization": f"Bearer {self._api_key()}"},
                json=payload,
            )
        except httpx.HTTPError as exc:
            raise TTSError(f"调用 TTS 服务失败：{exc}") from exc
        if response.status_code >= 400:
            raise TTSError(f"TTS 服务返回 {response.status_code}")
        if not response.content:
            raise TTSError("TTS 服务返回空音频")

        result = SpeechResult(
            audio=response.content,
            media_type=response.headers.get("content-type", "audio/mpeg"),
            provider=self.name,
            cached=False,
        )
        await self._cache.put(key, result)
        await self._write_disk(key, result.audio)
        return result

    # ---------------------------------------------------------------- 磁盘缓存
    def _disk_path(self, key: str) -> Path | None:
        if not self.settings.tts_cache_enabled:
            return None
        return Path(self.settings.tts_cache_dir) / f"{key}.mp3"

    async def _read_disk(self, key: str) -> SpeechResult | None:
        path = self._disk_path(key)
        if path is None or not path.is_file():
            return None
        try:
            data = await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            logger.debug("TTS 磁盘缓存读取失败: %s", exc)
            return None
        if not data:
            return None
        return SpeechResult(audio=data, media_type="audio/mpeg", provider=self.name, cached=True)

    async def _write_disk(self, key: str, audio: bytes) -> None:
        path = self._disk_path(key)
        if path is None:
            return
        try:
            await asyncio.to_thread(self._write_disk_sync, path, audio)
        except OSError as exc:  # 缓存写失败不影响主流程
            logger.debug("TTS 磁盘缓存写入失败: %s", exc)

    @staticmethod
    def _write_disk_sync(path: Path, audio: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(audio)
        tmp.replace(path)
        # 简单裁剪：文件数超过 300 时删最旧的一半，避免长期运行撑大磁盘
        files = sorted(path.parent.glob("*.mp3"), key=lambda item: item.stat().st_mtime)
        if len(files) > 300:
            for old in files[: len(files) - 300]:
                try:
                    old.unlink()
                except OSError:
                    pass
