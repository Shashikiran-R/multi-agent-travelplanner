"""
Unit and Integration Test Suite for Phase 6: Streamlit Interactive UI & Observability Dashboard.
Tests AppTest execution, preset configuration, circuit breaker view,
and 4-tab dashboard rendering (Timeline, Map, Financials, Observability).
Zero paid APIs ($0.00 cost).
"""

import os
import unittest
from streamlit.testing.v1 import AppTest

APP_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))

from src.data_access.sqlite_client import DubaiSQLiteClient
from src.models.request import UserConstraints
from src.models.itinerary import (
    TripItinerary, DayPlan, ActivitySlot, TransitSegment
)
from src.models.budget import BudgetBreakdown, CostItem
from src.models.review import ReviewFeedback, ViolationItem


def create_sample_mock_itinerary() -> dict:
    """Constructs a deterministic 2-day mock itinerary dictionary matching TripItinerary schema."""
    constraints = UserConstraints(
        trip_duration_days=2,
        total_budget_aed=3000.0,
        interests=["culture", "views"],
        accommodation_tier="budget",
        pacing_preference="moderate",
        avoid_crowds=False,
        travel_month=2
    )

    day1_activities = [
        ActivitySlot(
            time_slot="morning",
            place_id="att_001",
            place_name="Al Fahidi Historical Neighbourhood",
            category="attraction",
            duration_mins=90,
            cost_aed=0.0,
            district="Old Dubai & Creek",
            lat=25.2631,
            lng=55.2972,
            transit_to_next=TransitSegment(
                origin="Al Fahidi Historical Neighbourhood",
                destination="Al Ustad Special Kebab",
                mode="metro",
                duration_mins=15,
                fare_aed=3.0,
                distance_km=0.8,
                notes="Dubai Metro Silver Nol"
            )
        ),
        ActivitySlot(
            time_slot="afternoon",
            place_id="rest_001",
            place_name="Al Ustad Special Kebab",
            category="dining",
            duration_mins=60,
            cost_aed=55.0,
            district="Old Dubai & Creek",
            lat=25.2605,
            lng=55.2990
        )
    ]

    day2_activities = [
        ActivitySlot(
            time_slot="morning",
            place_id="att_002",
            place_name="Dubai Frame",
            category="attraction",
            duration_mins=75,
            cost_aed=52.5,
            district="Downtown & DIFC",
            lat=25.2345,
            lng=55.3003
        )
    ]

    days = [
        DayPlan(
            day_number=1,
            primary_district="Old Dubai & Creek",
            theme="Heritage Creek & Spice Odyssey",
            activities=day1_activities,
            daily_spend_aed=58.0,
            hotel_area="Deira & Creek",
            transit_summary="Traditional Abra crossing and Red Line Metro"
        ),
        DayPlan(
            day_number=2,
            primary_district="Downtown & DIFC",
            theme="Architectural Marvels & Skyline Views",
            activities=day2_activities,
            daily_spend_aed=52.5,
            hotel_area="Downtown Dubai",
            transit_summary="Direct Metro connections"
        )
    ]

    budget = BudgetBreakdown.calculate(
        accommodation=420.0,
        dining=350.0,
        attractions=105.0,
        transit=30.0,
        budget_limit=3000.0,
        records=[
            CostItem(category="accommodation", item_name="Budget Hotel Deira (1 night)", cost_aed=420.0, day_number=1),
            CostItem(category="attraction", item_name="Dubai Frame Entry", cost_aed=52.5, day_number=2),
            CostItem(category="dining", item_name="Al Ustad Lunch", cost_aed=55.0, day_number=1),
            CostItem(category="transit", item_name="Metro Nol Passes", cost_aed=30.0)
        ]
    )

    review = ReviewFeedback(
        passed=True,
        violations=[],
        structured_violations=[],
        cost_delta_aed=0.0,
        recommended_swaps=[],
        revision_round=0,
        audit_notes="Plan strictly complies with thermal, transit, and financial limits."
    )

    itinerary = TripItinerary(
        trip_id="dxb_test_mock_001",
        title="2-Day Cultural & Skyline Highlights",
        summary="A balanced 2-day exploration of Old Dubai creek culture and modern skyline landmarks.",
        constraints=constraints,
        days=days,
        budget=budget,
        review=review
    )

    return itinerary.model_dump()


