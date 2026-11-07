"""本地 FunASR 识别实现。

模型加载放在第一次识别时进行，避免服务启动就被几 GB 权重拖住；
本模块不 import torch/funasr，只有真正调用时才会触发 ImportError，
从而让未安装模型的环境仍能正常启动，并在接口层返回明确的 503。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.asr.base import ASRError, ASRProvider, ASRUnavailableError, TranscriptionResult

logger = get_logger(__name__)


class FunASRProvider(ASRProvider):
    name = "funasr"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        try:
            from funasr import AutoModel
        except ImportError as exc:  # 未安装可选依赖
            raise ASRUnavailableError(
                "未安装 FunASR。请执行 pip install -r requirements-asr.txt，"
                "并确认模型权重已下载。"
            ) from exc
        try:
            kwargs = {
                "model": self.settings.asr_model,
                "device": self.settings.asr_device,
                "disable_update": True,
            }
            if self.settings.asr_vad_model:
                kwargs["vad_model"] = self.settings.asr_vad_model
            if self.settings.asr_punc_model:
                kwargs["punc_model"] = self.settings.asr_punc_model
            self._model = AutoModel(**kwargs)
        except Exception as exc:  # 模型下载/加载失败
            raise ASRUnavailableError(f"FunASR 模型加载失败：{exc}") from exc
        logger.info("FunASR 模型已加载: %s (%s)", self.settings.asr_model, self.settings.asr_device)
        return self._model

    async def transcribe(self, audio_path: Path) -> TranscriptionResult:
        model = await asyncio.to_thread(self._ensure_model)
        kwargs: dict[str, object] = {"input": str(audio_path)}
        # SenseVoice 支持 language/use_itn；Paraformer 不需要这些参数。
        if "sensevoice" in self.settings.asr_model.lower():
            kwargs["language"] = self.settings.asr_language or "auto"
            kwargs["use_itn"] = True
        try:
            output = await asyncio.to_thread(model.generate, **kwargs)
        except ASRError:
            raise
        except Exception as exc:
            raise ASRError(f"FunASR 识别失败：{exc}") from exc

        text = ""
        if isinstance(output, list) and output:
            item = output[0] or {}
            text = item.get("text") or item.get("sentence") or ""
        elif isinstance(output, dict):
            text = output.get("text") or ""
        return TranscriptionResult(
            text=str(text).strip(),
            provider=self.name,
            language=self.settings.asr_language,
        )

    def supported_formats(self) -> list[str]:
        return ["wav", "mp3", "m4a", "webm", "ogg", "flac"]

    async def health_check(self) -> bool:
        try:
            import funasr  # noqa: F401
        except ImportError:
            return False
        return True
