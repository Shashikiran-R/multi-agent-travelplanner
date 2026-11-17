"""
LangGraph Node Implementations for the Dubai AI Travel Planner Multi-Agent System.
Wraps Orchestrator, Destination, Logistics, Budget, and Review agents into stateful graph nodes.
Zero paid APIs ($0.00 cost).
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from src.graph.state import PlannerState
from src.models.request import UserConstraints
from src.models.itinerary import DayPlan, TripItinerary
from src.models.budget import BudgetBreakdown
from src.models.review import ReviewFeedback
from src.agents.orchestrator import OrchestratorAgent
from src.agents.destination import DestinationAgent
from src.agents.logistics import LogisticsAgent
from src.agents.budget import BudgetAgent
from src.agents.review import ReviewAgent
from src.data_access.sqlite_client import DubaiSQLiteClient


def _log_entry(agent: str, node: str, status: str, message: str) -> Dict[str, Any]:
    """Helper to produce structured agent activity log records."""
    return {
        "timestamp": datetime.now().isoformat(),
        "agent": agent,
        "node": node,
        "status": status,
        "message": message
    }


def orchestrator_parse_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 1: Parses natural language prompt into UserConstraints using Groq
    (with deterministic regex fallback) and evaluates minimum financial baseline.
    """
    raw_prompt = state.get("raw_prompt", "")
    overrides = state.get("overrides")
    agent = OrchestratorAgent()

    constraints, is_rejected, rejection_reason = agent.parse_prompt(
        raw_prompt=raw_prompt,
        overrides=overrides
    )

    if is_rejected:
        return {
            "constraints": constraints.model_dump() if constraints else None,
            "is_rejected": True,
            "rejection_reason": rejection_reason,
            "agent_logs": [_log_entry(
                agent="OrchestratorAgent",
                node="parse_request",
                status="rejected",
                message=f"Financial baseline rejection: {rejection_reason}"
            )]
        }

    # Fetch climate profile if month is present
    climate_profile = None
    if constraints.travel_month:
        climate_profile = DubaiSQLiteClient().get_climate_profile(constraints.travel_month)

    return {
        "constraints": constraints.model_dump(),
        "hotel_tier": constraints.accommodation_tier,
        "is_rejected": False,
        "rejection_reason": None,
        "climate_profile": climate_profile,
        "revision_count": 0,
        "agent_logs": [_log_entry(
            agent="OrchestratorAgent",
            node="parse_request",
            status="success",
            message=(
                f"Extracted constraints: {constraints.trip_duration_days} days, "
                f"AED {constraints.total_budget_aed:.2f} budget, {constraints.accommodation_tier} tier, "
                f"interests: {', '.join(constraints.interests)}"
            )
        )]
    }


def destination_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 2: Curates candidate attractions and authentic dining venues from
    verified Dubai catalog, applying summer climate adaptations and Groq concierge advice.
    """
    constraints_dict = state.get("constraints")
    if not constraints_dict:
        return {
            "candidate_attractions": [],
            "candidate_restaurants": [],
            "agent_logs": [_log_entry("DestinationAgent", "destination_research", "error", "Missing constraints")]
        }

    constraints = UserConstraints(**constraints_dict)
    agent = DestinationAgent()
    findings = agent.research_destinations(constraints)

    msg = (
        f"Retrieved {len(findings['candidate_attractions'])} attractions and "
        f"{len(findings['candidate_restaurants'])} dining options across Dubai."
    )
    if findings.get("is_summer_adapted"):
        msg += " Summer indoor climate filter active."

    return {
        "candidate_attractions": findings["candidate_attractions"],
        "candidate_restaurants": findings["candidate_restaurants"],
        "concierge_notes": findings.get("concierge_notes"),
        "agent_logs": [_log_entry(
            agent="DestinationAgent",
            node="destination_research",
            status="success",
            message=msg
        )]
    }


def logistics_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 3: Partitions venues into single-district days across Dubai's 5 official districts,
    selects optimal base hotel area, and calculates deterministic RTA transit steps.
    """
    constraints_dict = state.get("constraints")
    if not constraints_dict:
        return {
            "daily_schedules": [],
            "agent_logs": [_log_entry("LogisticsAgent", "logistics_planning", "error", "Missing constraints")]
        }

    constraints = UserConstraints(**constraints_dict)
    candidate_att = state.get("candidate_attractions", [])
    candidate_rest = state.get("candidate_restaurants", [])

    agent = LogisticsAgent()
    days, hotel_area = agent.plan_itinerary_logistics(
        constraints=constraints,
        candidate_attractions=candidate_att,
        candidate_restaurants=candidate_rest
    )

    briefing = agent.generate_logistics_briefing(days, hotel_area, constraints)

    return {
        "daily_schedules": [d.model_dump() for d in days],
        "recommended_hotel_area": hotel_area,
        "logistics_briefing": briefing,
        "agent_logs": [_log_entry(
            agent="LogisticsAgent",
            node="logistics_planning",
            status="success",
            message=(
                f"Built {len(days)} single-district daily itineraries based at {hotel_area}. "
                f"RTA transit connections calculated."
            )
        )]
    }