class TestStreamlitAppUI(unittest.TestCase):
    """Verifies Streamlit app UI rendering, sidebar presets, rejection states, and tab views."""

    def test_app_initial_render(self):
        """Validates that app.py initializes cleanly with zero exceptions and correct default widgets."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        self.assertFalse(at.exception, f"AppTest raised unexpected exception: {at.exception}")
        # Verify sidebar controls
        self.assertGreater(len(at.sidebar), 5)
        # Verify initial telemetry status
        self.assertIn("planner_result", at.session_state)
        self.assertIsNone(at.session_state["planner_result"])

    def test_app_preset_selection(self):
        """Validates that quick curated presets populate parameters cleanly."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        # Click '🏛️ 4D Heritage' preset button (first button in sidebar)
        self.assertEqual(at.sidebar.button[0].label, "🏛️ 4D Heritage")
        at.sidebar.button[0].click().run()

        self.assertEqual(at.session_state["duration_input"], 4)
        self.assertEqual(at.session_state["budget_input"], 2800.0)
        self.assertEqual(at.session_state["tier_input"], "budget")
        self.assertEqual(at.session_state["month_input"], 11)
        self.assertIn("culture", at.session_state["interests_input"])

    def test_app_circuit_breaker_rejection_view(self):
        """Validates that circuit breaker rejection displays the error message and guidance card."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        at.session_state["planner_result"] = {
            "is_rejected": True,
            "rejection_reason": "Total budget AED 200 is below minimum baseline (AED 690 for 3 days).",
            "agent_logs": [
                {
                    "timestamp": "2026-11-07T12:00:00",
                    "agent": "OrchestratorAgent",
                    "node": "parse_request",
                    "status": "rejected",
                    "message": "Financial baseline violation"
                }
            ]
        }
        at.session_state["execution_latency"] = 0.02
        at.run()

        self.assertFalse(at.exception, f"Rejection view failed: {at.exception}")
        # Verify error card rendered
        self.assertTrue(len(at.error) > 0 or len(at.markdown) > 0)

    def test_app_approved_itinerary_tabs_render(self):
        """Validates that an approved itinerary renders all 4 tabs without exceptions."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        mock_itin = create_sample_mock_itinerary()
        at.session_state["planner_result"] = {
            "is_rejected": False,
            "final_itinerary": mock_itin,
            "revision_count": 0,
            "agent_logs": [
                {"timestamp": "2026-11-07T12:00:00", "agent": "OrchestratorAgent", "node": "parse_request", "status": "success", "message": "Parsed"},
                {"timestamp": "2026-11-07T12:00:01", "agent": "ReviewAgent", "node": "review_itinerary", "status": "approved", "message": "Approved"}
            ]
        }
        at.session_state["execution_latency"] = 0.12
        at.run()

        self.assertFalse(at.exception, f"Approved itinerary tab view failed: {at.exception}")
        # Check that tabs rendered
        self.assertEqual(len(at.tabs), 4)

    def test_climate_profiles_dynamically_loaded(self):
        """Validates that Dubai SQLite database returns correct extreme summer and winter climate profiles."""
        client = DubaiSQLiteClient()
        july = client.get_climate_profile(7)
        january = client.get_climate_profile(1)

        self.assertIsNotNone(july)
        self.assertTrue(july["is_extreme_summer"])
        self.assertGreater(july["avg_high_c"], 40.0)

        self.assertIsNotNone(january)
        self.assertFalse(january["is_extreme_summer"])
        self.assertLess(january["avg_high_c"], 30.0)

    def test_real_time_budget_warning_tag(self):
        """Validates that selecting Luxury tier (AED 1,750) with 4 days and AED 4,500 budget prompts budget increase in real time."""
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()

        # Set 4 days, luxury tier, and AED 4,500 budget
        at.session_state["duration_input"] = 4
        at.session_state["tier_input"] = "luxury"
        at.session_state["budget_input"] = 4500.0
        at.run()

        self.assertFalse(at.exception)
        sidebar_md = " ".join(m.value for m in at.sidebar.markdown)
        self.assertIn("You have to increase the budget", sidebar_md)
        self.assertIn("1,070", sidebar_md)
        self.assertIn("5,570", sidebar_md)

        # Test clicking the auto-fix budget button
        auto_fix_btn = next((b for b in at.sidebar.button if "Set Budget" in b.label), None)
        self.assertIsNotNone(auto_fix_btn, "Expected Set Budget button in sidebar")
        auto_fix_btn.click().run()

        self.assertFalse(at.exception, f"Clicking Set Budget raised unexpected exception: {at.exception}")
        self.assertEqual(at.session_state["budget_input"], 5570.0)
        btn_clicked_md = " ".join(m.value for m in at.sidebar.markdown)
        self.assertIn("Budget sufficient for", btn_clicked_md)


if __name__ == "__main__":
    unittest.main()
