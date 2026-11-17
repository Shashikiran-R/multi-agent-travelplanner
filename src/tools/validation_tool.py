"""
Deterministic Constraint Auditor & Quality Assurance Tool.
Audits candidate itineraries against hard financial limits, thermal safety guidelines,
geographic clustering coherence, pacing rules, and transit feasibility.
Zero paid APIs ($0.00 cost).
"""

from typing import List, Dict, Any, Optional, Set
from src.models.request import UserConstraints
from src.models.budget import BudgetBreakdown
from src.models.review import ReviewFeedback, ViolationItem
from src.models.itinerary import DayPlan, TripItinerary, ActivitySlot
from src.data_access.sqlite_client import DubaiSQLiteClient
from src.tools.budget_tool import BudgetTool


class ValidationTool:
    """
    Deterministic domain auditor used by the Review Agent to validate itineraries.
    Ensures that generated plans comply with safety, budget, and geographic rules.
    """

    # Incompatible district pairs that should never be visited on the same day
    INCOMPATIBLE_DISTRICT_PAIRS = [
        ({"Old Dubai & Creek"}, {"Dubai Marina & JBR"}),
        ({"Old Dubai & Creek"}, {"Palm Jumeirah & Jumeirah"}),
        ({"Desert & Outskirts"}, {"Dubai Marina & JBR"}),
    ]

    # Extreme summer months in Dubai where midday outdoor activity is dangerous
    SUMMER_MONTHS = {6, 7, 8, 9}  # June, July, August, September

    def __init__(
        self,
        db_client: Optional[DubaiSQLiteClient] = None,
        budget_tool: Optional[BudgetTool] = None
    ):
        self.db = db_client or DubaiSQLiteClient()
        self.budget_tool = budget_tool or BudgetTool(db_client=self.db)

    def audit_itinerary(
        self,
        itinerary: TripItinerary,
        constraints: Optional[UserConstraints] = None,
        revision_round: int = 0
    ) -> ReviewFeedback:
        """Audits a complete TripItinerary object."""
        active_constraints = constraints or itinerary.constraints
        return self.audit_plan(
            days=itinerary.days,
            budget=itinerary.budget,
            constraints=active_constraints,
            revision_round=revision_round
        )

    def audit_plan(
        self,
        days: List[DayPlan],
        budget: BudgetBreakdown,
        constraints: UserConstraints,
        revision_round: int = 0
    ) -> ReviewFeedback:
        """
        Executes all deterministic validation checks across the plan.
        Returns a structured ReviewFeedback report.
        """
        violations: List[ViolationItem] = []
        recommended_swaps: List[str] = []

        # -------------------------------------------------------------
        # 1. Budget Cap Validation
        # -------------------------------------------------------------
        cost_delta_aed = round(max(0.0, budget.grand_total_aed - constraints.total_budget_aed), 2)
        if cost_delta_aed > 0.01:
            violations.append(ViolationItem(
                rule_name="budget_limit",
                severity="critical",
                message=(
                    f"Budget exceeded by AED {cost_delta_aed:.2f}. "
                    f"Total proposed cost AED {budget.grand_total_aed:.2f} exceeds "
                    f"user ceiling of AED {constraints.total_budget_aed:.2f}."
                ),
                suggested_action="Apply recommended cost-cutting substitutions (switch taxis to Metro, select free landmark alternatives, or optimize hotel)."
            ))

            # Generate actionable swaps from BudgetTool
            hotel_district = days[0].hotel_area if days else "Downtown & DIFC"
            swaps = self.budget_tool.generate_cost_cutting_swaps(
                days=days,
                current_breakdown=budget,
                hotel_district=hotel_district,
                hotel_tier=constraints.accommodation_tier,
                duration_days=constraints.trip_duration_days
            )
            for s in swaps[:4]:  # Top 4 recommendations
                recommended_swaps.append(
                    f"[Save AED {s['savings_aed']:.2f}] {s['description']}"
                )

        # -------------------------------------------------------------
        # 2. Pacing & Max Activities Per Day
        # -------------------------------------------------------------
        max_allowed_activities = 3 if constraints.pacing_preference == "relaxed" else 4
        for day in days:
            activity_count = len(day.activities)
            if activity_count > max_allowed_activities:
                is_severe = activity_count > (max_allowed_activities + 1)
                violations.append(ViolationItem(
                    rule_name="max_activities_exceeded",
                    severity="critical" if is_severe else "warning",
                    message=(
                        f"Day {day.day_number} has {activity_count} activities, "
                        f"exceeding the recommended limit of {max_allowed_activities} "
                        f"for '{constraints.pacing_preference}' pacing."
                    ),
                    affected_day=day.day_number,
                    suggested_action="Consolidate schedule to 3-4 key experiences to prevent traveler exhaustion."
                ))

        # -------------------------------------------------------------
        # 3. Geographic Coherence / District Isolation
        # -------------------------------------------------------------
        for day in days:
            districts_in_day: Set[str] = set()
            for act in day.activities:
                if act.district:
                    districts_in_day.add(act.district)

            # Check for incompatible distant district pairs
            for pair_a, pair_b in self.INCOMPATIBLE_DISTRICT_PAIRS:
                if (districts_in_day & pair_a) and (districts_in_day & pair_b):
                    name_a = list(pair_a)[0]
                    name_b = list(pair_b)[0]
                    violations.append(ViolationItem(
                        rule_name="geographic_incoherence",
                        severity="critical",
                        message=(
                            f"Day {day.day_number} combines conflicting distant districts "
                            f"('{name_a}' and '{name_b}'), causing unnecessary cross-city transit."
                        ),
                        affected_day=day.day_number,
                        suggested_action=f"Cluster all activities on Day {day.day_number} within '{day.primary_district}'."
                    ))

            # Check if more than 2 distinct districts are mixed in a single day
            if len(districts_in_day) > 2:
                violations.append(ViolationItem(
                    rule_name="excessive_district_hopping",
                    severity="warning",
                    message=(
                        f"Day {day.day_number} touches {len(districts_in_day)} distinct districts "
                        f"({', '.join(districts_in_day)}). Minimizing district switches improves trip quality."
                    ),
                    affected_day=day.day_number,
                    suggested_action=f"Reassign stops to align with primary district '{day.primary_district}'."
                ))

        # -------------------------------------------------------------
        # 4. Transit Feasibility
        # -------------------------------------------------------------
        for day in days:
            for act in day.activities:
                if act.transit_to_next:
                    t = act.transit_to_next
                    if t.duration_mins > 60:
                        violations.append(ViolationItem(
                            rule_name="transit_feasibility",
                            severity="critical" if t.duration_mins > 75 else "warning",
                            message=(
                                f"Day {day.day_number} transit from '{t.origin}' to '{t.destination}' "
                                f"takes {t.duration_mins} minutes, exceeding acceptable travel time."
                            ),
                            affected_day=day.day_number,
                            suggested_action="Reorder activities geographically or use metered taxi instead of multi-transfer transit."
                        ))

        # -------------------------------------------------------------
        # 5. Duplicate Attractions Check
        # -------------------------------------------------------------
        seen_places: Dict[str, int] = {}
        for day in days:
            for act in day.activities:
                if act.category == "attraction":
                    key = act.place_name.strip().lower()
                    if key in seen_places:
                        violations.append(ViolationItem(
                            rule_name="duplicate_attraction",
                            severity="critical",
                            message=(
                                f"Attraction '{act.place_name}' is scheduled multiple times "
                                f"(Day {seen_places[key]} and Day {day.day_number})."
                            ),
                            affected_day=day.day_number,
                            suggested_action=f"Replace the second visit with another attraction in '{day.primary_district}'."
                        ))
                    else:
                        seen_places[key] = day.day_number

        # -------------------------------------------------------------
        # 6. Thermal Safety & Open-Meteo Climate Check
        # -------------------------------------------------------------
        travel_month = constraints.travel_month
        if travel_month and travel_month in self.SUMMER_MONTHS:
            climate_profile = self.db.get_climate_profile(travel_month)
            avg_high = climate_profile.get("avg_high_c", 41.0) if climate_profile else 41.0

            for day in days:
                for act in day.activities:
                    # Check afternoon outdoor activities
                    if act.time_slot == "afternoon":
                        is_outdoor = self._is_place_outdoor(act)
                        if is_outdoor:
                            violations.append(ViolationItem(
                                rule_name="thermal_safety",
                                severity="critical",
                                message=(
                                    f"Thermal Hazard: '{act.place_name}' is an outdoor activity scheduled "
                                    f"in the afternoon during month {travel_month} (average high: {avg_high}°C). "
                                    f"Direct sun exposure between 11:30 AM and 04:30 PM poses high heatstroke risk."
                                ),
                                affected_day=day.day_number,
                                suggested_action="Move this activity to the evening (after 18:00) or replace with an indoor air-conditioned attraction."
                            ))
                            recommended_swaps.append(
                                f"Reschedule outdoor venue '{act.place_name}' on Day {day.day_number} to evening or swap with an air-conditioned museum/indoor mall."
                            )

        # -------------------------------------------------------------
        # Synthesis: Determine overall pass/fail status
        # -------------------------------------------------------------
        critical_violations = [v for v in violations if v.severity == "critical"]
        passed = len(critical_violations) == 0

        summary_messages = [f"[{v.severity.upper()}] {v.message}" for v in violations]

        audit_notes = (
            "All hard constraints satisfied. Itinerary is geographically coherent, budget-compliant, and thermally safe."
            if passed else
            f"Audit flagged {len(critical_violations)} critical constraint violation(s) requiring revision."
        )

        return ReviewFeedback(
            passed=passed,
            violations=summary_messages,
            structured_violations=violations,
            cost_delta_aed=cost_delta_aed,
            recommended_swaps=recommended_swaps,
            revision_round=revision_round,
            audit_notes=audit_notes
        )

    def _is_place_outdoor(self, activity: ActivitySlot) -> bool:
        """Determines if an activity slot is an outdoor venue."""
        # Query local database for venue details
        place_info = self.db.get_attraction_by_id(activity.place_id)
        if place_info:
            return not bool(place_info.get("is_indoor", 0))

        # Heuristic fallback based on common outdoor venue names
        outdoor_keywords = ["beach", "walk", "promenade", "desert", "safari", "creek", "souk", "park", "garden"]
        p_name = activity.place_name.lower()
        return any(k in p_name for k in outdoor_keywords)
