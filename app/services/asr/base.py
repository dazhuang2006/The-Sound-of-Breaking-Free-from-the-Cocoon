"""语音识别（ASR）能力抽象。

业务接口只依赖 `ASRProvider`，不直接绑定 FunASR / 云端 SDK：
- FunASRProvider：本地中文识别（按需安装）
- HttpASRProvider：OpenAI Whisper 兼容的 /audio/transcriptions
- DisabledASRProvider：未配置时明确报错，绝不返回伪造文本
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


class ASRError(RuntimeError):
    """识别过程中的可预期错误（模型异常、服务返回错误等）。"""


class ASRUnavailableError(ASRError):
    """未安装模型或未配置服务，属于部署问题。"""


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    provider: str
    duration: float | None = None
    language: str | None = None


class ASRProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """把本地音频文件转成文字。失败时必须抛 ASRError，不得返回占位文本。"""

    @abstractmethod
    def supported_formats(self) -> list[str]:
        """返回支持的音频扩展名（不带点）。"""

    @abstractmethod
    async def health_check(self) -> bool:
        """只检查依赖是否就绪，不触发模型下载。"""
