"""TTS 能力包。"""

from app.services.tts.base import SpeechResult, TTSError, TTSProvider, TTSUnavailableError
from app.services.tts.factory import build_tts

__all__ = [
    "SpeechResult",
    "TTSError",
    "TTSProvider",
    "TTSUnavailableError",
    "build_tts",
]
