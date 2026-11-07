"""语音识别接口。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, HTTPException, Response, UploadFile

from app.api.deps import CurrentUser, ServicesDep
from app.core.logging import get_logger
from app.schemas.audio import AudioHealthResponse, TranscriptionResponse
from app.schemas.tts import SpeechRequest, TTSHealthResponse
from app.services.asr import ASRError, ASRUnavailableError
from app.services.audio import (
    ALLOWED_FORMATS,
    AudioDecodeError,
    AudioValidationError,
    ensure_temp_dir,
    ffmpeg_available,
    new_temp_path,
    probe_duration,
    sniff_audio,
)
from app.services.tts import TTSError, TTSUnavailableError

logger = get_logger(__name__)

router = APIRouter(prefix="/audio", tags=["语音识别"])


@router.get("/health", response_model=AudioHealthResponse)
async def audio_health(services: ServicesDep) -> AudioHealthResponse:
    settings = services.settings
    return AudioHealthResponse(
        provider=services.asr.name,
        available=await services.asr.health_check(),
        supported_formats=services.asr.supported_formats() or list(ALLOWED_FORMATS),
        max_upload_mb=settings.asr_max_upload_mb,
        max_duration_seconds=settings.asr_max_duration_seconds,
    )


@router.get("/tts/health", response_model=TTSHealthResponse)
async def tts_health(services: ServicesDep) -> TTSHealthResponse:
    return TTSHealthResponse(
        provider=services.tts.name,
        available=services.tts.available(),
        voices=services.tts.voices(),
        default_voice=services.settings.tts_voice,
        max_chars=services.settings.tts_max_chars,
    )


@router.post("/speech")
async def synthesize_speech(
    payload: SpeechRequest,
    user: CurrentUser,
    services: ServicesDep,
) -> Response:
    """把 AI 回答合成为语音；音频直接在响应体返回，不落盘。"""
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="朗读文本不能为空")
    if len(text) > services.settings.tts_max_chars:
        raise HTTPException(
            status_code=422,
            detail=f"朗读文本超过 {services.settings.tts_max_chars} 字限制，请分段朗读",
        )
    try:
        result = await services.tts.synthesize(text, payload.voice)
    except TTSUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TTSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(
        content=result.audio,
        media_type=result.media_type,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    user: CurrentUser,
    services: ServicesDep,
    file: UploadFile = File(..., description="浏览器录制的音频文件"),
) -> TranscriptionResponse:
    """上传音频并转写。

    音频只在内存/临时目录中处理，转写结束立即删除；日志不记录转写正文。
    """
    settings = services.settings
    max_bytes = int(settings.asr_max_upload_mb * 1024 * 1024)
    data = await file.read(max_bytes + 1)
    if not data:
        raise HTTPException(status_code=422, detail="音频文件为空")
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"音频文件超过 {settings.asr_max_upload_mb:g} MB 限制",
        )

    kind = sniff_audio(data)
    if kind is None:
        raise HTTPException(
            status_code=415,
            detail="不支持的音频格式，请使用 WebM / OGG / MP4 / WAV / MP3 / FLAC",
        )

    directory = ensure_temp_dir(settings.asr_temp_dir)
    path = new_temp_path(directory, kind)
    path.write_bytes(data)
    try:
        duration = await probe_duration(path)
        if duration is None:
            if ffmpeg_available():
                raise AudioDecodeError("音频无法解析，可能已损坏或格式伪装")
            logger.warning("ffmpeg 不可用，跳过时长校验")
        elif duration > settings.asr_max_duration_seconds:
            raise HTTPException(
                status_code=422,
                detail=f"录音时长 {duration:g} 秒，超过 {settings.asr_max_duration_seconds:g} 秒限制",
            )

        try:
            result = await asyncio.wait_for(
                services.asr.transcribe(path), timeout=settings.asr_timeout_seconds
            )
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail="语音识别超时，请重试") from exc
        except ASRUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ASRError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        if not result.text.strip():
            raise HTTPException(status_code=422, detail="未识别到语音内容，请靠近麦克风重试")
        logger.info(
            "ASR 完成 provider=%s bytes=%d duration=%s chars=%d",
            result.provider,
            len(data),
            duration,
            len(result.text),
        )
        return TranscriptionResponse(
            transcription=result.text.strip(),
            duration=duration or result.duration,
            provider=result.provider,
            language=result.language,
        )
    except AudioValidationError as exc:
        logger.warning("音频校验失败: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)
