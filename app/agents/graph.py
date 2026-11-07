"""主工作流装配。

主图负责「安全审核 + 意图路由」，答疑分支下沉为一个可独立编译的子图：

        START
          │
       analyze ──(安全拦截)──> safety_response
          │
          ├─ qa ──> 自反思子图（见下）
          ├─ training_start / training_turn / training_end
          ├─ followup_record / followup_summary
          └─ chat
          │
         END

答疑子图（Plan → Retrieve → Grade → Draft → Critique → Revise）：

        START
          │
      plan_queries           把问题拆成 2-3 条检索式（有模型用模型，没模型用规则）
          │
   retrieve_evidence         多条检索式并行召回，按 chunk 去重取最高分
          │
    grade_evidence           查全率 + 最高分，判断证据够不够
          │
   ┌──────┴───────┐
   │ 证据不足      │ 证据充足
   ▼              ▼
rewrite_query   draft_answer   生成草稿（模型失败则检索兜底）
   │              │
   └──> retrieve  self_critique  四条确定性审查：长度/引用/相关性/证据
                  │
          ┌───────┴────────┐
          │ 不达标 & 未改过 │ 通过
          ▼                ▼
     revise_answer ──> finalize_answer
                       （免责声明 + 警示 + 引用 + 轨迹入 meta）

两条回边都有次数上限（检索 2 轮、修订 1 轮），保证图一定收敛，不会无限循环。
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.state import AgentState


def build_qa_subgraph() -> Any:
    """自反思答疑子图：可独立编译、独立测试。"""
    graph = StateGraph(AgentState)

    graph.add_node("plan_queries", nodes.plan_queries)
    graph.add_node("retrieve_evidence", nodes.retrieve_evidence)
    graph.add_node("grade_evidence", nodes.grade_evidence)
    graph.add_node("rewrite_query", nodes.rewrite_query)
    graph.add_node("draft_answer", nodes.draft_answer)
    graph.add_node("self_critique", nodes.self_critique)
    graph.add_node("revise_answer", nodes.revise_answer)
    graph.add_node("finalize_answer", nodes.finalize_answer)

    graph.add_edge(START, "plan_queries")
    graph.add_edge("plan_queries", "retrieve_evidence")
    graph.add_edge("retrieve_evidence", "grade_evidence")
    graph.add_conditional_edges(
        "grade_evidence",
        nodes.route_after_grade,
        {
            "rewrite_query": "rewrite_query",
            "draft_answer": "draft_answer",
        },
    )
    graph.add_edge("rewrite_query", "retrieve_evidence")
    graph.add_edge("draft_answer", "self_critique")
    graph.add_conditional_edges(
        "self_critique",
        nodes.route_after_critique,
        {
            "revise_answer": "revise_answer",
            "finalize_answer": "finalize_answer",
        },
    )
    graph.add_edge("revise_answer", "self_critique")  # 改完再审一次，最多一轮
    graph.add_edge("finalize_answer", END)

    return graph.compile()


def build_graph() -> Any:
    graph = StateGraph(AgentState)

    graph.add_node("analyze", nodes.analyze)
    graph.add_node("safety_response", nodes.safety_response)
    graph.add_node("qa", build_qa_subgraph())
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
