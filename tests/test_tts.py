"""TTS 接口测试。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.tts.base import SpeechResult, TTSProvider
from app.services.tts.disabled import DisabledTTSProvider


class FakeTTS(TTSProvider):
    name = "fake"

    async def synthesize(self, text: str, voice: str | None = None) -> SpeechResult:
        return SpeechResult(audio=b"ID3-fake-mp3-bytes", media_type="audio/mpeg", provider=self.name)

    def available(self) -> bool:
        return True

    def voices(self) -> list[str]:
        return ["fake:voice"]


@pytest.fixture
def use_tts(client: TestClient):
    services = client.app.state.services
    original = services.tts

    def _install(provider: TTSProvider) -> TTSProvider:
        services.tts = provider
        return provider

    yield _install
    services.tts = original


def test_tts_success(client: TestClient, account: dict, use_tts):
    use_tts(FakeTTS())
    response = client.post(
        "/api/v1/audio/speech",
        json={"text": "你好，我是破茧之声。"},
        headers=account["headers"],
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/mpeg")
    assert response.content.startswith(b"ID3")


def test_tts_requires_auth(client: TestClient, use_tts):
    use_tts(FakeTTS())
    response = client.post("/api/v1/audio/speech", json={"text": "你好"})
    assert response.status_code == 401


def test_tts_disabled_returns_503(client: TestClient, account: dict, use_tts):
    use_tts(DisabledTTSProvider("TTS 未启用"))
    response = client.post(
        "/api/v1/audio/speech",
        json={"text": "你好"},
        headers=account["headers"],
    )
    assert response.status_code == 503
    assert "TTS" in response.json()["detail"]


def test_tts_rejects_blank_text(client: TestClient, account: dict, use_tts):
    use_tts(FakeTTS())
    response = client.post(
        "/api/v1/audio/speech",
        json={"text": "   "},
        headers=account["headers"],
    )
    assert response.status_code == 422


def test_tts_rejects_too_long(client: TestClient, account: dict, use_tts):
    services = client.app.state.services
    original = services.settings.tts_max_chars
    services.settings.tts_max_chars = 5
    use_tts(FakeTTS())
    try:
        response = client.post(
            "/api/v1/audio/speech",
            json={"text": "这是一段超过五个字的文本"},
            headers=account["headers"],
        )
        assert response.status_code == 422
    finally:
        services.settings.tts_max_chars = original


def test_tts_health(client: TestClient, use_tts):
    use_tts(FakeTTS())
    response = client.get("/api/v1/audio/tts/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "fake"
    assert payload["available"] is True
    assert payload["voices"] == ["fake:voice"]
