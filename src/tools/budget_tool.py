"""
Deterministic Budget Calculation, Variance Engine, and Cost-Cutting Swap Tool.
Enforces financial ceilings in AED, identifies deficit causes, and generates
prioritized substitutions when an itinerary exceeds user budget limits.
"""

from typing import List, Dict, Any, Tuple, Optional
from src.models.budget import BudgetBreakdown, CostItem
from src.models.itinerary import DayPlan, ActivitySlot, TransitSegment
from src.data_access.sqlite_client import DubaiSQLiteClient


class BudgetTool:
    """
    Mathematical financial engine utilized by the Budget and Review agents.
    Calculates exact itemized trip expenses and proposes actionable substitutions.
    """

    # Pre-calibrated high-value attraction substitution catalog (Same-district swaps)
    ATTRACTION_SUBSTITUTION_CATALOG = {
        "Burj Khalifa — At The Top (Levels 124 & 125)": {
            "replacement_id": "att_downtown_04",
            "replacement_name": "The Dubai Fountain Show & Souk Al Bahar Boardwalk",
            "replacement_fee_aed": 0.0,
            "savings_aed": 179.0,
            "district": "Downtown & DIFC",
            "rationale": "Experience unobstructed iconic views of Burj Khalifa and the choreographed fountain show completely free."
        },
        "Atlantis Aquaventure Waterpark": {
            "replacement_id": "att_palm_04",
            "replacement_name": "Palm West Beach Boardwalk & Coastal Lagoon",
            "replacement_fee_aed": 0.0,
            "savings_aed": 345.0,
            "district": "Palm Jumeirah & Jumeirah",
            "rationale": "Swap paid waterpark with a scenic, complimentary beach promenade and swim zone overlooking Dubai Marina."
        },
        "Museum of the Future": {
            "replacement_id": "att_downtown_06",
            "replacement_name": "Dubai Frame (Zabeel Park)",
            "replacement_fee_aed": 52.50,
            "savings_aed": 96.50,
            "district": "Downtown & DIFC",
            "rationale": "Visit the world-famous golden Dubai Frame offering panoramic views of both Old and New Dubai at a fraction of the cost."
        },
        "Dubai Desert Conservation Reserve Heritage Drive": {
            "replacement_id": "att_outskirts_04",
            "replacement_name": "Ras Al Khor Wildlife Sanctuary & Flamingo Hide",
            "replacement_fee_aed": 0.0,
            "savings_aed": 220.0,
            "district": "Desert & Outskirts",
            "rationale": "Experience native wildlife and pink flamingos in a protected wetland sanctuary with free public admission."
        },
        "The Lost Chambers Aquarium (Atlantis)": {
            "replacement_id": "att_palm_02",
            "replacement_name": "Souk Madinat Jumeirah Traditional Waterways",
            "replacement_fee_aed": 0.0,
            "savings_aed": 135.0,
            "district": "Palm Jumeirah & Jumeirah",
            "rationale": "Explore authentic Arabesque canal architecture with Burj Al Arab photo viewpoints at zero entrance fee."
        },
        "Ski Dubai Snow Park (Mall of the Emirates)": {
            "replacement_id": "att_marina_03",
            "replacement_name": "Bluewaters Island & Ain Dubai Viewing Plaza",
            "replacement_fee_aed": 0.0,
            "savings_aed": 220.0,
            "district": "Dubai Marina & JBR",
            "rationale": "Enjoy waterfront coastal sightseeing and pedestrian promenade views with zero admission fee."
        }
    }

    # Mapping of database place IDs to catalog keys
    ID_TO_CATALOG_KEY = {
        "att_downtown_01": "Burj Khalifa — At The Top (Levels 124 & 125)",
        "att_palm_05": "Atlantis Aquaventure Waterpark",
        "att_palm_01": "Atlantis Aquaventure Waterpark",
        "att_downtown_02": "Museum of the Future",
        "att_downtown_03": "Museum of the Future",
        "att_outskirts_03": "Dubai Desert Conservation Reserve Heritage Drive",
        "att_outskirts_01": "Dubai Desert Conservation Reserve Heritage Drive",
        "att_palm_06": "The Lost Chambers Aquarium (Atlantis)",
        "att_outskirts_06": "Ski Dubai Snow Park (Mall of the Emirates)",
    }

    def __init__(self, db_client: Optional[DubaiSQLiteClient] = None):
        self.db = db_client or DubaiSQLiteClient()

    def _find_attraction_substitute(self, act: ActivitySlot) -> Optional[Dict[str, Any]]:
        """Resolves the best same-district free/low-cost alternative for a paid attraction."""
        # 1. Exact Name Match
        if act.place_name in self.ATTRACTION_SUBSTITUTION_CATALOG:
            return self.ATTRACTION_SUBSTITUTION_CATALOG[act.place_name]

        # 2. Exact ID Match
        if act.place_id in self.ID_TO_CATALOG_KEY:
            catalog_key = self.ID_TO_CATALOG_KEY[act.place_id]
            return self.ATTRACTION_SUBSTITUTION_CATALOG[catalog_key]

        # 3. Fuzzy Keyword Match
        p_lower = act.place_name.lower()
        for cat_name, sub in self.ATTRACTION_SUBSTITUTION_CATALOG.items():
            for term in ["burj khalifa", "aquaventure", "museum of the future", "desert conservation", "lost chambers", "ski dubai"]:
                if term in p_lower and term in cat_name.lower():
                    return sub

        # 4. Dynamic Same-District Free Attraction from SQLite
        if act.cost_aed >= 80.0:
            free_candidates = self.db.get_attractions(district=act.district, max_fee=0.0)
            for cand in free_candidates:
                if cand["id"] != act.place_id:
                    return {
                        "replacement_id": cand["id"],
                        "replacement_name": cand["name"],
                        "replacement_fee_aed": 0.0,
                        "savings_aed": round(act.cost_aed, 2),
                        "district": act.district,
                        "rationale": f"Complimentary cultural/scenic landmark in {act.district} with zero admission fee."
                    }
        return None

    def calculate_itinerary_budget(
        self,
        days: List[DayPlan],
        hotel_district: str,
        hotel_tier: str,
        duration_days: int,
        budget_limit_aed: float
    ) -> BudgetBreakdown:
        """
        Calculates itemized costs across accommodation, dining, attractions, and transit in AED.
        """
        records: List[CostItem] = []

        # 1. Accommodation Expenses: (duration - 1) nights, or 1 night minimum for 1-day trips
        nights = max(1, duration_days - 1) if duration_days > 1 else 1
        nightly_rate = self.db.get_hotel_rate(hotel_district, hotel_tier)
        accommodation_total = round(nights * nightly_rate, 2)
        records.append(CostItem(
            category="accommodation",
            item_name=f"{hotel_tier.capitalize()} Hotel in {hotel_district} ({nights} night{'s' if nights > 1 else ''})",
            cost_aed=accommodation_total,
            is_estimated=True,
            notes=f"Calculated at AED {nightly_rate:.2f} per night"
        ))

        # 2. Activity & Dining Expenses from Day Plans
        dining_total = 0.0
        attractions_total = 0.0
        transit_total = 0.0

        for day in days:
            for act in day.activities:
                cost = round(act.cost_aed, 2)
                if act.category == "dining":
                    dining_total += cost
                    records.append(CostItem(
                        category="dining",
                        item_name=act.place_name,
                        cost_aed=cost,
                        day_number=day.day_number
                    ))
                elif act.category in ["attraction", "leisure"]:
                    attractions_total += cost
                    records.append(CostItem(
                        category="attraction",
                        item_name=act.place_name,
                        cost_aed=cost,
                        day_number=day.day_number
                    ))

                # Transit step attached to activity
                if act.transit_to_next and act.transit_to_next.fare_aed > 0:
                    t_cost = round(act.transit_to_next.fare_aed, 2)
                    transit_total += t_cost
                    records.append(CostItem(
                        category="transit",
                        item_name=f"{act.transit_to_next.mode.capitalize()}: {act.transit_to_next.origin} -> {act.transit_to_next.destination}",
                        cost_aed=t_cost,
                        day_number=day.day_number,
                        notes=act.transit_to_next.notes
                    ))

        return BudgetBreakdown.calculate(
            accommodation=accommodation_total,
            dining=round(dining_total, 2),
            attractions=round(attractions_total, 2),
            transit=round(transit_total, 2),
            budget_limit=round(budget_limit_aed, 2),
            records=records
        )

    def generate_cost_cutting_swaps(
        self,
        days: List[DayPlan],
        current_breakdown: BudgetBreakdown,
        hotel_district: str,
        hotel_tier: str,
        duration_days: int
    ) -> List[Dict[str, Any]]:
        """
        When the itinerary is over budget (cost_delta_aed > 0), generates a prioritized list
        of concrete, high-impact substitutions to bring expenses within limits.
        """
        deficit = abs(current_breakdown.remaining_balance_aed)
        swaps: List[Dict[str, Any]] = []

        # ------------------------------------------------------------------
        # Strategy 1: Replace Expensive Metered Taxis with Dubai Metro
        # ------------------------------------------------------------------
        for day in days:
            for act in day.activities:
                if act.transit_to_next and act.transit_to_next.mode == "taxi" and act.transit_to_next.fare_aed > 15.0:
                    old_fare = act.transit_to_next.fare_aed
                    new_fare = 5.0  # Typical Metro Silver Nol fare
                    savings = round(old_fare - new_fare, 2)
                    swaps.append({
                        "type": "transit_swap",
                        "day_number": day.day_number,
                        "description": f"Switch transit from Taxi (AED {old_fare:.2f}) to Dubai Metro (AED {new_fare:.2f}) for journey to {act.transit_to_next.destination}",
                        "savings_aed": savings,
                        "action": {
                            "category": "transit",
                            "day_number": day.day_number,
                            "place_id": act.place_id,
                            "new_mode": "metro",
                            "new_fare": new_fare
                        }
                    })

        # ------------------------------------------------------------------
        # Strategy 2: High-Fee Attraction Replacements in Same District
        # ------------------------------------------------------------------
        for day in days:
            for act in day.activities:
                if act.category == "attraction":
                    sub_info = self._find_attraction_substitute(act)
                    if sub_info:
                        swaps.append({
                            "type": "attraction_swap",
                            "day_number": day.day_number,
                            "description": f"Replace '{act.place_name}' (AED {act.cost_aed:.2f}) with '{sub_info['replacement_name']}' (AED {sub_info['replacement_fee_aed']:.2f})",
                            "savings_aed": sub_info["savings_aed"],
                            "rationale": sub_info["rationale"],
                            "action": {
                                "category": "attraction",
                                "day_number": day.day_number,
                                "old_place_id": act.place_id,
                                "old_name": act.place_name,
                                "new_place_id": sub_info["replacement_id"],
                                "new_name": sub_info["replacement_name"],
                                "new_cost": sub_info["replacement_fee_aed"],
                                "district": sub_info["district"]
                            }
                        })

        # ------------------------------------------------------------------
        # Strategy 3: Dining Tier Downgrade (e.g. Fine dining to Midscale/Street food)
        # ------------------------------------------------------------------
        for day in days:
            for act in day.activities:
                if act.category == "dining" and act.cost_aed > 150.0:
                    savings = round(act.cost_aed - 75.0, 2)
                    swaps.append({
                        "type": "dining_swap",
                        "day_number": day.day_number,
                        "description": f"Adjust dining from upscale venue '{act.place_name}' (AED {act.cost_aed:.2f}) to a midscale authentic cafe (AED 75.00)",
                        "savings_aed": savings,
                        "action": {
                            "category": "dining",
                            "day_number": day.day_number,
                            "place_id": act.place_id,
                            "new_cost": 75.0
                        }
                    })

        # ------------------------------------------------------------------
        # Strategy 4: Hotel District / Tier Downgrade
        # ------------------------------------------------------------------
        if hotel_tier.lower() != "budget" or hotel_district != "Old Dubai & Creek":
            nights = max(1, duration_days - 1)
            old_nightly = self.db.get_hotel_rate(hotel_district, hotel_tier)
            budget_nightly = self.db.get_hotel_rate("Old Dubai & Creek", "budget")
            if old_nightly > budget_nightly:
                hotel_savings = round((old_nightly - budget_nightly) * nights, 2)
                swaps.append({
                    "type": "hotel_swap",
                    "day_number": 0,
                    "description": f"Switch hotel from {hotel_tier.capitalize()} in {hotel_district} (AED {old_nightly}/night) to Budget in Old Dubai / Deira (AED {budget_nightly}/night)",
                    "savings_aed": hotel_savings,
                    "action": {
                        "category": "hotel",
                        "new_district": "Old Dubai & Creek",
                        "new_tier": "budget"
                    }
                })

        # Sort swaps by savings descending
        swaps.sort(key=lambda s: s.get("savings_aed", 0.0), reverse=True)
        return swaps

    @staticmethod
    def apply_swap_to_itinerary(days: List[DayPlan], swap: Dict[str, Any]) -> Tuple[List[DayPlan], bool]:
        """
        Executes a swap directive on the day plans and returns (modified_days, was_applied).
        """
        action = swap.get("action", {})
        category = action.get("category")
        day_num = action.get("day_number")

        applied = False
        for day in days:
            if day_num and day.day_number != day_num:
                continue

            for act in day.activities:
                if category == "attraction" and (act.place_id == action.get("old_place_id") or act.place_name == action.get("old_name")):
                    act.place_id = action.get("new_place_id", act.place_id)
                    act.place_name = action.get("new_name", act.place_name)
                    act.cost_aed = action.get("new_cost", 0.0)
                    applied = True
                    break
                elif category == "dining" and act.place_id == action.get("place_id"):
                    act.cost_aed = action.get("new_cost", act.cost_aed)
                    applied = True
                    break
                elif category == "transit" and act.place_id == action.get("place_id"):
                    if act.transit_to_next:
                        act.transit_to_next.mode = action.get("new_mode", act.transit_to_next.mode)
                        act.transit_to_next.fare_aed = action.get("new_fare", act.transit_to_next.fare_aed)
                        act.transit_to_next.notes = "Replaced with Dubai Metro to optimize budget"
                        applied = True
                        break

        # Recalculate daily spend
        for day in days:
            day.daily_spend_aed = round(sum(a.cost_aed + (a.transit_to_next.fare_aed if a.transit_to_next else 0.0) for a in day.activities), 2)

        return days, applied
