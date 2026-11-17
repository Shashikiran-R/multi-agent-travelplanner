"""
Comprehensive Unit Test Suite for Deterministic Domain Tools & Dubai RTA Transit Engine.
Tests RTATransitEngine, PlacesTool, BudgetTool, and ValidationTool.
Zero paid APIs ($0.00 cost).
"""

import unittest
from typing import List

from src.models.request import UserConstraints
from src.models.budget import BudgetBreakdown, CostItem
from src.models.itinerary import (
    ActivitySlot,
    DayPlan,
    TransitSegment,
    TripItinerary,
)
from src.models.review import ReviewFeedback
from src.tools.routing_tool import RTATransitEngine
from src.tools.places_tool import PlacesTool
from src.tools.budget_tool import BudgetTool
from src.tools.validation_tool import ValidationTool
from src.data_access.sqlite_client import DubaiSQLiteClient


class TestRTATransitEngine(unittest.TestCase):
    """Tests the mathematical Dubai RTA transit engine and fare tariffs."""

    def test_haversine_and_road_distance(self):
        # Burj Khalifa (25.1972, 55.2744) to Dubai Frame (25.2285, 55.3003)
        straight_km = RTATransitEngine.haversine_km(25.1972, 55.2744, 25.2285, 55.3003)
        self.assertGreater(straight_km, 3.0)
        self.assertLess(straight_km, 6.0)

        road_km = RTATransitEngine.estimate_road_distance_km(25.1972, 55.2744, 25.2285, 55.3003)
        # Detour factor is 1.28
        self.assertAlmostEqual(road_km, round(straight_km * 1.28, 2), places=2)

    def test_metro_fares_by_explicit_zone(self):
        # Within same zone (zone diff == 0) -> Tier 1: AED 3.00
        fare_same, tier_same = RTATransitEngine.calculate_metro_fare(5.0, origin_zone=6, dest_zone=6)
        self.assertEqual(fare_same, 3.00)
        self.assertIn("Tier 1", tier_same)

        # 2 adjacent zones (zone diff == 1) -> Tier 2: AED 5.00
        fare_adj, tier_adj = RTATransitEngine.calculate_metro_fare(12.0, origin_zone=6, dest_zone=5)
        self.assertEqual(fare_adj, 5.00)
        self.assertIn("Tier 2", tier_adj)

        # 3+ zones (zone diff >= 2) -> Tier 3: AED 7.50
        fare_far, tier_far = RTATransitEngine.calculate_metro_fare(28.0, origin_zone=6, dest_zone=2)
        self.assertEqual(fare_far, 7.50)
        self.assertIn("Tier 3", tier_far)

    def test_metro_fares_by_distance_inference(self):
        # <= 10 km -> Tier 1 (AED 3.00)
        fare_short, _ = RTATransitEngine.calculate_metro_fare(9.5)
        self.assertEqual(fare_short, 3.00)

        # 10 - 25 km -> Tier 2 (AED 5.00)
        fare_mid, _ = RTATransitEngine.calculate_metro_fare(18.0)
        self.assertEqual(fare_mid, 5.00)

        # > 25 km -> Tier 3 (AED 7.50)
        fare_long, _ = RTATransitEngine.calculate_metro_fare(26.5)
        self.assertEqual(fare_long, 7.50)

    def test_taxi_fares_minimum_and_running_rate(self):
        # Extremely short distance: Base (5.00) + 1.0 km * 2.21 = 7.21, but minimum fare is AED 12.00
        short_taxi = RTATransitEngine.calculate_taxi_fare(1.0, is_night=False)
        self.assertEqual(short_taxi, 12.00)

        # Long distance day: Base (5.00) + 10.0 km * 2.21 = 27.10
        day_taxi = RTATransitEngine.calculate_taxi_fare(10.0, is_night=False)
        self.assertEqual(day_taxi, 27.10)

        # Long distance night: Base (5.50) + 10.0 km * 2.21 = 27.60
        night_taxi = RTATransitEngine.calculate_taxi_fare(10.0, is_night=True)
        self.assertEqual(night_taxi, 27.60)

    def test_traditional_abra_creek_crossing(self):
        # Across Dubai Creek between Bur Dubai (25.263) and Deira (25.269)
        segment = RTATransitEngine.build_transit_segment(
            origin_name="Al Fahidi Historical District",
            dest_name="Deira Gold & Spice Souks",
            origin_lat=25.2635,
            origin_lng=55.2972,
            dest_lat=25.2695,
            dest_lng=55.2995,
            origin_district="Old Dubai & Creek",
            dest_district="Old Dubai & Creek"
        )
        self.assertEqual(segment.fare_aed, 2.00)
        self.assertIn("Abra", segment.notes)

    def test_walking_feasibility_cutoff(self):
        # Walkable distance (< 1.2 km): e.g. 0.4 km between Dubai Mall and Souk Al Bahar
        walk_seg = RTATransitEngine.build_transit_segment(
            origin_name="Dubai Mall",
            dest_name="Souk Al Bahar",
            origin_lat=25.1975,
            origin_lng=55.2795,
            dest_lat=25.1950,
            dest_lng=55.2780,
            origin_district="Downtown & DIFC",
            dest_district="Downtown & DIFC"
        )
        self.assertEqual(walk_seg.mode, "walk")
        self.assertEqual(walk_seg.fare_aed, 0.0)

        # Non-walkable distance (> 1.2 km): should default to metro/transit
        far_seg = RTATransitEngine.build_transit_segment(
            origin_name="Dubai Mall",
            dest_name="Dubai Frame",
            origin_lat=25.1975,
            origin_lng=55.2795,
            dest_lat=25.2285,
            dest_lng=55.3003,
            origin_district="Downtown & DIFC",
            dest_district="Downtown & DIFC"
        )
        self.assertNotEqual(far_seg.mode, "walk")
        self.assertGreater(far_seg.fare_aed, 0.0)


