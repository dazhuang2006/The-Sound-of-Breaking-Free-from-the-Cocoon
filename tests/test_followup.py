"""随访接口测试：记录、聚合指标、阶段小结、越权访问。"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _create_child(client: TestClient, headers: dict, nickname: str = "小满") -> int:
    response = client.post(
        "/api/v1/children",
        json={"nickname": nickname, "birth_date": "2020-08-01", "profile_note": "喜欢数字"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_followup_records_and_summary(client: TestClient, account: dict):
    headers = account["headers"]
    child_id = _create_child(client, headers)
    today = date.today()
    samples = [
        (today - timedelta(days=2), 2, 8.0, 40),
        (today - timedelta(days=1), 3, 9.0, 60),
        (today, 4, 10.0, 80),
    ]
    for day, mood, sleep, completion in samples:
        response = client.post(
            "/api/v1/followup/records",
            json={
                "child_id": child_id,
                "record_date": day.isoformat(),
                "mood": mood,
                "sleep_hours": sleep,
                "completion": completion,
                "behavior": "晚饭后情绪平稳",
                "training_items": ["图片时间表", "道谢练习"],
                "interaction": "和妈妈一起读了绘本",
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text

    listed = client.get(
        f"/api/v1/followup/records?child_id={child_id}&days=7", headers=headers
    ).json()
    assert len(listed) == 3

    summary = client.post(
        "/api/v1/followup/summary",
        json={"child_id": child_id, "days": 7},
        headers=headers,
    )
    assert summary.status_code == 201, summary.text
    payload = summary.json()
    metrics = payload["metrics"]
    assert metrics["record_count"] == 3
    assert metrics["avg_mood"] == 3.0
    assert metrics["avg_sleep_hours"] == 9.0
    assert metrics["avg_completion"] == 60
    assert "仅供居家辅助参考" in payload["content"]

    summaries = client.get(
        f"/api/v1/followup/summaries?child_id={child_id}", headers=headers
    ).json()
    assert summaries and summaries[0]["id"] == payload["id"]


def test_summary_requires_records(client: TestClient, account: dict):
    headers = account["headers"]
    child_id = _create_child(client, headers, nickname="无记录")
    response = client.post(
        "/api/v1/followup/summary", json={"child_id": child_id, "days": 7}, headers=headers
    )
    assert response.status_code == 422
    assert "记录" in response.json()["detail"]


def test_record_validation(client: TestClient, account: dict):
    headers = account["headers"]
    child_id = _create_child(client, headers, nickname="校验")
    response = client.post(
        "/api/v1/followup/records",
        json={"child_id": child_id, "mood": 9, "sleep_hours": 30, "completion": 180},
        headers=headers,
    )
    assert response.status_code == 422


def test_cross_user_access_denied(client: TestClient, account: dict):
    headers = account["headers"]
    child_id = _create_child(client, headers, nickname="隐私")
    other = client.post(
        "/api/v1/auth/register",
        json={"username": "other_parent_01", "password": "secret123"},
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    response = client.get(
        f"/api/v1/followup/records?child_id={child_id}", headers=other_headers
    )
    assert response.status_code == 404
