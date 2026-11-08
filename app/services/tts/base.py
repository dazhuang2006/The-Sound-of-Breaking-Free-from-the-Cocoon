"""TTS（文本转语音）能力抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class TTSError(RuntimeError):
    """语音合成失败。"""


class TTSUnavailableError(TTSError):
    """未配置或未安装 TTS 服务。"""


@dataclass(slots=True)
class SpeechResult:
    audio: bytes
    media_type: str
    provider: str
    cached: bool = False


class TTSProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def synthesize(self, text: str, voice: str | None = None) -> SpeechResult:
        """把文本合成为音频字节；失败必须抛 TTSError。"""

    @abstractmethod
    def available(self) -> bool:
        """配置是否完整（不发网络请求）。"""

    @abstractmethod
    def voices(self) -> list[str]:
        """可用的音色标识。"""
