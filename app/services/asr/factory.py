"""ASR Provider 工厂。"""

from __future__ import annotations

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.asr.base import ASRProvider
from app.services.asr.disabled import DisabledASRProvider
from app.services.asr.funasr_provider import FunASRProvider
from app.services.asr.http_provider import HttpASRProvider

logger = get_logger(__name__)

_DISABLED_REASON = (
    "语音识别未启用：安装 pip install -r requirements-asr.txt 并设置 "
    "ASR_PROVIDER=funasr；或配置 ASR_PROVIDER=http 与 ASR_HTTP_URL。"
)


def build_asr(settings: Settings) -> ASRProvider:
    if settings.asr_provider == "funasr":
        return FunASRProvider(settings)
    if settings.asr_provider == "http":
        if not settings.asr_http_url:
            logger.warning("ASR_PROVIDER=http 但 ASR_HTTP_URL 为空，语音接口将返回 503")
            return DisabledASRProvider("ASR_PROVIDER=http 但未配置 ASR_HTTP_URL")
        return HttpASRProvider(settings)
    return DisabledASRProvider(_DISABLED_REASON)
