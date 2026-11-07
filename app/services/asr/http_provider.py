"""云端 ASR：兼容 OpenAI Whisper /audio/transcriptions 的服务。"""

from __future__ import annotations

from pathlib import Path

import httpx

from app.core.config import Settings
from app.services.asr.base import ASRError, ASRProvider, ASRUnavailableError, TranscriptionResult


class HttpASRProvider(ASRProvider):
    name = "http"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if not self.settings.asr_http_url:
            raise ASRUnavailableError("ASR_HTTP_URL 未配置")
        headers = {}
        if self.settings.asr_http_api_key:
            headers["Authorization"] = f"Bearer {self.settings.asr_http_api_key}"
        try:
            with audio_path.open("rb") as handle:
                files = {"file": (audio_path.name, handle, "application/octet-stream")}
                data = {
                    "model": self.settings.asr_http_model,
                    "language": self.settings.asr_language,
                }
                async with httpx.AsyncClient(
                    timeout=self.settings.asr_timeout_seconds,
                    trust_env=self.settings.asr_http_trust_env,
                ) as client:
                    response = await client.post(
                        self.settings.asr_http_url, headers=headers, files=files, data=data
                    )
        except httpx.HTTPError as exc:
            raise ASRError(f"调用云端 ASR 失败：{exc}") from exc
        if response.status_code >= 400:
            raise ASRError(f"云端 ASR 返回 {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ASRError("云端 ASR 返回的不是 JSON") from exc
        text = payload.get("text") or payload.get("transcription") or ""
        usage = payload.get("usage") or {}
        duration = payload.get("duration") or usage.get("seconds")
        return TranscriptionResult(
            text=str(text).strip(),
            provider=self.name,
            duration=float(duration) if isinstance(duration, (int, float)) else None,
            language=self.settings.asr_language,
        )

    def supported_formats(self) -> list[str]:
        return ["wav", "mp3", "m4a", "webm", "ogg", "flac"]

    async def health_check(self) -> bool:
        return bool(self.settings.asr_http_url)
