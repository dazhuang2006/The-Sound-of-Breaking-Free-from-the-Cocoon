"""对话接口端到端测试：答疑 + 引用、安全拦截、聊天式训练。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_chat_requires_auth(client: TestClient):
    response = client.post("/api/v1/chat", json={"message": "你好"})
    assert response.status_code == 401


def test_qa_returns_citations_and_disclaimer(client: TestClient, account: dict, child: dict):
    response = client.post(
        "/api/v1/chat",
        json={"message": "孩子晚上不肯睡觉，睡前总是很兴奋，有什么居家办法？", "child_id": child["id"]},
        headers=account["headers"],
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["intent"] == "qa"
    assert data["mode"] == "qa"
    assert data["citations"], "应带知识库引用"
    assert data["meta"]["retrieved"] >= 1
    assert "仅供居家辅助参考" in data["reply"]
    assert data["session_id"]

    detail = client.get(
        f"/api/v1/chat/sessions/{data['session_id']}", headers=account["headers"]
    ).json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][1]["citations"]


def test_emergency_input_is_blocked(client: TestClient, account: dict, child: dict):
    response = client.post(
        "/api/v1/chat",
        json={"message": "孩子刚才抽搐了，现在叫不醒", "child_id": child["id"]},
        headers=account["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "safety"
    assert data["safety"]["level"] == "emergency"
    assert "120" in data["reply"]
    assert data["training"] is None


def test_diagnosis_request_is_redirected(client: TestClient, account: dict):
    response = client.post(
        "/api/v1/chat",
        json={"message": "我孩子是不是自闭症？"},
        headers=account["headers"],
    )
    data = response.json()
    assert data["safety"]["level"] == "redirect"
    assert "诊断" in data["reply"]


def test_training_via_chat_mode_switch(client: TestClient, account: dict, child: dict):
    headers = account["headers"]
    start = client.post(
        "/api/v1/chat",
        json={"message": "开始训练：道谢", "child_id": child["id"]},
        headers=headers,
    ).json()
    assert start["intent"] == "training_start"
    assert start["mode"] == "training"
    assert start["training"]["status"] == "active"
    session_id = start["session_id"]

    turn = client.post(
        "/api/v1/chat",
        json={"message": "谢谢", "session_id": session_id, "child_id": child["id"]},
        headers=headers,
    ).json()
    assert turn["training"]["step_index"] >= 1

    end = client.post(
        "/api/v1/chat",
        json={"message": "结束训练", "session_id": session_id, "child_id": child["id"]},
        headers=headers,
    ).json()
    assert end["intent"] == "training_end"
    assert end["training"]["status"] == "completed"
    assert "训练小结" in end["reply"]


def test_session_list_and_delete(client: TestClient, account: dict):
    headers = account["headers"]
    created = client.post(
        "/api/v1/chat", json={"message": "孩子不爱和小朋友玩怎么办"}, headers=headers
    ).json()
    sessions = client.get("/api/v1/chat/sessions", headers=headers).json()
    assert any(item["id"] == created["session_id"] for item in sessions)

    deleted = client.delete(f"/api/v1/chat/sessions/{created['session_id']}", headers=headers)
    assert deleted.status_code == 200
    after = client.get("/api/v1/chat/sessions", headers=headers).json()
    assert all(item["id"] != created["session_id"] for item in after)


def test_unknown_session_returns_404(client: TestClient, account: dict):
    response = client.post(
        "/api/v1/chat",
        json={"message": "你好", "session_id": "00000000-0000-0000-0000-000000000000"},
        headers=account["headers"],
    )
    assert response.status_code == 404
