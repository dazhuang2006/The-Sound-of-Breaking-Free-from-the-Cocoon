"""硅基流动 CosyVoice2 文本转语音。"""

from __future__ import annotations

import httpx

from app.core.config import Settings
from app.services.tts.base import SpeechResult, TTSError, TTSProvider, TTSUnavailableError


class SiliconFlowTTSProvider(TTSProvider):
    name = "siliconflow"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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

    async def synthesize(self, text: str, voice: str | None = None) -> SpeechResult:
        if not self.available():
            raise TTSUnavailableError("未配置 TTS_API_KEY（或 ASR_HTTP_API_KEY）")
        payload = {
            "model": self.settings.tts_model,
            "input": text,
            "voice": voice or self.settings.tts_voice,
            "response_format": "mp3",
            "speed": self.settings.tts_speed,
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.tts_timeout_seconds,
                trust_env=self.settings.tts_trust_env,
            ) as client:
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
        return SpeechResult(
            audio=response.content,
            media_type=response.headers.get("content-type", "audio/mpeg"),
            provider=self.name,
        )