def join_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 4: Synchronization join node validating completion of research and logistics planning.
    """
    days = state.get("daily_schedules", [])
    hotel_area = state.get("recommended_hotel_area", "Downtown")
    return {
        "agent_logs": [_log_entry(
            agent="JoinCoordinator",
            node="join_findings",
            status="success",
            message=f"Synchronized {len(days)} daily schedules based in {hotel_area} for financial analysis."
        )]
    }


def budget_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 5: Computes exact category-wise financial ledger in AED, determines cost delta,
    and formulates executive financial assessment narrative via Groq.
    """
    constraints_dict = state.get("constraints")
    if not constraints_dict:
        return {"agent_logs": [_log_entry("BudgetAgent", "calculate_budget", "error", "Missing constraints")]}

    constraints = UserConstraints(**constraints_dict)
    days = [DayPlan(**d) for d in state.get("daily_schedules", [])]
    hotel_district = state.get("recommended_hotel_area", "Old Dubai & Creek")

    agent = BudgetAgent()
    breakdown, cost_delta, swaps = agent.calculate_budget(
        days=days,
        constraints=constraints,
        hotel_district=hotel_district
    )

    status_str = "within_budget" if breakdown.is_within_budget else "over_budget"
    message = (
        f"Calculated budget: Total AED {breakdown.grand_total_aed:.2f} "
        f"(Target: AED {constraints.total_budget_aed:.2f}, Balance: AED {breakdown.remaining_balance_aed:.2f}). "
        f"{len(swaps)} swaps available if required."
    )

    return {
        "budget_breakdown": breakdown.model_dump(),
        "financial_narrative": agent.last_financial_narrative,
        "agent_logs": [_log_entry(
            agent="BudgetAgent",
            node="calculate_budget",
            status=status_str,
            message=message
        )]
    }


def review_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 6: Audits proposed itinerary across 6 hard constraints using deterministic rules
    and synthesizes expert QA commentary with Ollama (nemotron-3-ultra).
    """
    constraints_dict = state.get("constraints")
    budget_dict = state.get("budget_breakdown")
    if not constraints_dict or not budget_dict:
        return {"agent_logs": [_log_entry("ReviewAgent", "review_itinerary", "error", "Missing state data for review")]}

    constraints = UserConstraints(**constraints_dict)
    budget = BudgetBreakdown(**budget_dict)
    days = [DayPlan(**d) for d in state.get("daily_schedules", [])]
    revision_round = state.get("revision_count", 0)

    agent = ReviewAgent()
    feedback = agent.audit_itinerary_plan(
        days=days,
        budget=budget,
        constraints=constraints,
        revision_round=revision_round
    )

    return {
        "review_feedback": feedback.model_dump(),
        "agent_logs": [_log_entry(
            agent="ReviewAgent",
            node="review_itinerary",
            status="passed" if feedback.passed else "needs_revision",
            message=(
                f"Audit Round {revision_round}: {'PASSED' if feedback.passed else 'VIOLATIONS DETECTED'} "
                f"({len(feedback.structured_violations)} issues, Delta: AED {feedback.cost_delta_aed:.2f})"
            )
        )]
    }


def revision_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 7: Executes prioritized substitutions (transit Nol downgrade, free boardwalk swaps,
    dining price tier adjustment) to resolve audit violations.
    """
    constraints_dict = state.get("constraints")
    constraints = UserConstraints(**constraints_dict)
    days = [DayPlan(**d) for d in state.get("daily_schedules", [])]
    hotel_district = state.get("recommended_hotel_area", "Old Dubai & Creek")
    current_rev = state.get("revision_count", 0)

    budget_agent = BudgetAgent()
    breakdown, cost_delta, swaps = budget_agent.calculate_budget(
        days=days,
        constraints=constraints,
        hotel_district=hotel_district
    )

    applied_desc = "No applicable swaps found; pruned excessive schedule density."
    modified_days = days

    if swaps:
        best_swap = swaps[0]
        modified_days, applied = budget_agent.apply_best_swap(days, best_swap)
        if applied:
            applied_desc = best_swap.get("description", "Applied cost-cutting swap")
    else:
        # If no budget swaps found, check if there are pacing violations (> 4 activities) and prune
        for d in modified_days:
            if len(d.activities) > 4:
                d.activities = d.activities[:4]
                applied_desc = f"Pruned Day {d.day_number} activities to 4 to satisfy pacing rules."

    return {
        "daily_schedules": [d.model_dump() for d in modified_days],
        "revision_count": current_rev + 1,
        "agent_logs": [_log_entry(
            agent="BudgetAgent",
            node="apply_revisions",
            status="revised",
            message=f"Applied Revision {current_rev + 1}: {applied_desc}"
        )]
    }


