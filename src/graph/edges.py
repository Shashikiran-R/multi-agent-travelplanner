"""
Conditional Routing Edges for the Dubai AI Travel Planner LangGraph System.
Defines circuit-breaker branching and bounded cyclic feedback logic.
Zero paid APIs ($0.00 cost).
"""

from typing import Dict, Any
from src.graph.state import PlannerState


def route_after_parse(state: PlannerState) -> str:
    """
    Early exit circuit breaker:
    If the requested trip duration and budget are mathematically impossible based on
    real Dubai municipal baselines, immediately abort execution to prevent wasted processing.
    """
    if state.get("is_rejected", False):
        return "finalize_rejection"
    return "destination_research"


def should_continue(state: PlannerState) -> str:
    """
    Decides whether to finalize, revise, or fallback after review audit:
    - If audit passed (0 violations): branch to 'finalize'
    - If failed but revision_count >= 3: branch to 'fallback_finalize' (bounded loop safeguard)
    - Otherwise: branch to 'revise' (cyclic substitution loop)
    """
    review = state.get("review_feedback") or {}
    count = state.get("revision_count", 0)

    if review.get("passed", False):
        return "finalize"

    if count >= 3:
        return "fallback_finalize"

    return "revise"
