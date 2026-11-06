"""情景训练接口测试：推进、分层提示、结束与小结。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_scenario_catalog(client: TestClient, account: dict):
    response = client.get("/api/v1/training/scenarios", headers=account["headers"])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6
    assert {item["key"] for item in data} == {
        "thanks",
        "help",
        "discomfort",
        "refuse",
        "invite",
        "shopping",
    }


def test_training_flow(client: TestClient, account: dict, child: dict):
    headers = account["headers"]
    start = client.post(
        "/api/v1/training/start",
        json={"scenario": "thanks", "child_id": child["id"]},
        headers=headers,
    )
    assert start.status_code == 201, start.text
    view = start.json()
    training_id = view["id"]
    assert view["status"] == "active"
    assert view["total_steps"] == 3
    assert view["prompt"]

    # 第一次答对：推进到第 2 步
    first = client.post(
        f"/api/v1/training/{training_id}/answer", json={"answer": "谢谢！"}, headers=headers
    ).json()
    assert first["step_index"] == 1
    assert first["correct_count"] == 1
    assert first["hint_level"] == 0

    # 连续答偏：逐级提示，不直接给答案
    second = client.post(
        f"/api/v1/training/{training_id}/answer", json={"answer": "我不知道"}, headers=headers
    ).json()
    assert second["hint_level"] == 1
    assert second["step_index"] == 1
    assert second["status"] == "active"

    third = client.post(
        f"/api/v1/training/{training_id}/answer", json={"answer": "嗯……"}, headers=headers
    ).json()
    assert third["hint_level"] == 2

    # 提示用尽：示范后推进
    fourth = client.post(
        f"/api/v1/training/{training_id}/answer", json={"answer": "还是不会"}, headers=headers
    ).json()
    assert fourth["step_index"] == 2
    assert fourth["hint_level"] == 0

    # 用手势表达也算完成（替代沟通）
    aac = client.post(
        f"/api/v1/training/{training_id}/answer", json={"answer": "点点头"}, headers=headers
    ).json()
    assert aac["correct_count"] >= 2
    assert "手势" in aac["feedback"] or "图片" in aac["feedback"] or aac["step_index"] >= 2

    end = client.post(f"/api/v1/training/{training_id}/end", headers=headers).json()
    assert end["status"] == "completed"
    assert "训练小结" in end["summary"]
    assert "仅供居家辅助参考" in end["summary"]

    # 重复结束是幂等的
    again = client.post(f"/api/v1/training/{training_id}/end", headers=headers).json()
    assert again["status"] == "completed"
    assert again["summary"] == end["summary"]


def test_training_rejects_unknown_scenario(client: TestClient, account: dict):
    response = client.post(
        "/api/v1/training/start",
        json={"scenario": "travel"},
        headers=account["headers"],
    )
    assert response.status_code == 422


def test_abort_training_closes_session(client: TestClient, account: dict):
    """刚进场景就退出：标记 aborted，不再出现在「继续上次」里。"""
    start = client.post(
        "/api/v1/training/start", json={"scenario": "thanks"}, headers=account["headers"]
    ).json()
    aborted = client.post(
        f"/api/v1/training/{start['id']}/abort", headers=account["headers"]
    ).json()
    assert aborted["status"] == "aborted"
    sessions = client.get("/api/v1/training/sessions", headers=account["headers"]).json()
    active = [item for item in sessions if item["status"] == "active"]
    assert all(item["id"] != start["id"] for item in active)
    # 放弃后可以立刻重新开始，不会因为旧会话没关而被挡住
    again = client.post(
        "/api/v1/training/start", json={"scenario": "help"}, headers=account["headers"]
    )
    assert again.status_code == 201


def test_training_is_private(client: TestClient, account: dict, child: dict):
    start = client.post(
        "/api/v1/training/start",
        json={"scenario": "help", "child_id": child["id"]},
        headers=account["headers"],
    ).json()
    other = client.post(
        "/api/v1/auth/register",
        json={"username": "intruder_01", "password": "secret123"},
    ).json()
    response = client.get(
        f"/api/v1/training/{start['id']}",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert response.status_code == 404
