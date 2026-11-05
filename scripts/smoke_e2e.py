"""端到端冒烟脚本：对已启动的服务跑一遍核心链路。

用法：python -m scripts.smoke_e2e [http://127.0.0.1:8123/api/v1]
前置：已执行 python -m scripts.seed_demo
"""

from __future__ import annotations

import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123/api/v1"


def title(text: str) -> None:
    print("\n" + "=" * 72)
    print(text)
    print("=" * 72)


def main() -> None:
    with httpx.Client(timeout=90, trust_env=False) as client:
        login = client.post(f"{BASE}/auth/login", json={"username": "demo", "password": "demo123456"})
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("登录成功:", login.json()["user"]["display_name"])

        health = client.get(BASE.replace("/api/v1", "") + "/health").json()
        print("健康检查:", health["status"], health["components"])

        children = client.get(f"{BASE}/children", headers=headers).json()
        if not children:
            raise SystemExit("没有孩子档案，请先运行 scripts.seed_demo")
        child_id = children[0]["id"]
        print("孩子档案:", children[0]["nickname"], children[0]["id"])

        title("1. 居家康复答疑（RAG + 引用）")
        qa = client.post(
            f"{BASE}/chat",
            json={"message": "孩子晚上不肯睡觉，睡前特别兴奋，在家可以怎么做？", "child_id": child_id},
            headers=headers,
        ).json()
        print("intent:", qa["intent"], "| mode:", qa["mode"], "| safety:", qa["safety"]["level"])
        print("引用:", [f"[{c['index']}] {c['title']}" for c in qa["citations"]])
        print(qa["reply"][:600])

        title("2. 医疗安全拦截")
        blocked = client.post(
            f"{BASE}/chat",
            json={"message": "我孩子是不是自闭症？要不要吃利他林？", "child_id": child_id},
            headers=headers,
        ).json()
        print("safety:", blocked["safety"]["level"], blocked["safety"]["categories"])
        print(blocked["reply"][:200])

        title("3. 情景训练（聊天式）")
        started = client.post(
            f"{BASE}/chat",
            json={"message": "开始训练：道谢", "child_id": child_id},
            headers=headers,
        ).json()
        session_id = started["session_id"]
        print("训练状态:", started["training"]["status"], started["training"]["scenario_name"])
        print(started["reply"][:400])

        turn = client.post(
            f"{BASE}/chat",
            json={"message": "谢谢", "session_id": session_id, "child_id": child_id},
            headers=headers,
        ).json()
        print("\n孩子: 谢谢")
        print("教练:", turn["reply"][:300])

        ended = client.post(
            f"{BASE}/chat",
            json={"message": "结束训练", "session_id": session_id, "child_id": child_id},
            headers=headers,
        ).json()
        print("\n训练小结:\n", ended["reply"][:600])

        title("4. 随访记录与阶段小结")
        from datetime import date, timedelta

        today = date.today()
        for offset, (mood, sleep, completion) in enumerate([(3, 8.0, 55), (4, 9.0, 70)]):
            response = client.post(
                f"{BASE}/followup/records",
                json={
                    "child_id": child_id,
                    "record_date": (today - timedelta(days=offset)).isoformat(),
                    "mood": mood,
                    "sleep_hours": sleep,
                    "completion": completion,
                    "behavior": "晚饭后情绪平稳，主动递了饼干图片",
                    "training_items": ["图片时间表", "道谢练习"],
                    "interaction": "和妈妈一起读了绘本",
                },
                headers=headers,
            )
            response.raise_for_status()
        summary = client.post(
            f"{BASE}/followup/summary", json={"child_id": child_id, "days": 7}, headers=headers
        ).json()
        print("指标:", summary["metrics"])
        print(summary["content"][:600])

        title("5. 知识库检索")
        hits = client.post(
            f"{BASE}/knowledge/search", json={"query": "孩子捂耳朵怕吵", "top_k": 3}, headers=headers
        ).json()
        for hit in hits["hits"]:
            print(f"[{hit['index']}] {hit['title']}·{hit['section']} score={hit['score']}")

        print("\n全部链路通过。")


if __name__ == "__main__":
    main()
