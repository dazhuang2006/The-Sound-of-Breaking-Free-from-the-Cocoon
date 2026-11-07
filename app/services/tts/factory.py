"""TTS Provider 工厂。"""

from __future__ import annotations

from app.core.config import Settings
from app.services.tts.base import TTSProvider
from app.services.tts.disabled import DisabledTTSProvider
from app.services.tts.siliconflow_provider import SiliconFlowTTSProvider


def build_tts(settings: Settings) -> TTSProvider:
    if settings.tts_provider == "siliconflow":
        return SiliconFlowTTSProvider(settings)
    return DisabledTTSProvider("TTS 未启用：设置 TTS_PROVIDER=siliconflow 与 TTS_API_KEY")
