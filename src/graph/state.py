"""
State Definition for the Dubai AI Travel Planner LangGraph Multi-Agent System.
Defines PlannerState with strongly typed dictionary and accumulator channels.
Zero paid APIs ($0.00 cost).
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator


class PlannerState(TypedDict, total=False):
    """
    Central shared state passed between LangGraph nodes during execution.
    Supports concurrent fan-out, fan-in joins, bounded revision loops,
    and agent observability logs.
    """
    # Raw User Inputs
    raw_prompt: str
    overrides: Optional[Dict[str, Any]]

    # Extracted & Validated Constraints
    constraints: Optional[Dict[str, Any]]
    is_rejected: bool
    rejection_reason: Optional[str]

    # Destination Research Findings
    candidate_attractions: List[Dict[str, Any]]
    candidate_restaurants: List[Dict[str, Any]]
    concierge_notes: Optional[str]
    climate_profile: Optional[Dict[str, Any]]

    # Logistics & Scheduling
    daily_schedules: List[Dict[str, Any]]
    recommended_hotel_area: str
    hotel_tier: str
    logistics_briefing: Optional[str]

    # Budget & Financial Ledger
    budget_breakdown: Optional[Dict[str, Any]]
    financial_narrative: Optional[str]

    # Review & QA Auditing
    review_feedback: Optional[Dict[str, Any]]
    revision_count: int

    # Observability & Traceability Log Accumulator
    agent_logs: Annotated[List[Dict[str, Any]], operator.add]

    # Final Assembled Itinerary Output
    final_itinerary: Optional[Dict[str, Any]]