class TestPlacesTool(unittest.TestCase):
    """Tests the PlacesTool SQLite-backed queries and clustering."""

    @classmethod
    def setUpClass(cls):
        cls.db = DubaiSQLiteClient()
        cls.tool = PlacesTool(db_client=cls.db)

    def test_search_attractions(self):
        # Search downtown attractions
        downtown_attractions = self.tool.search_attractions(
            district="Downtown & DIFC",
            limit=5
        )
        self.assertGreater(len(downtown_attractions), 0)
        for att in downtown_attractions:
            self.assertEqual(att["district"], "Downtown & DIFC")
            self.assertIn("admission_fee_aed", att)

    def test_search_restaurants(self):
        # Search budget restaurants in Old Dubai
        budget_eats = self.tool.search_restaurants(
            district="Old Dubai & Creek",
            price_tier="budget",
            limit=5
        )
        self.assertGreater(len(budget_eats), 0)
        for r in budget_eats:
            self.assertEqual(r["price_tier"], "budget")
            self.assertLessEqual(r["avg_cost_aed"], 50.0)

    def test_cluster_places_by_district(self):
        places = [
            {"id": "1", "name": "Burj Khalifa", "district": "Downtown & DIFC"},
            {"id": "2", "name": "Dubai Mall", "district": "Downtown & DIFC"},
            {"id": "3", "name": "Gold Souk", "district": "Old Dubai & Creek"},
        ]
        clusters = self.tool.cluster_places_by_district(places)
        self.assertEqual(len(clusters["Downtown & DIFC"]), 2)
        self.assertEqual(len(clusters["Old Dubai & Creek"]), 1)

    def test_recommend_district_sequence(self):
        seq_3 = self.tool.recommend_district_sequence(3)
        self.assertEqual(len(seq_3), 3)
        self.assertEqual(seq_3[0]["day_number"], 1)
        self.assertEqual(seq_3[1]["day_number"], 2)
        self.assertEqual(seq_3[2]["day_number"], 3)

        # Beach first preference swaps day 1 and 3
        seq_beach = self.tool.recommend_district_sequence(3, interests=["beach"])
        self.assertEqual(seq_beach[0]["primary_district"], "Dubai Marina & JBR")

    def test_recommend_base_hotel_area(self):
        # Budget preference chooses Old Dubai if in primary districts
        hotel_area = self.tool.recommend_base_hotel_area(["Old Dubai & Creek", "Downtown & DIFC"], "budget")
        self.assertEqual(hotel_area, "Old Dubai & Creek")

    def test_places_tool_indoor_free_and_district_summary(self):
        # 1. Test indoor attractions retrieval
        indoor_places = self.tool.get_indoor_attractions(limit=5)
        self.assertGreater(len(indoor_places), 0)
        for p in indoor_places:
            self.assertTrue(p["is_indoor"])

        # 2. Test free attractions retrieval
        free_places = self.tool.get_free_attractions(limit=5)
        self.assertGreater(len(free_places), 0)
        for p in free_places:
            self.assertEqual(p["admission_fee_aed"], 0.0)

        # 3. Test district summary across 5 districts
        summary = self.tool.get_district_summary()
        self.assertIn("Old Dubai & Creek", summary)
        self.assertIn("Downtown & DIFC", summary)
        self.assertIn("Dubai Marina & JBR", summary)
        self.assertIn("Palm Jumeirah & Jumeirah", summary)
        self.assertIn("Desert & Outskirts", summary)
        self.assertGreater(summary["Old Dubai & Creek"]["attractions"], 30)
        self.assertGreater(summary["Downtown & DIFC"]["attractions"], 15)


