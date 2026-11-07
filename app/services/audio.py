"""音频文件校验与时长探测。

浏览器录音常见格式：WebM/Opus、Ogg/Opus、MP4/AAC、WAV、MP3。
不能只信扩展名与 Content-Type，所以先读文件头（magic bytes），再用 ffmpeg 解析时长。
"""

from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

ALLOWED_FORMATS: tuple[str, ...] = ("webm", "ogg", "mp4", "wav", "mp3", "flac")

_SUFFIX = {
    "webm": ".webm",
    "ogg": ".ogg",
    "mp4": ".m4a",
    "wav": ".wav",
    "mp3": ".mp3",
    "flac": ".flac",
}

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


class AudioValidationError(ValueError):
    """上传内容不是可接受的音频。"""


class AudioDecodeError(AudioValidationError):
    """有音频容器头但无法解析（损坏或伪装的文件）。"""


def sniff_audio(data: bytes) -> str | None:
    """根据文件头判断格式，返回 None 表示不在允许列表内。"""
    if len(data) < 12:
        return None
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[:4] == b"OggS":
        return "ogg"
    if data[4:8] == b"ftyp":
        return "mp4"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "mp3"
    if data[:4] == b"fLaC":
        return "flac"
    return None


def suffix_for(kind: str) -> str:
    return _SUFFIX.get(kind, ".bin")


def ensure_temp_dir(path: str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def new_temp_path(directory: Path, kind: str) -> Path:
    return directory / f"asr-{uuid.uuid4().hex}{suffix_for(kind)}"


def ffmpeg_available() -> bool:
    try:
        import imageio_ffmpeg

        return Path(imageio_ffmpeg.get_ffmpeg_exe()).exists()
    except Exception:
        return False


def _probe(path: Path) -> float | None:
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        process = subprocess.run(
            [exe, "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            errors="ignore",
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    stderr = process.stderr or ""
    match = _DURATION_RE.search(stderr)
    if match:
        hours, minutes, seconds = match.groups()
        return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 2)

    # 浏览器 MediaRecorder 生成的 WebM 常常没有 duration 元数据（Duration: N/A），
    # 这时解码一遍到 null，从进度输出里取最后一个 time=，仍然可以拿到真实时长。
    if "Duration: N/A" in stderr:
        try:
            decoded = subprocess.run(
                [exe, "-hide_banner", "-i", str(path), "-f", "null", "-"],
                capture_output=True,
                text=True,
                errors="ignore",
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        times = _TIME_RE.findall(decoded.stderr or "")
        if not times:
            return None
        hours, minutes, seconds = times[-1]
        return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds), 2)
    return None


async def probe_duration(path: Path) -> float | None:
    import asyncio

    return await asyncio.to_thread(_probe, path)
