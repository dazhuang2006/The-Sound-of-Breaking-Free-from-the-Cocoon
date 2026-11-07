"""语音识别接口模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    success: bool = True
    transcription: str
    duration: float | None = None
    provider: str
    language: str | None = None


class AudioHealthResponse(BaseModel):
    provider: str
    available: bool
    supported_formats: list[str] = Field(default_factory=list)
    max_upload_mb: float
    max_duration_seconds: float
