"""TTS 接口模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    voice: str | None = None


class TTSHealthResponse(BaseModel):
    provider: str
    available: bool
    voices: list[str] = Field(default_factory=list)
    default_voice: str = ""
    max_chars: int
