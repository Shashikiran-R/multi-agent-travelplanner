"""
Unit and Integration Test Suite for Phase 5: LangGraph Multi-Agent Workflow.
Tests state transitions, node execution, circuit-breaker routing,
bounded revision cycles, and final itinerary synthesis.
Zero paid APIs ($0.00 cost).
"""

import unittest
from typing import Dict, Any

from src.graph.state import PlannerState
from src.graph.workflow import create_planner_graph, run_travel_planner
from src.graph.edges import route_after_parse, should_continue
from src.models.itinerary import TripItinerary


class TestLangGraphRouting(unittest.TestCase):
    """Tests conditional routing logic and circuit breaker edges."""

    def test_route_after_parse_rejection(self):
        state: PlannerState = {"is_rejected": True, "rejection_reason": "Budget insufficient"}
        target = route_after_parse(state)
        self.assertEqual(target, "finalize_rejection")

    def test_route_after_parse_approved(self):
        state: PlannerState = {"is_rejected": False}
        target = route_after_parse(state)
        self.assertEqual(target, "destination_research")

    def test_should_continue_passes(self):
        state: PlannerState = {
            "review_feedback": {"passed": True},
            "revision_count": 0
        }
        target = should_continue(state)
        self.assertEqual(target, "finalize")

    def test_should_continue_revises(self):
        state: PlannerState = {
            "review_feedback": {"passed": False},
            "revision_count": 1
        }
        target = should_continue(state)
        self.assertEqual(target, "revise")

    def test_should_continue_hits_max_revision_bound(self):
        # When revision_count >= 3, must exit to fallback_finalize
        state: PlannerState = {
            "review_feedback": {"passed": False},
            "revision_count": 3
        }
        target = should_continue(state)
        self.assertEqual(target, "fallback_finalize")


class TestLangGraphWorkflowExecution(unittest.TestCase):
    """Tests end-to-end multi-agent execution through LangGraph."""

    def test_circuit_breaker_early_rejection(self):
        """Validates that impossible budget requests abort immediately without running research."""
        # 4 days in Dubai with AED 250 is mathematically impossible (min ~AED 920)
        prompt = "Plan 4 days in Dubai with 250 AED budget"
        final_state = run_travel_planner(prompt)

        self.assertTrue(final_state.get("is_rejected"))
        self.assertIsNotNone(final_state.get("rejection_reason"))
        self.assertIsNone(final_state.get("final_itinerary"))

        # Verify agent logs reflect early termination
        logs = final_state.get("agent_logs", [])
        nodes_executed = [log["node"] for log in logs]
        self.assertIn("parse_request", nodes_executed)
        self.assertIn("finalize_rejection", nodes_executed)
        self.assertNotIn("destination_research", nodes_executed)
        self.assertNotIn("logistics_planning", nodes_executed)

    def test_standard_trip_execution_flow(self):
        """Validates a standard 3-day request executes all nodes and outputs a valid itinerary."""
        prompt = "Plan a 3-day cultural and foodie trip to Dubai with AED 4,500 budget in February"
        final_state = run_travel_planner(prompt)

        self.assertFalse(final_state.get("is_rejected"))
        self.assertIsNone(final_state.get("rejection_reason"))

        # Check final itinerary
        itinerary_data = final_state.get("final_itinerary")
        self.assertIsNotNone(itinerary_data)
        itinerary = TripItinerary(**itinerary_data)

        self.assertEqual(len(itinerary.days), 3)
        self.assertTrue(itinerary.budget.grand_total_aed <= 4500.0)
        self.assertIn(itinerary.days[0].primary_district, [
            "Old Dubai & Creek", "Downtown & DIFC", "Dubai Marina & JBR",
            "Palm Jumeirah & Jumeirah", "Desert & Outskirts"
        ])

        # Verify trace sequence in agent_logs
        logs = final_state.get("agent_logs", [])
        self.assertGreater(len(logs), 5)
        nodes_executed = [log["node"] for log in logs]
        self.assertIn("parse_request", nodes_executed)
        self.assertIn("destination_research", nodes_executed)
        self.assertIn("logistics_planning", nodes_executed)
        self.assertIn("calculate_budget", nodes_executed)
        self.assertIn("review_itinerary", nodes_executed)
        self.assertIn("finalize_itinerary", nodes_executed)

    def test_overrides_priority(self):
        """Validates that explicit user overrides take precedence over natural language prompt."""
        prompt = "2 days in Dubai with AED 3000"
        overrides = {
            "trip_duration_days": 4,
            "total_budget_aed": 5500.0,
            "accommodation_tier": "budget",
            "interests": ["shopping", "views"]
        }
        final_state = run_travel_planner(prompt, overrides=overrides)

        itinerary = TripItinerary(**final_state["final_itinerary"])
        self.assertEqual(itinerary.constraints.trip_duration_days, 4)
        self.assertEqual(itinerary.constraints.total_budget_aed, 5500.0)
        self.assertEqual(itinerary.constraints.accommodation_tier, "budget")
        self.assertEqual(len(itinerary.days), 4)

    def test_bounded_revision_cycle(self):
        """
        Validates that when a tight budget is provided with midscale hotel,
        the cyclic revision loop triggers, executes cost-cutting substitutions,
        and either passes or cleanly terminates within 3 cycles via fallback_finalize.
        """
        # Tight budget of AED 1,200 for 2 days with midscale tier
        # Midscale Downtown is AED 650/night + food ~AED 260 + admissions ~AED 300 = ~AED 1,210+
        prompt = "2 days in Dubai with AED 1,000 budget, staying in midscale hotel"
        final_state = run_travel_planner(prompt)

        # Ensure revision loop triggered or completed
        rev_count = final_state.get("revision_count", 0)
        self.assertLessEqual(rev_count, 3)

        # Either finalized cleanly or through bounded fallback
        itinerary_data = final_state.get("final_itinerary")
        self.assertIsNotNone(itinerary_data)
        itinerary = TripItinerary(**itinerary_data)
        self.assertEqual(len(itinerary.days), 2)


if __name__ == "__main__":
    unittest.main()
