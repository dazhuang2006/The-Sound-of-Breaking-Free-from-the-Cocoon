"""未启用 TTS 时的占位实现。"""

from __future__ import annotations

from app.services.tts.base import SpeechResult, TTSProvider, TTSUnavailableError


class DisabledTTSProvider(TTSProvider):
    name = "disabled"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def synthesize(self, text: str, voice: str | None = None) -> SpeechResult:
        raise TTSUnavailableError(self.reason)

    def available(self) -> bool:
        return False

    def voices(self) -> list[str]:
        return []
