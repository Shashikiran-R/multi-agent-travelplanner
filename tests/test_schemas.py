#!/usr/bin/env python3
"""
Unit Test Suite for Pydantic V2 Schemas & Data Contracts.
Validates input constraints, nested serialization, and error conditions.
"""

import unittest
from pydantic import ValidationError

from src.models import (
    UserConstraints,
    RawTripPrompt,
    CostItem,
    BudgetBreakdown,
    ViolationItem,
    ReviewFeedback,
    AttractionItem,
    RestaurantItem,
    TransitSegment,
    ActivitySlot,
    DayPlan,
    TripItinerary,
)


class TestRequestSchemas(unittest.TestCase):
    def test_valid_user_constraints(self):
        constraints = UserConstraints(
            trip_duration_days=4,
            total_budget_aed=5000.0,
            interests=["Culture", " BEACH ", "Food"],
            accommodation_tier="budget",
            pacing_preference="moderate",
            avoid_crowds=True,
            travel_month=3
        )
        self.assertEqual(constraints.trip_duration_days, 4)
        self.assertEqual(constraints.total_budget_aed, 5000.0)
        self.assertEqual(constraints.interests, ["culture", "beach", "food"])
        self.assertTrue(constraints.avoid_crowds)
        self.assertEqual(constraints.travel_month, 3)

    def test_invalid_duration_out_of_bounds(self):
        # Days must be between 1 and 7
        with self.assertRaises(ValidationError):
            UserConstraints(trip_duration_days=0, total_budget_aed=2000.0)
        with self.assertRaises(ValidationError):
            UserConstraints(trip_duration_days=8, total_budget_aed=2000.0)

    def test_invalid_budget_too_low(self):
        # Less than 150 AED triggers subsistence validation error
        with self.assertRaises(ValidationError):
            UserConstraints(trip_duration_days=3, total_budget_aed=50.0)

    def test_invalid_travel_month(self):
        with self.assertRaises(ValidationError):
            UserConstraints(trip_duration_days=3, total_budget_aed=2000.0, travel_month=13)


class TestBudgetSchemas(unittest.TestCase):
    def test_budget_breakdown_calculation_within_budget(self):
        breakdown = BudgetBreakdown.calculate(
            accommodation=750.0,
            dining=1200.0,
            attractions=1800.0,
            transit=400.0,
            budget_limit=5000.0
        )
        self.assertEqual(breakdown.grand_total_aed, 4150.0)
        self.assertEqual(breakdown.remaining_balance_aed, 850.0)
        self.assertTrue(breakdown.is_within_budget)

    def test_budget_breakdown_over_budget(self):
        breakdown = BudgetBreakdown.calculate(
            accommodation=2000.0,
            dining=1500.0,
            attractions=2500.0,
            transit=500.0,
            budget_limit=5000.0
        )
        self.assertEqual(breakdown.grand_total_aed, 6500.0)
        self.assertEqual(breakdown.remaining_balance_aed, -1500.0)
        self.assertFalse(breakdown.is_within_budget)


class TestReviewSchemas(unittest.TestCase):
    def test_review_feedback_structure(self):
        violation = ViolationItem(
            rule_name="budget_limit",
            severity="critical",
            message="Grand total exceeds budget limit by AED 450",
            affected_day=2,
            suggested_action="Swap Desert Safari with Heritage Walking Tour"
        )
        feedback = ReviewFeedback(
            passed=False,
            violations=[violation.message],
            structured_violations=[violation],
            cost_delta_aed=450.0,
            recommended_swaps=[violation.suggested_action],
            revision_round=1
        )
        self.assertFalse(feedback.passed)
        self.assertEqual(len(feedback.violations), 1)
        self.assertEqual(feedback.cost_delta_aed, 450.0)
        self.assertEqual(feedback.revision_round, 1)


class TestItinerarySchemas(unittest.TestCase):
    def test_complete_trip_itinerary_nesting_and_serialization(self):
        constraints = UserConstraints(
            trip_duration_days=1,
            total_budget_aed=1500.0,
            interests=["culture"]
        )
        budget = BudgetBreakdown.calculate(
            accommodation=250.0,
            dining=120.0,
            attractions=50.0,
            transit=30.0,
            budget_limit=1500.0
        )
        review = ReviewFeedback(passed=True, revision_round=0)

        transit_step = TransitSegment(
            origin="Al Fahidi Neighbourhood",
            destination="Arabian Tea House",
            mode="walk",
            duration_mins=5,
            fare_aed=0.0
        )

        activity_1 = ActivitySlot(
            time_slot="morning",
            place_id="att_01",
            place_name="Al Fahidi Historical Neighbourhood",
            category="attraction",
            duration_mins=90,
            cost_aed=0.0,
            district="Old Dubai & Creek",
            lat=25.2635,
            lng=55.2974,
            transit_to_next=transit_step
        )

        day_1 = DayPlan(
            day_number=1,
            primary_district="Old Dubai & Creek",
            theme="Historic Creekside Culture & Souks",
            activities=[activity_1],
            daily_spend_aed=450.0,
            hotel_area="Deira / Bur Dubai"
        )

        itinerary = TripItinerary(
            trip_id="trip_dubai_test_001",
            title="Dubai Cultural Odyssey (1 Day)",
            summary="Immersive heritage experience through Old Dubai and Creek souks.",
            constraints=constraints,
            days=[day_1],
            budget=budget,
            review=review
        )

        # Validate roundtrip JSON serialization
        json_str = itinerary.model_dump_json()
        self.assertIn("Dubai Cultural Odyssey", json_str)
        self.assertIn("Al Fahidi Historical Neighbourhood", json_str)

        # Validate deserialization back to model
        loaded = TripItinerary.model_validate_json(json_str)
        self.assertEqual(loaded.trip_id, "trip_dubai_test_001")
        self.assertEqual(len(loaded.days), 1)
        self.assertEqual(loaded.days[0].activities[0].transit_to_next.mode, "walk")
        self.assertTrue(loaded.budget.is_within_budget)


if __name__ == "__main__":
    unittest.main()
