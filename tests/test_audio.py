"""语音识别与随访草稿接口测试。

ASR 使用显式注入的 Fake Provider（测试专用），生产路径不会回退到假结果；
真实音频用程序生成的 WAV，确保时长探测、格式校验走的是实际代码。
"""

from __future__ import annotations

import asyncio
import io
import wave

import pytest
from fastapi.testclient import TestClient

from app.services.asr.base import ASRProvider, TranscriptionResult
from app.services.asr.disabled import DisabledASRProvider
from app.services.audio import sniff_audio


def make_wav(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * int(sample_rate * seconds))
    return buffer.getvalue()


class FakeASR(ASRProvider):
    name = "fake"

    def __init__(self, text: str = "今天孩子主动和我打招呼了。", delay: float = 0.0) -> None:
        self.text = text
        self.delay = delay
        self.calls = 0

    async def transcribe(self, audio_path) -> TranscriptionResult:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        assert audio_path.exists()
        return TranscriptionResult(text=self.text, provider=self.name, duration=1.0, language="zh")

    def supported_formats(self) -> list[str]:
        return ["wav"]

    async def health_check(self) -> bool:
        return True


@pytest.fixture
def use_asr(client: TestClient):
    services = client.app.state.services
    original = services.asr

    def _install(provider: ASRProvider) -> ASRProvider:
        services.asr = provider
        return provider

    yield _install
    services.asr = original


@pytest.fixture
def audio_settings(client: TestClient):
    settings = client.app.state.services.settings
    snapshot = (
        settings.asr_max_upload_mb,
        settings.asr_max_duration_seconds,
        settings.asr_timeout_seconds,
    )
    yield settings
    (
        settings.asr_max_upload_mb,
        settings.asr_max_duration_seconds,
        settings.asr_timeout_seconds,
    ) = snapshot


def test_sniff_audio_headers():
    assert sniff_audio(make_wav(0.1)) == "wav"
    assert sniff_audio(b"\x1a\x45\xdf\xa3" + b"\x00" * 20) == "webm"
    assert sniff_audio(b"OggS" + b"\x00" * 20) == "ogg"
    assert sniff_audio(b"not-an-audio-file") is None


def test_transcribe_success(
    client: TestClient, account: dict, use_asr, audio_settings
):
    fake = use_asr(FakeASR())
    response = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("voice.wav", make_wav(1.0), "audio/wav")},
        headers=account["headers"],
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["transcription"] == "今天孩子主动和我打招呼了。"
    assert payload["provider"] == "fake"
    assert payload["duration"] == pytest.approx(1.0, abs=0.2)
    assert fake.calls == 1


def test_transcribe_requires_auth(client: TestClient, use_asr):
    use_asr(FakeASR())
    response = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("voice.wav", make_wav(0.5), "audio/wav")},
    )
    assert response.status_code == 401


def test_transcribe_rejects_unknown_format(client: TestClient, account: dict, use_asr):
    use_asr(FakeASR())
    response = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("note.txt", b"hello world, not audio", "text/plain")},
        headers=account["headers"],
    )
    assert response.status_code == 415


def test_transcribe_rejects_empty_file(client: TestClient, account: dict, use_asr):
    use_asr(FakeASR())
    response = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("voice.wav", b"", "audio/wav")},
        headers=account["headers"],
    )
    assert response.status_code == 422


def test_transcribe_rejects_oversize(client: TestClient, account: dict, use_asr, audio_settings):
    use_asr(FakeASR())
    audio_settings.asr_max_upload_mb = 0.001
    response = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("voice.wav", make_wav(1.0), "audio/wav")},
        headers=account["headers"],
    )
    assert response.status_code == 413


def test_transcribe_rejects_too_long(client: TestClient, account: dict, use_asr, audio_settings):
    use_asr(FakeASR())
    audio_settings.asr_max_duration_seconds = 0.5
    response = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("voice.wav", make_wav(1.0), "audio/wav")},
        headers=account["headers"],
    )
    assert response.status_code == 422
    assert "时长" in response.json()["detail"]


def test_disabled_asr_returns_503(client: TestClient, account: dict, use_asr):
    use_asr(DisabledASRProvider("未安装 FunASR"))
    response = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("voice.wav", make_wav(0.5), "audio/wav")},
        headers=account["headers"],
    )
    assert response.status_code == 503
    assert "FunASR" in response.json()["detail"]


def test_asr_timeout_returns_504(client: TestClient, account: dict, use_asr, audio_settings):
    use_asr(FakeASR(delay=1.0))
    audio_settings.asr_timeout_seconds = 0.05
    response = client.post(
        "/api/v1/audio/transcribe",
        files={"file": ("voice.wav", make_wav(0.5), "audio/wav")},
        headers=account["headers"],
    )
    assert response.status_code == 504


def test_audio_health(client: TestClient, use_asr):
    use_asr(FakeASR())
    response = client.get("/api/v1/audio/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "fake"
    assert payload["available"] is True
    assert payload["max_duration_seconds"] > 0


def test_voice_draft_structure(client: TestClient, account: dict, child: dict):
    transcription = (
        "今天上午带他去公园玩。下午做了拼图训练，完成了三张。"
        "他情绪比较平静，主动说了两次谢谢。"
    )
    response = client.post(
        "/api/v1/followup/voice-draft",
        json={"transcription": transcription, "child_id": child["id"]},
        headers=account["headers"],
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    draft = payload["draft"]
    assert set(draft) == {
        "date",
        "daily_activities",
        "training_content",
        "behavior_observations",
        "emotional_state",
        "communication_performance",
        "parent_notes",
    }
    assert draft["daily_activities"]
    assert draft["training_content"]
    assert payload["mocked"] is True  # 测试环境使用 Mock LLM，响应需明确标记


def test_voice_draft_blank_transcription(client: TestClient, account: dict):
    response = client.post(
        "/api/v1/followup/voice-draft",
        json={"transcription": "   "},
        headers=account["headers"],
    )
    assert response.status_code == 422


def test_voice_draft_cross_child_denied(client: TestClient, account: dict, child: dict):
    other = client.post(
        "/api/v1/auth/register",
        json={"username": "voice_intruder", "password": "secret123"},
    ).json()
    response = client.post(
        "/api/v1/followup/voice-draft",
        json={"transcription": "今天做了拼图训练。", "child_id": child["id"]},
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert response.status_code == 404


def test_voice_draft_requires_auth(client: TestClient):
    response = client.post(
        "/api/v1/followup/voice-draft", json={"transcription": "今天做了拼图训练。"}
    )
    assert response.status_code == 401
