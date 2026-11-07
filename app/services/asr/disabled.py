"""未启用 ASR 时的占位实现：只报错，不伪造结果。"""

from __future__ import annotations

from pathlib import Path

from app.services.asr.base import ASRProvider, ASRUnavailableError, TranscriptionResult


class DisabledASRProvider(ASRProvider):
    name = "disabled"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def transcribe(self, audio_path: Path) -> TranscriptionResult:
        raise ASRUnavailableError(self.reason)

    def supported_formats(self) -> list[str]:
        return []

    async def health_check(self) -> bool:
        return False
