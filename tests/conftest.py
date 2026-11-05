"""pytest 公共配置：在导入应用前固定测试环境（SQLite 临时库、Mock LLM、内存向量库）。"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

TMP_DIR = Path(tempfile.mkdtemp(prefix="pojian-test-"))

os.environ.update(
    {
        "ENV": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{(TMP_DIR / 'test.db').as_posix()}",
        "KB_INDEX_PATH": str(TMP_DIR / "kb.json"),
        "KB_DIR": "knowledge",
        "CACHE_ENABLED": "false",
        "LLM_PROVIDER": "mock",
        "EMBEDDING_PROVIDER": "hash",
        "EMBEDDING_DIM": "256",
        "VECTOR_BACKEND": "memory",
        "SECRET_KEY": "test-secret-key-please-change-32bytes",
        "RAG_MIN_SCORE": "0.05",
        "AUTO_CREATE_TABLES": "true",
        "DEBUG": "false",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def account(client: TestClient) -> dict:
    username = f"user_{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "secret123", "display_name": "测试家长"},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return {
        "headers": {"Authorization": f"Bearer {payload['access_token']}"},
        "user": payload["user"],
        "token": payload["access_token"],
    }


@pytest.fixture
def child(client: TestClient, account: dict) -> dict:
    response = client.post(
        "/api/v1/children",
        json={
            "nickname": "测试宝宝",
            "birth_date": "2021-03-01",
            "profile_note": "4 岁，能说少量单词，喜欢拼图，对声音敏感。",
        },
        headers=account["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()