class TestBudgetTool(unittest.TestCase):
    """Tests deterministic cost calculations, variance calculation, and substitution swaps."""

    @classmethod
    def setUpClass(cls):
        cls.db = DubaiSQLiteClient()
        cls.tool = BudgetTool(db_client=cls.db)

    def _create_sample_day_plan(self) -> DayPlan:
        return DayPlan(
            day_number=1,
            primary_district="Downtown & DIFC",
            theme="Modern Icons",
            hotel_area="Downtown & DIFC",
            activities=[
                ActivitySlot(
                    time_slot="morning",
                    place_id="att_downtown_01",
                    place_name="Burj Khalifa — At The Top (Levels 124 & 125)",
                    category="attraction",
                    duration_mins=120,
                    cost_aed=179.0,
                    district="Downtown & DIFC",
                    lat=25.1972,
                    lng=55.2744,
                    transit_to_next=TransitSegment(
                        origin="Burj Khalifa",
                        destination="Atmosphere Restaurant",
                        mode="taxi",
                        duration_mins=15,
                        fare_aed=25.0
                    )
                ),
                ActivitySlot(
                    time_slot="afternoon",
                    place_id="rest_downtown_01",
                    place_name="Atmosphere Lounge (Burj Khalifa)",
                    category="dining",
                    duration_mins=90,
                    cost_aed=280.0,
                    district="Downtown & DIFC",
                    lat=25.1972,
                    lng=55.2744
                )
            ]
        )

    def test_calculate_itinerary_budget(self):
        day1 = self._create_sample_day_plan()
        breakdown = self.tool.calculate_itinerary_budget(
            days=[day1],
            hotel_district="Downtown & DIFC",
            hotel_tier="midscale",
            duration_days=1,
            budget_limit_aed=1000.0
        )
        self.assertGreater(breakdown.accommodation_total_aed, 0.0)
        self.assertEqual(breakdown.attractions_total_aed, 179.0)
        self.assertEqual(breakdown.dining_total_aed, 280.0)
        self.assertEqual(breakdown.transit_total_aed, 25.0)
        self.assertEqual(breakdown.budget_limit_aed, 1000.0)
        self.assertAlmostEqual(
            breakdown.grand_total_aed,
            breakdown.accommodation_total_aed + 179.0 + 280.0 + 25.0,
            places=2
        )

    def test_generate_cost_cutting_swaps_and_reduction(self):
        day1 = self._create_sample_day_plan()
        # Set a tight budget so remaining balance is negative (deficit)
        breakdown = self.tool.calculate_itinerary_budget(
            days=[day1],
            hotel_district="Downtown & DIFC",
            hotel_tier="midscale",
            duration_days=1,
            budget_limit_aed=400.0  # grand_total will be ~1084 AED -> ~684 deficit
        )
        self.assertLess(breakdown.remaining_balance_aed, 0)

        swaps = self.tool.generate_cost_cutting_swaps(
            days=[day1],
            current_breakdown=breakdown,
            hotel_district="Downtown & DIFC",
            hotel_tier="midscale",
            duration_days=1
        )
        self.assertGreater(len(swaps), 0)

        # Check that Burj Khalifa swap is proposed
        attraction_swaps = [s for s in swaps if s["type"] == "attraction_swap"]
        self.assertGreater(len(attraction_swaps), 0)
        self.assertIn("Fountain", attraction_swaps[0]["description"])
        self.assertEqual(attraction_swaps[0]["savings_aed"], 179.0)

        # Apply the attraction swap to the day plan
        modified_days, applied = BudgetTool.apply_swap_to_itinerary([day1], attraction_swaps[0])
        self.assertTrue(applied)
        # Check activity cost is now 0.0
        self.assertEqual(modified_days[0].activities[0].cost_aed, 0.0)
        self.assertIn("Fountain", modified_days[0].activities[0].place_name)

    def test_attraction_substitute_by_id_and_keyword(self):
        # 1. Test lookup by place_id: att_palm_05 (Aquaventure Waterpark)
        act_by_id = ActivitySlot(
            time_slot="morning",
            place_id="att_palm_05",
            place_name="Aquaventure",
            category="attraction",
            duration_mins=180,
            cost_aed=345.0,
            district="Palm Jumeirah & Jumeirah",
            lat=25.133,
            lng=55.120
        )
        sub1 = self.tool._find_attraction_substitute(act_by_id)
        self.assertIsNotNone(sub1)
        self.assertIn("Palm West Beach", sub1["replacement_name"])
        self.assertEqual(sub1["savings_aed"], 345.0)

        # 2. Test lookup by fuzzy keyword: "Museum of the Future"
        act_by_fuzzy = ActivitySlot(
            time_slot="morning",
            place_id="unknown_id",
            place_name="Visit Museum of the Future",
            category="attraction",
            duration_mins=120,
            cost_aed=149.0,
            district="Downtown & DIFC",
            lat=25.225,
            lng=55.281
        )
        sub2 = self.tool._find_attraction_substitute(act_by_fuzzy)
        self.assertIsNotNone(sub2)
        self.assertIn("Dubai Frame", sub2["replacement_name"])
        self.assertEqual(sub2["savings_aed"], 96.50)


