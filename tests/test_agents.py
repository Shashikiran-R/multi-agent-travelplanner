"""
Unit Test Suite for Phase 4 Specialized AI Agents.
Tests OrchestratorAgent, DestinationAgent, LogisticsAgent, BudgetAgent, and ReviewAgent.
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
from src.agents.orchestrator import OrchestratorAgent
from src.agents.destination import DestinationAgent
from src.agents.logistics import LogisticsAgent
from src.agents.budget import BudgetAgent
from src.agents.review import ReviewAgent
from src.data_access.sqlite_client import DubaiSQLiteClient


class TestOrchestratorAgent(unittest.TestCase):
    """Tests natural language parsing, rejection guardrail, and itinerary synthesis."""

    @classmethod
    def setUpClass(cls):
        cls.agent = OrchestratorAgent(llm=None)

    def test_parse_prompt_standard(self):
        prompt = "Plan a 4-day trip to Dubai with AED 5,000 budget in January interested in culture and food, staying in budget hotel"
        constraints, is_rejected, reason = self.agent.parse_prompt(prompt)

        self.assertFalse(is_rejected)
        self.assertIsNone(reason)
        self.assertEqual(constraints.trip_duration_days, 4)
        self.assertEqual(constraints.total_budget_aed, 5000.0)
        self.assertEqual(constraints.travel_month, 1)
        self.assertEqual(constraints.accommodation_tier, "budget")
        self.assertIn("culture", constraints.interests)
        self.assertIn("food", constraints.interests)

    def test_rejection_guardrail_triggered(self):
        # 4 days with AED 300 budget (mathematically impossible, min is ~AED 920)
        prompt = "4 days in Dubai with 300 AED budget"
        constraints, is_rejected, reason = self.agent.parse_prompt(prompt)

        self.assertTrue(is_rejected)
        self.assertIsNotNone(reason)
        self.assertIn("Budget Rejection", reason)
        self.assertIn("Old Dubai/Deira", reason)

    def test_rejection_guardrail_passed(self):
        # 3 days with AED 3,500 budget (plenty of buffer)
        prompt = "3-day luxury trip with 7000 aed budget"
        constraints, is_rejected, reason = self.agent.parse_prompt(prompt)

        self.assertFalse(is_rejected)
        self.assertIsNone(reason)
        self.assertEqual(constraints.trip_duration_days, 3)
        self.assertEqual(constraints.accommodation_tier, "luxury")

    def test_assemble_final_itinerary(self):
        constraints = UserConstraints(trip_duration_days=1, total_budget_aed=1500.0)
        day1 = DayPlan(day_number=1, primary_district="Old Dubai & Creek", theme="Culture", hotel_area="Old Dubai & Creek", activities=[])
        budget = BudgetBreakdown.calculate(accommodation=210.0, dining=70.0, attractions=50.0, transit=15.0, budget_limit=1500.0)
        review = ReviewFeedback(passed=True, revision_round=0)

        itinerary = self.agent.assemble_final_itinerary(constraints, [day1], budget, review)
        self.assertIsInstance(itinerary, TripItinerary)
        self.assertTrue(itinerary.trip_id.startswith("dxb_"))
        self.assertEqual(len(itinerary.days), 1)
        self.assertTrue(itinerary.review.passed)


class TestDestinationAgent(unittest.TestCase):
    """Tests destination research and summer climate adaptation."""

    @classmethod
    def setUpClass(cls):
        cls.agent = DestinationAgent(llm=None)

    def test_research_destinations_winter(self):
        constraints = UserConstraints(
            trip_duration_days=3,
            total_budget_aed=4000.0,
            interests=["culture", "food"],
            travel_month=1  # January
        )
        findings = self.agent.research_destinations(constraints, target_districts=["Old Dubai & Creek", "Downtown & DIFC"])

        self.assertGreater(findings["total_attractions_found"], 0)
        self.assertGreater(findings["total_restaurants_found"], 0)
        self.assertFalse(findings["is_summer_adapted"])

    def test_research_destinations_summer_adaptation(self):
        constraints = UserConstraints(
            trip_duration_days=3,
            total_budget_aed=4000.0,
            interests=["culture", "views"],
            travel_month=7  # Extreme Summer July
        )
        findings = self.agent.research_destinations(constraints, target_districts=["Downtown & DIFC"])

        self.assertTrue(findings["is_summer_adapted"])
        self.assertIsNotNone(findings["climate_advisory"])
        self.assertIn("Summer Season Advisory", findings["climate_advisory"])
        # Verify indoor attractions are retrieved
        indoor_found = [a for a in findings["candidate_attractions"] if a.get("is_indoor")]
        self.assertGreater(len(indoor_found), 0)


class TestLogisticsAgent(unittest.TestCase):
    """Tests geographic clustering, daily sequencing, and RTA transit integration."""

    @classmethod
    def setUpClass(cls):
        cls.agent = LogisticsAgent(llm=None)
        cls.dest_agent = DestinationAgent(llm=None)

    def test_plan_itinerary_logistics_multiday(self):
        constraints = UserConstraints(
            trip_duration_days=3,
            total_budget_aed=3500.0,
            interests=["culture", "food", "views"],
            accommodation_tier="budget",
            travel_month=1
        )
        findings = self.dest_agent.research_destinations(constraints)
        days, hotel_area = self.agent.plan_itinerary_logistics(
            constraints=constraints,
            candidate_attractions=findings["candidate_attractions"],
            candidate_restaurants=findings["candidate_restaurants"]
        )

        self.assertEqual(len(days), 3)
        self.assertIn(hotel_area, ["Old Dubai & Creek", "Downtown & DIFC"])

        # Check Day 1 integrity
        day1 = days[0]
        self.assertEqual(day1.day_number, 1)
        self.assertGreater(len(day1.activities), 0)
        self.assertLessEqual(len(day1.activities), 4)

        # Check transit segment between activities
        if len(day1.activities) > 1:
            first_act = day1.activities[0]
            self.assertIsNotNone(first_act.transit_to_next)
            self.assertIsInstance(first_act.transit_to_next, TransitSegment)
            self.assertGreaterEqual(first_act.transit_to_next.fare_aed, 0.0)

    def test_plan_itinerary_logistics_summer_afternoon_indoor(self):
        # Extreme summer July month
        constraints = UserConstraints(
            trip_duration_days=2,
            total_budget_aed=4000.0,
            travel_month=7,  # July
            accommodation_tier="midscale"
        )
        findings = self.dest_agent.research_destinations(constraints)
        days, _ = self.agent.plan_itinerary_logistics(
            constraints=constraints,
            candidate_attractions=findings["candidate_attractions"],
            candidate_restaurants=findings["candidate_restaurants"]
        )

        # Verify that for each day, afternoon attractions are indoor
        for day in days:
            for act in day.activities:
                if act.time_slot == "afternoon" and act.category == "attraction":
                    place_info = DubaiSQLiteClient().get_attraction_by_id(act.place_id)
                    if place_info:
                        self.assertTrue(
                            place_info.get("is_indoor", False),
                            f"Expected indoor afternoon activity on Day {day.day_number}, got {act.place_name}"
                        )


class TestBudgetAgent(unittest.TestCase):
    """Tests financial calculation and substitution preparation."""

    @classmethod
    def setUpClass(cls):
        cls.agent = BudgetAgent(llm=None)

    def _sample_day(self) -> DayPlan:
        return DayPlan(
            day_number=1,
            primary_district="Downtown & DIFC",
            theme="Modern Marvels",
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
                    lat=25.197,
                    lng=55.274,
                    transit_to_next=TransitSegment(
                        origin="Burj Khalifa", destination="Restaurant",
                        mode="taxi", duration_mins=15, fare_aed=25.0
                    )
                ),
                ActivitySlot(
                    time_slot="afternoon",
                    place_id="rest_downtown_01",
                    place_name="Atmosphere Lounge",
                    category="dining",
                    duration_mins=90,
                    cost_aed=280.0,
                    district="Downtown & DIFC",
                    lat=25.197,
                    lng=55.274
                )
            ]
        )

    def test_calculate_budget_under_limit(self):
        constraints = UserConstraints(trip_duration_days=1, total_budget_aed=2000.0, accommodation_tier="midscale")
        day1 = self._sample_day()
        breakdown, cost_delta, swaps = self.agent.calculate_budget([day1], constraints, "Downtown & DIFC")

        self.assertEqual(cost_delta, 0.0)
        self.assertTrue(breakdown.is_within_budget)
        self.assertEqual(len(swaps), 0)

    def test_calculate_budget_over_limit_generates_swaps(self):
        # Tight budget of AED 500 (expenses are ~AED 1134)
        constraints = UserConstraints(trip_duration_days=1, total_budget_aed=500.0, accommodation_tier="midscale")
        day1 = self._sample_day()
        breakdown, cost_delta, swaps = self.agent.calculate_budget([day1], constraints, "Downtown & DIFC")

        self.assertGreater(cost_delta, 0.0)
        self.assertFalse(breakdown.is_within_budget)
        self.assertGreater(len(swaps), 0)

        # Apply best swap (Burj Khalifa -> Fountain)
        att_swaps = [s for s in swaps if s["type"] == "attraction_swap"]
        self.assertGreater(len(att_swaps), 0)
        modified_days, applied = self.agent.apply_best_swap([day1], att_swaps[0])
        self.assertTrue(applied)
        self.assertEqual(modified_days[0].activities[0].cost_aed, 0.0)


class TestReviewAgent(unittest.TestCase):
    """Tests deterministic auditing and feedback generation."""

    @classmethod
    def setUpClass(cls):
        cls.agent = ReviewAgent(llm=None)

    def test_audit_compliant_itinerary(self):
        constraints = UserConstraints(trip_duration_days=1, total_budget_aed=3000.0, travel_month=1)
        day1 = DayPlan(
            day_number=1,
            primary_district="Old Dubai & Creek",
            theme="Heritage",
            hotel_area="Old Dubai & Creek",
            activities=[
                ActivitySlot(
                    time_slot="morning",
                    place_id="att_old_01",
                    place_name="Al Fahidi Historical Neighbourhood",
                    category="attraction",
                    duration_mins=90,
                    cost_aed=0.0,
                    district="Old Dubai & Creek",
                    lat=25.263,
                    lng=55.297
                )
            ]
        )
        budget = BudgetBreakdown.calculate(accommodation=210.0, dining=70.0, attractions=0.0, transit=10.0, budget_limit=3000.0)
        feedback = self.agent.audit_itinerary_plan([day1], budget, constraints)

        self.assertTrue(feedback.passed)
        self.assertEqual(len(feedback.structured_violations), 0)
        self.assertEqual(feedback.cost_delta_aed, 0.0)

    def test_audit_violating_itinerary(self):
        # Exceeded budget + extreme heat outdoor afternoon activity
        constraints = UserConstraints(trip_duration_days=1, total_budget_aed=200.0, travel_month=7)
        day1 = DayPlan(
            day_number=1,
            primary_district="Palm Jumeirah & Jumeirah",
            theme="Beach",
            hotel_area="Palm Jumeirah & Jumeirah",
            activities=[
                ActivitySlot(
                    time_slot="afternoon",
                    place_id="att_palm_03",
                    place_name="Kite Beach",
                    category="attraction",
                    duration_mins=90,
                    cost_aed=0.0,
                    district="Palm Jumeirah & Jumeirah",
                    lat=25.164,
                    lng=55.207
                )
            ]
        )
        budget = BudgetBreakdown.calculate(accommodation=350.0, dining=70.0, attractions=0.0, transit=10.0, budget_limit=200.0)
        feedback = self.agent.audit_itinerary_plan([day1], budget, constraints)

        self.assertFalse(feedback.passed)
        rule_names = [v.rule_name for v in feedback.structured_violations]
        self.assertIn("budget_limit", rule_names)
        self.assertIn("thermal_safety", rule_names)


class MockLLM:
    """Helper Mock LLM class simulating Groq or Gemini responses."""
    def __init__(self, response_text: str):
        self.response_text = response_text

    def invoke(self, messages):
        class MockResponse:
            def __init__(self, content):
                self.content = content
        return MockResponse(self.response_text)


class TestAgentLLMIntegrations(unittest.TestCase):
    """
    Validates Groq integration on Orchestrator, Destination, Logistics, Budget
    and Google Gemini integration on Review Agent.
    """

    def test_orchestrator_groq_parsing(self):
        mock_groq_json = (
            '{\n'
            '  "trip_duration_days": 5,\n'
            '  "total_budget_aed": 6500.0,\n'
            '  "interests": ["culture", "views", "shopping"],\n'
            '  "accommodation_tier": "luxury",\n'
            '  "pacing_preference": "relaxed",\n'
            '  "avoid_crowds": true,\n'
            '  "travel_month": 11\n'
            '}'
        )
        agent = OrchestratorAgent(llm=MockLLM(mock_groq_json))
        prompt = "I want a 5-day luxury trip in November for shopping and culture with 6500 AED"
        constraints, is_rejected, reason = agent.parse_prompt(prompt)

        self.assertFalse(is_rejected)
        self.assertEqual(constraints.trip_duration_days, 5)
        self.assertEqual(constraints.total_budget_aed, 6500.0)
        self.assertEqual(constraints.accommodation_tier, "luxury")
        self.assertEqual(constraints.pacing_preference, "relaxed")
        self.assertTrue(constraints.avoid_crowds)
        self.assertEqual(constraints.travel_month, 11)

    def test_destination_groq_concierge_notes(self):
        mock_groq_advice = (
            "- Visit Al Shindagha Museum during morning hours for best cultural heritage guidance.\n"
            "- Taste authentic Machboos at Al Fanar Restaurant & Cafe in Al Seef.\n"
            "- Modest dress code recommended when strolling through the historic Al Fahidi quarters."
        )
        agent = DestinationAgent(llm=MockLLM(mock_groq_advice))
        constraints = UserConstraints(trip_duration_days=2, total_budget_aed=3000.0, interests=["culture", "food"])
        findings = agent.research_destinations(constraints, target_districts=["Old Dubai & Creek"])

        self.assertIn("concierge_notes", findings)
        self.assertIn("Al Shindagha Museum", findings["concierge_notes"])
        self.assertIn("Machboos", findings["concierge_notes"])

    def test_logistics_groq_theme_and_briefing(self):
        mock_groq_theme = "Heritage Creek & Spice Odyssey"
        agent = LogisticsAgent(llm=MockLLM(mock_groq_theme))
        constraints = UserConstraints(trip_duration_days=1, total_budget_aed=2500.0)
        dest_agent = DestinationAgent(llm=MockLLM("mock notes"))
        findings = dest_agent.research_destinations(constraints, target_districts=["Old Dubai & Creek"])

        days, hotel_area = agent.plan_itinerary_logistics(
            constraints=constraints,
            candidate_attractions=findings["candidate_attractions"],
            candidate_restaurants=findings["candidate_restaurants"]
        )
        self.assertEqual(len(days), 1)
        self.assertEqual(days[0].theme, "Heritage Creek & Spice Odyssey")

        # Test briefing with Groq
        mock_briefing = "Lodging in Old Dubai minimizes travel time. Silver Nol metro cards cover all intra-city legs efficiently."
        agent.llm = MockLLM(mock_briefing)
        briefing = agent.generate_logistics_briefing(days, hotel_area, constraints)
        self.assertIn("Silver Nol metro cards", briefing)

    def test_budget_groq_financial_narrative(self):
        mock_groq_narrative = (
            "Executive Financial Review: Projected total spend of AED 2,150.00 is well within the "
            "AED 3,000.00 budget ceiling, providing a secure reserve of AED 850.00. Accommodation in Old Dubai "
            "accounts for 52% of total expenditures, maximizing travel value."
        )
        agent = BudgetAgent(llm=MockLLM(mock_groq_narrative))
        constraints = UserConstraints(trip_duration_days=2, total_budget_aed=3000.0, accommodation_tier="budget")
        day1 = DayPlan(
            day_number=1, primary_district="Old Dubai & Creek", theme="Culture", hotel_area="Old Dubai & Creek", activities=[]
        )
        breakdown, cost_delta, swaps = agent.calculate_budget([day1], constraints, "Old Dubai & Creek")

        self.assertIsNotNone(agent.last_financial_narrative)
        self.assertIn("Executive Financial Review", agent.last_financial_narrative)
        self.assertIn("AED 850.00", agent.last_financial_narrative)

    def test_review_ollama_qa_commentary(self):
        mock_ollama_commentary = (
            "Chief QA Compliance Review (Ollama nemotron-3-ultra): Itinerary successfully validated. "
            "Geographical cohesion is strictly preserved with zero cross-city transit jumps. "
            "Pacing of 3 activities/day ensures a relaxed, realistic traveler journey."
        )
        agent = ReviewAgent(llm=MockLLM(mock_ollama_commentary))
        constraints = UserConstraints(trip_duration_days=1, total_budget_aed=3000.0, travel_month=2)
        day1 = DayPlan(
            day_number=1, primary_district="Old Dubai & Creek", theme="Heritage", hotel_area="Old Dubai & Creek", activities=[]
        )
        budget = BudgetBreakdown.calculate(accommodation=210.0, dining=70.0, attractions=0.0, transit=10.0, budget_limit=3000.0)

        feedback = agent.audit_itinerary_plan([day1], budget, constraints)
        self.assertTrue(feedback.passed)
        self.assertIsNotNone(feedback.audit_notes)
        self.assertIn("Chief QA Compliance Review", feedback.audit_notes)
        self.assertIn("Ollama nemotron-3-ultra", feedback.audit_notes)

    def test_llm_factory_groq_model_resolution(self):
        from unittest.mock import patch
        from src.utils.llm_factory import get_groq_llm

        with patch("src.utils.llm_factory.is_groq_available", return_value=True):
            with patch("langchain_groq.ChatGroq") as mock_chat_groq:
                # 1. Default model
                get_groq_llm()
                mock_chat_groq.assert_called_with(
                    model="openai/gpt-oss-120b",
                    temperature=0.2,
                    max_tokens=2048,
                    max_retries=1,
                    timeout=15,
                    groq_api_key=unittest.mock.ANY
                )

                # 2. oss-120b alias normalization
                get_groq_llm(model="oss-120b")
                mock_chat_groq.assert_called_with(
                    model="openai/gpt-oss-120b",
                    temperature=0.2,
                    max_tokens=2048,
                    max_retries=1,
                    timeout=15,
                    groq_api_key=unittest.mock.ANY
                )

    def test_llm_factory_ollama_model_resolution(self):
        import os
        from unittest.mock import patch
        from src.utils.llm_factory import get_ollama_llm

        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://localhost:11434", "OLLAMA_API_KEY": ""}):
            with patch("langchain_ollama.ChatOllama") as mock_chat_ollama:
                # 1. Default model nemotron-3-ultra
                get_ollama_llm()
                mock_chat_ollama.assert_called_with(
                    model="nemotron-3-ultra",
                    base_url="http://localhost:11434",
                    temperature=0.1,
                    timeout=20
                )

                # 2. Custom model or base_url
                get_ollama_llm(model="custom-nemotron", base_url="http://ollama-host:11434")
                mock_chat_ollama.assert_called_with(
                    model="custom-nemotron",
                    base_url="http://ollama-host:11434",
                    temperature=0.1,
                    timeout=20
                )

                # 3. Cloud endpoint with API Key authentication (client_kwargs headers)
                get_ollama_llm(
                    model="nemotron-3-ultra",
                    base_url="https://api.ollama.ai",
                    api_key="sk-ollama-cloud-test-key"
                )
                mock_chat_ollama.assert_called_with(
                    model="nemotron-3-ultra",
                    base_url="https://api.ollama.ai",
                    temperature=0.1,
                    timeout=20,
                    client_kwargs={
                        "headers": {
                            "Authorization": "Bearer sk-ollama-cloud-test-key",
                            "x-api-key": "sk-ollama-cloud-test-key"
                        }
                    }
                )


if __name__ == "__main__":
    unittest.main()