def finalize_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 8: Synthesizes the fully verified, constraint-compliant itinerary
    into the immutable TripItinerary model.
    """
    constraints = UserConstraints(**state["constraints"])
    days = [DayPlan(**d) for d in state.get("daily_schedules", [])]
    budget = BudgetBreakdown(**state["budget_breakdown"])
    review = ReviewFeedback(**state["review_feedback"])

    orchestrator = OrchestratorAgent()
    itinerary = orchestrator.assemble_final_itinerary(
        constraints=constraints,
        days=days,
        budget=budget,
        review=review
    )

    return {
        "final_itinerary": itinerary.model_dump(),
        "agent_logs": [_log_entry(
            agent="OrchestratorAgent",
            node="finalize_itinerary",
            status="completed",
            message=(
                f"Trip {itinerary.trip_id} successfully compiled. Total: AED {itinerary.budget.grand_total_aed:.2f} "
                f"across {len(itinerary.days)} days."
            )
        )]
    }


def fallback_finalize_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 9: Bounded revision termination fallback.
    Finalizes best-effort itinerary after 3 revision attempts with explicit advisory notes.
    """
    constraints = UserConstraints(**state["constraints"])
    days = [DayPlan(**d) for d in state.get("daily_schedules", [])]
    budget = BudgetBreakdown(**state["budget_breakdown"])
    review = ReviewFeedback(**state["review_feedback"])

    fallback_note = (
        f"Notice: Optimization reached the maximum 3 revision rounds. Finalized best-effort "
        f"itinerary with total spend of AED {budget.grand_total_aed:.2f} (Budget: AED {constraints.total_budget_aed:.2f}). "
        f"Remaining advisory items: {'; '.join(review.violations) if review.violations else 'None'}."
    )
    review.audit_notes = (review.audit_notes + "\n" + fallback_note) if review.audit_notes else fallback_note

    orchestrator = OrchestratorAgent()
    itinerary = orchestrator.assemble_final_itinerary(
        constraints=constraints,
        days=days,
        budget=budget,
        review=review,
        summary=fallback_note
    )

    return {
        "final_itinerary": itinerary.model_dump(),
        "agent_logs": [_log_entry(
            agent="OrchestratorAgent",
            node="fallback_finalize",
            status="completed_with_fallback",
            message=fallback_note
        )]
    }


def finalize_rejection_node(state: PlannerState) -> Dict[str, Any]:
    """
    Node 10: Circuit breaker termination node for impossible budget requests.
    """
    reason = state.get("rejection_reason", "Budget is mathematically insufficient for Dubai travel.")
    return {
        "final_itinerary": None,
        "agent_logs": [_log_entry(
            agent="OrchestratorAgent",
            node="finalize_rejection",
            status="aborted",
            message=f"Planner halted: {reason}"
        )]
    }
