"""LangGraph State Graph Construction.

Compiles the multi-agent research and decision-support workflow:
- Explicit node callables from app.workflow.nodes
- Strongly typed state (ResearchWorkflowState)
- Conditional routing directed by the Research Quality Supervisor ("The Third Eye")
- Bounded corrective retrieval loop back to retrieve_evidence
- Final synthesis and deterministic verification gate
"""

from typing import Literal
from langgraph.graph import END, StateGraph

from app.workflow.nodes import (
    acquire_sources_node,
    calculate_metrics_node,
    check_readiness_node,
    decompose_question_node,
    repair_retrieval_node,
    retrieve_evidence_node,
    run_analysts_node,
    run_judges_node,
    supervise_quality_node,
    synthesize_report_node,
    validate_scope_node,
)
from app.workflow.state import ResearchWorkflowState


def supervisor_routing_condition(
    state: ResearchWorkflowState,
) -> Literal["repair_retrieval", "synthesize_report"]:
    """Conditional edge evaluating Supervisor action."""
    decisions = state.get("supervisor_decisions", [])
    if not decisions:
        return "synthesize_report"

    latest = decisions[-1]
    action = latest.get("action")
    remaining_repairs = state.get("remaining_repair_budget", 0)

    if action == "REPAIR_RETRIEVAL" and remaining_repairs > 0:
        return "repair_retrieval"

    return "synthesize_report"


def build_research_graph():
    """Build and compile the multi-agent financial research LangGraph state graph."""
    workflow = StateGraph(ResearchWorkflowState)

    # 1. Add all workflow nodes
    workflow.add_node("validate_scope", validate_scope_node)
    workflow.add_node("acquire_sources", acquire_sources_node)
    workflow.add_node("check_readiness", check_readiness_node)
    workflow.add_node("decompose_question", decompose_question_node)
    workflow.add_node("retrieve_evidence", retrieve_evidence_node)
    workflow.add_node("calculate_metrics", calculate_metrics_node)
    workflow.add_node("run_analysts", run_analysts_node)
    workflow.add_node("run_judges", run_judges_node)
    workflow.add_node("supervise_quality", supervise_quality_node)
    workflow.add_node("repair_retrieval", repair_retrieval_node)
    workflow.add_node("synthesize_report", synthesize_report_node)

    # 2. Configure deterministic sequential edges
    workflow.set_entry_point("validate_scope")
    workflow.add_edge("validate_scope", "acquire_sources")
    workflow.add_edge("acquire_sources", "check_readiness")
    workflow.add_edge("check_readiness", "decompose_question")
    workflow.add_edge("decompose_question", "retrieve_evidence")
    workflow.add_edge("retrieve_evidence", "calculate_metrics")
    workflow.add_edge("calculate_metrics", "run_analysts")
    workflow.add_edge("run_analysts", "run_judges")
    workflow.add_edge("run_judges", "supervise_quality")

    # 3. Configure conditional edge from Supervisor
    workflow.add_conditional_edges(
        "supervise_quality",
        supervisor_routing_condition,
        {
            "repair_retrieval": "repair_retrieval",
            "synthesize_report": "synthesize_report",
        },
    )

    # 4. Corrective loop: from repair_retrieval, re-evaluate through analysts & judges
    workflow.add_edge("repair_retrieval", "run_analysts")

    # 5. Terminal edge
    workflow.add_edge("synthesize_report", END)

    return workflow.compile()


# Compiled singleton app instance
research_graph_app = build_research_graph()
