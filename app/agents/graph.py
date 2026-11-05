"""主工作流装配。

一个主图 + 三个业务分支 + 一条贯穿全流程的安全审核链路：

        START
          │
       analyze ──(安全拦截)──> safety_response
          │
          ├─ qa ──────────────> 检索 → 生成 → 输出审核
          ├─ training_start ──> 训练开场
          ├─ training_turn ───> 单轮互动（评价/分层提示/推进）
          ├─ training_end ────> 训练小结
          ├─ followup_record ─> 记录落库
          ├─ followup_summary > 阶段小结
          └─ chat ────────────> 简短引导
          │
         END

业务子流程没有拆成独立 Agent：状态机清晰、可测试，比"为多智能体而多智能体"更可靠。
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.state import AgentState


def build_graph() -> Any:
    graph = StateGraph(AgentState)

    graph.add_node("analyze", nodes.analyze)
    graph.add_node("safety_response", nodes.safety_response)
    graph.add_node("qa", nodes.qa_answer)
    graph.add_node("training_start", nodes.training_start)
    graph.add_node("training_turn", nodes.training_turn)
    graph.add_node("training_end", nodes.training_end)
    graph.add_node("followup_record", nodes.followup_record)
    graph.add_node("followup_summary", nodes.followup_summary)
    graph.add_node("chat", nodes.smalltalk)

    graph.add_edge(START, "analyze")
    graph.add_conditional_edges(
        "analyze",
        nodes.route_after_analyze,
        {
            "safety_response": "safety_response",
            "qa": "qa",
            "training_start": "training_start",
            "training_turn": "training_turn",
            "training_end": "training_end",
            "followup_record": "followup_record",
            "followup_summary": "followup_summary",
            "chat": "chat",
        },
    )
    for terminal in (
        "safety_response",
        "qa",
        "training_start",
        "training_turn",
        "training_end",
        "followup_record",
        "followup_summary",
        "chat",
    ):
        graph.add_edge(terminal, END)

    return graph.compile()
