"""2D 情景游戏接口测试：世界配置、存档、LangGraph 回合、安全兜底。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.game_worlds import validate_worlds, world_catalog, world_payload
from app.services.training_scripts import SCENARIOS


def test_world_config_matches_training_scripts():
    """六个场景、步骤数、Prompt 全部与既有训练脚本对齐。"""
    assert validate_worlds() == []
    catalog = world_catalog()
    assert [item["scenario"] for item in catalog] == list(SCENARIOS)
    for item in catalog:
        world = world_payload(item["scenario"])
        script = SCENARIOS[item["scenario"]]
        assert len(world["steps"]) == len(script.steps)
        assert len(item["scenes"]) >= 1
        for step in world["steps"]:
            scene = world["scenes"][step["scene"]]
            assert step["speaker"] in {npc["id"] for npc in scene["npcs"]}
            focus_ids = {npc["id"] for npc in scene["npcs"]} | {p["id"] for p in scene["props"]}
            assert step["focus"] in focus_ids
            assert step["task"]


def test_world_scene_switching_and_stands():
    """跨房间的关卡必须声明正确的房间顺序，所有角色都要有可站立的锚点。"""
    discomfort = world_payload("discomfort")
    assert [step["scene"] for step in discomfort["steps"]] == [
        "home_living",
        "classroom",
        "home_living",
    ]
    invite = world_payload("invite")
    assert [step["scene"] for step in invite["steps"]] == [
        "classroom",
        "playground",
        "playground",
    ]
    for key in SCENARIOS:
        world = world_payload(key)
        for step in world["steps"]:
            scene = world["scenes"][step["scene"]]
            for npc in scene["npcs"]:
                stand = npc["stand"]
                assert 0 < stand["x"] < world["grid"]["w"]
                assert 0 < stand["y"] < world["grid"]["h"]
            assert scene["bounds"]["minX"] < scene["bounds"]["maxX"]


def test_game_catalog_requires_auth(client: TestClient):
    assert client.get("/api/v1/game/scenarios").status_code == 401


def test_game_catalog(client: TestClient, account: dict):
    response = client.get("/api/v1/game/scenarios", headers=account["headers"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 6
    assert {item["scenario"] for item in data} == set(SCENARIOS)
    thanks = next(item for item in data if item["scenario"] == "thanks")
    assert thanks["art"] == "home"
    assert thanks["casts"]


def test_game_session_and_save(client: TestClient, account: dict, child: dict):
    headers = account["headers"]
    start = client.post(
        "/api/v1/training/start",
        json={"scenario": "shopping", "child_id": child["id"]},
        headers=headers,
    ).json()
    response = client.get(f"/api/v1/game/{start['id']}", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["world"]["scenario"] == "shopping"
    assert payload["world"]["scenes"]["store"]["props"]
    assert payload["state"]["scene"] == "store"
    assert payload["training"]["prompt"]

    saved = client.put(
        f"/api/v1/game/{start['id']}/state",
        json={
            "scene": "store",
            "player": {"x": 9.4, "y": 8.1},
            "visited": ["fridge", "counter", "fridge"],
            "actions": [{"kind": "inspect", "target": "fridge", "step": 0, "at": "1"}],
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    state = saved.json()
    assert state["player"] == {"x": 9.4, "y": 8.1}
    assert state["visited"] == ["fridge", "counter"]
    assert state["actions"][0]["kind"] == "inspect"

    # 坐标越界要被夹回房间内
    clamped = client.put(
        f"/api/v1/game/{start['id']}/state",
        json={"player": {"x": 999, "y": -5}},
        headers=headers,
    ).json()
    assert 0 <= clamped["player"]["x"] <= 16
    assert 0 <= clamped["player"]["y"] <= 11

    again = client.get(f"/api/v1/game/{start['id']}", headers=headers).json()
    assert again["state"]["player"] == clamped["player"]


def test_game_turn_reuses_training_flow(client: TestClient, account: dict):
    headers = account["headers"]
    start = client.post(
        "/api/v1/training/start", json={"scenario": "thanks"}, headers=headers
    ).json()

    good = client.post(
        f"/api/v1/game/{start['id']}/turn", json={"answer": "谢谢"}, headers=headers
    ).json()
    assert good["accepted"] is True
    assert good["via"] == "speech"
    assert good["training"]["step_index"] == 1
    assert good["reply"]

    # 答偏：不推进，给分层提示，由后端返回（不是前端自己编的）
    bad = client.post(
        f"/api/v1/game/{start['id']}/turn", json={"answer": "嗯……"}, headers=headers
    ).json()
    assert bad["accepted"] is False
    assert bad["training"]["step_index"] == 1
    assert bad["training"]["hint_level"] == 1
    assert "很接近了" in bad["reply"]

    # 非语言表达同样通过
    gesture = client.post(
        f"/api/v1/game/{start['id']}/turn",
        json={"answer": "点点头", "source": "gesture"},
        headers=headers,
    ).json()
    assert gesture["accepted"] is True
    assert gesture["via"] == "aac"


def test_game_turn_blocks_unsafe_message(client: TestClient, account: dict):
    headers = account["headers"]
    start = client.post(
        "/api/v1/training/start", json={"scenario": "refuse"}, headers=headers
    ).json()
    blocked = client.post(
        f"/api/v1/game/{start['id']}/turn", json={"answer": "我想死"}, headers=headers
    ).json()
    assert blocked["blocked"] is True
    assert blocked["notice"]
    assert blocked["training"]["step_index"] == 0

    view = client.get(f"/api/v1/game/{start['id']}", headers=headers).json()
    assert view["training"]["step_index"] == 0


def test_game_session_is_private(client: TestClient, account: dict):
    start = client.post(
        "/api/v1/training/start", json={"scenario": "help"}, headers=account["headers"]
    ).json()
    other = client.post(
        "/api/v1/auth/register", json={"username": "game_intruder", "password": "secret123"}
    ).json()
    response = client.get(
        f"/api/v1/game/{start['id']}",
        headers={"Authorization": f"Bearer {other['access_token']}"},
    )
    assert response.status_code == 404