class TestValidationTool(unittest.TestCase):
    """Tests deterministic validation rules and thermal safety audits."""

    @classmethod
    def setUpClass(cls):
        cls.db = DubaiSQLiteClient()
        cls.tool = ValidationTool(db_client=cls.db)

    def test_budget_exceeded_violation(self):
        constraints = UserConstraints(
            trip_duration_days=1,
            total_budget_aed=500.0
        )
        breakdown = BudgetBreakdown.calculate(
            accommodation=400.0,
            dining=150.0,
            attractions=100.0,
            transit=50.0,
            budget_limit=500.0,
            records=[]
        )  # Total: 700 AED, exceeds 500 by 200
        day1 = DayPlan(
            day_number=1,
            primary_district="Downtown & DIFC",
            theme="Day 1",
            hotel_area="Downtown & DIFC",
            activities=[]
        )
        feedback = self.tool.audit_plan([day1], breakdown, constraints)
        self.assertFalse(feedback.passed)
        self.assertGreater(feedback.cost_delta_aed, 0)
        rule_names = [v.rule_name for v in feedback.structured_violations]
        self.assertIn("budget_limit", rule_names)

    def test_pacing_max_activities_violation(self):
        constraints = UserConstraints(
            trip_duration_days=1,
            total_budget_aed=2000.0,
            pacing_preference="relaxed"  # Relaxed max is 3
        )
        breakdown = BudgetBreakdown.calculate(
            accommodation=200.0, dining=50.0, attractions=50.0, transit=20.0,
            budget_limit=2000.0, records=[]
        )
        # 5 activities in one day
        activities = [
            ActivitySlot(
                time_slot="morning",
                place_id=f"p_{i}",
                place_name=f"Place {i}",
                category="attraction",
                duration_mins=60,
                cost_aed=10.0,
                district="Downtown & DIFC",
                lat=25.2,
                lng=55.3
            )
            for i in range(5)
        ]
        day1 = DayPlan(
            day_number=1,
            primary_district="Downtown & DIFC",
            theme="Day 1",
            hotel_area="Downtown & DIFC",
            activities=activities
        )
        feedback = self.tool.audit_plan([day1], breakdown, constraints)
        self.assertFalse(feedback.passed)
        rule_names = [v.rule_name for v in feedback.structured_violations]
        self.assertIn("max_activities_exceeded", rule_names)

    def test_geographic_incoherence_violation(self):
        constraints = UserConstraints(
            trip_duration_days=1,
            total_budget_aed=2000.0
        )
        breakdown = BudgetBreakdown.calculate(
            accommodation=200.0, dining=50.0, attractions=50.0, transit=20.0,
            budget_limit=2000.0, records=[]
        )
        # Combining Old Dubai with Marina on the same day (30+ km cross-city jump)
        act1 = ActivitySlot(
            time_slot="morning",
            place_id="att_old_01",
            place_name="Al Fahidi Historical District",
            category="attraction",
            duration_mins=90,
            cost_aed=0.0,
            district="Old Dubai & Creek",
            lat=25.2635,
            lng=55.2972
        )
        act2 = ActivitySlot(
            time_slot="afternoon",
            place_id="att_marina_01",
            place_name="The Walk at JBR",
            category="attraction",
            duration_mins=90,
            cost_aed=0.0,
            district="Dubai Marina & JBR",
            lat=25.0772,
            lng=55.1325
        )
        day1 = DayPlan(
            day_number=1,
            primary_district="Old Dubai & Creek",
            theme="Day 1",
            hotel_area="Old Dubai & Creek",
            activities=[act1, act2]
        )
        feedback = self.tool.audit_plan([day1], breakdown, constraints)
        self.assertFalse(feedback.passed)
        rule_names = [v.rule_name for v in feedback.structured_violations]
        self.assertIn("geographic_incoherence", rule_names)

    def test_duplicate_attraction_violation(self):
        constraints = UserConstraints(
            trip_duration_days=2,
            total_budget_aed=3000.0
        )
        breakdown = BudgetBreakdown.calculate(
            accommodation=400.0, dining=100.0, attractions=100.0, transit=40.0,
            budget_limit=3000.0, records=[]
        )
        # Scheduling Dubai Mall on Day 1 and Day 2
        day1_act = ActivitySlot(
            time_slot="morning",
            place_id="att_downtown_02",
            place_name="The Dubai Mall",
            category="attraction",
            duration_mins=120,
            cost_aed=0.0,
            district="Downtown & DIFC",
            lat=25.1985,
            lng=55.2796
        )
        day2_act = ActivitySlot(
            time_slot="morning",
            place_id="att_downtown_02",
            place_name="The Dubai Mall",
            category="attraction",
            duration_mins=120,
            cost_aed=0.0,
            district="Downtown & DIFC",
            lat=25.1985,
            lng=55.2796
        )
        day1 = DayPlan(day_number=1, primary_district="Downtown & DIFC", theme="Day 1", hotel_area="Downtown & DIFC", activities=[day1_act])
        day2 = DayPlan(day_number=2, primary_district="Downtown & DIFC", theme="Day 2", hotel_area="Downtown & DIFC", activities=[day2_act])
        feedback = self.tool.audit_plan([day1, day2], breakdown, constraints)
        self.assertFalse(feedback.passed)
        rule_names = [v.rule_name for v in feedback.structured_violations]
        self.assertIn("duplicate_attraction", rule_names)

    def test_thermal_safety_summer_afternoon_violation(self):
        # Month 7 (July) - outdoor beach activity in the afternoon
        constraints = UserConstraints(
            trip_duration_days=1,
            total_budget_aed=2000.0,
            travel_month=7  # Extreme summer
        )
        breakdown = BudgetBreakdown.calculate(
            accommodation=200.0, dining=50.0, attractions=0.0, transit=20.0,
            budget_limit=2000.0, records=[]
        )
        outdoor_act = ActivitySlot(
            time_slot="afternoon",  # 11:30 AM to 16:30 PM
            place_id="att_palm_03",
            place_name="Kite Beach Promenade & Sands",
            category="attraction",
            duration_mins=90,
            cost_aed=0.0,
            district="Palm Jumeirah & Jumeirah",
            lat=25.1642,
            lng=55.2078
        )
        day1 = DayPlan(
            day_number=1,
            primary_district="Palm Jumeirah & Jumeirah",
            theme="Coastal Day",
            hotel_area="Palm Jumeirah & Jumeirah",
            activities=[outdoor_act]
        )
        feedback = self.tool.audit_plan([day1], breakdown, constraints)
        self.assertFalse(feedback.passed)
        rule_names = [v.rule_name for v in feedback.structured_violations]
        self.assertIn("thermal_safety", rule_names)
        self.assertTrue(any("heat" in m.lower() or "thermal" in m.lower() for m in feedback.violations))

    def test_clean_valid_itinerary_passes(self):
        # High budget, 3 activities in same district, indoor summer afternoon or winter month
        constraints = UserConstraints(
            trip_duration_days=1,
            total_budget_aed=3000.0,
            travel_month=1  # January (mild winter)
        )
        breakdown = BudgetBreakdown.calculate(
            accommodation=300.0, dining=120.0, attractions=100.0, transit=30.0,
            budget_limit=3000.0, records=[]
        )
        act1 = ActivitySlot(
            time_slot="morning",
            place_id="att_old_01",
            place_name="Al Fahidi Historical District",
            category="attraction",
            duration_mins=90,
            cost_aed=0.0,
            district="Old Dubai & Creek",
            lat=25.2635,
            lng=55.2972,
            transit_to_next=TransitSegment(
                origin="Al Fahidi",
                destination="Al Seef",
                mode="walk",
                duration_mins=10,
                fare_aed=0.0
            )
        )
        act2 = ActivitySlot(
            time_slot="afternoon",
            place_id="att_old_02",
            place_name="Al Seef Heritage District",
            category="attraction",
            duration_mins=90,
            cost_aed=0.0,
            district="Old Dubai & Creek",
            lat=25.2605,
            lng=55.3052
        )
        act3 = ActivitySlot(
            time_slot="evening",
            place_id="rest_old_01",
            place_name="Al Ustad Special Kabab",
            category="dining",
            duration_mins=60,
            cost_aed=45.0,
            district="Old Dubai & Creek",
            lat=25.2588,
            lng=55.2995
        )
        day1 = DayPlan(
            day_number=1,
            primary_district="Old Dubai & Creek",
            theme="Heritage Immersion",
            hotel_area="Old Dubai & Creek",
            activities=[act1, act2, act3]
        )
        feedback = self.tool.audit_plan([day1], breakdown, constraints)
        self.assertTrue(feedback.passed)
        self.assertEqual(len(feedback.violations), 0)


if __name__ == "__main__":
    unittest.main()
