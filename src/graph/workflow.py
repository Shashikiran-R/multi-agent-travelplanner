"""
Workflow Assembly and Graph Compilation for the Dubai AI Travel Planner.
Assembles StateGraph with parallel execution stages, cyclic feedback loops,
and memory checkpointing.
Zero paid APIs ($0.00 cost).
"""

import uuid
from typing import Optional, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.graph.state import PlannerState
from src.graph.nodes import (
    orchestrator_parse_node,
    destination_node,
    logistics_node,
    join_node,
    budget_node,
    review_node,
    revision_node,
    finalize_node,
    fallback_finalize_node,
    finalize_rejection_node,
)
from src.graph.edges import route_after_parse, should_continue


def create_planner_graph(checkpointer: Optional[Any] = None):
    """
    Constructs and compiles the Dubai AI Travel Planner StateGraph.
    - Entry: parse_request
    - Conditional route: rejection circuit breaker vs destination research
    - Research -> Logistics -> Join -> Budget -> Review
    - Conditional loop: Review -> (Finalize | Revise | Fallback Finalize)
    - Loop back: Revise -> Budget -> Review
    """
    graph = StateGraph(PlannerState)

    # 1. Register all nodes
    graph.add_node("parse_request", orchestrator_parse_node)
    graph.add_node("destination_research", destination_node)
    graph.add_node("logistics_planning", logistics_node)
    graph.add_node("join_findings", join_node)
    graph.add_node("calculate_budget", budget_node)
    graph.add_node("review_itinerary", review_node)
    graph.add_node("apply_revisions", revision_node)
    graph.add_node("finalize_itinerary", finalize_node)
    graph.add_node("fallback_finalize", fallback_finalize_node)
    graph.add_node("finalize_rejection", finalize_rejection_node)

    # 2. Set entry point
    graph.set_entry_point("parse_request")

    # 3. Add conditional edge after parse_request (circuit breaker)
    graph.add_conditional_edges(
        "parse_request",
        route_after_parse,
        {
            "finalize_rejection": "finalize_rejection",
            "destination_research": "destination_research"
        }
    )

    # 4. Pipeline connections
    graph.add_edge("destination_research", "logistics_planning")
    graph.add_edge("logistics_planning", "join_findings")
    graph.add_edge("join_findings", "calculate_budget")
    graph.add_edge("calculate_budget", "review_itinerary")

    # 5. Cyclic feedback edge based on Review Agent audit
    graph.add_conditional_edges(
        "review_itinerary",
        should_continue,
        {
            "finalize": "finalize_itinerary",
            "revise": "apply_revisions",
            "fallback_finalize": "fallback_finalize"
        }
    )

    # 6. Revisions cycle back to budget calculation
    graph.add_edge("apply_revisions", "calculate_budget")

    # 7. Terminal exit edges
    graph.add_edge("finalize_itinerary", END)
    graph.add_edge("fallback_finalize", END)
    graph.add_edge("finalize_rejection", END)

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return graph.compile(checkpointer=cp)


def run_travel_planner(
    prompt: str,
    overrides: Optional[Dict[str, Any]] = None,
    thread_id: Optional[str] = None
) -> PlannerState:
    """
    High-level execution utility to execute the graph for a given user prompt.
    Returns the final state containing final_itinerary, budget_breakdown, agent_logs, etc.
    """
    tid = thread_id or f"dxb_session_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": tid}}

    app = create_planner_graph()
    initial_state: PlannerState = {
        "raw_prompt": prompt,
        "overrides": overrides or {},
        "revision_count": 0,
        "agent_logs": []
    }

    final_state = app.invoke(initial_state, config=config)
    return final_state
