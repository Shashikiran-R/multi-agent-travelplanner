"""
Logistics Agent: Geographical Clustering, Daily Sequencing, and Transit Routing Planner powered by Groq
(with deterministic offline fallback).
Structures candidate places into coherent single-district daily itineraries with
deterministic Dubai RTA transit steps and base hotel assignment.
Zero paid APIs ($0.00 cost).
"""

from typing import Dict, Any, List, Optional, Tuple
from src.models.request import UserConstraints
from src.models.itinerary import DayPlan, ActivitySlot, TransitSegment
from src.tools.routing_tool import RTATransitEngine
from src.tools.places_tool import PlacesTool
from src.data_access.sqlite_client import DubaiSQLiteClient
from src.utils.llm_factory import get_groq_llm, extract_text_content


class LogisticsAgent:
    """
    Urban Transit Planner & Geographical Optimization Specialist.
    1. Partitions trip duration across Dubai's 5 official tourism districts.
    2. Selects strategic base hotel neighborhood to minimize commutes.
    3. Formulates chronological day plans (morning -> afternoon -> evening).
    4. Calculates deterministic RTA transit connections (Nol, DTC Taxi, Abra, Walking).
    5. Enhances daily themes and transit briefings via Groq (with deterministic fallback).
    """

    SUMMER_MONTHS = {6, 7, 8, 9}

    def __init__(
        self,
        places_tool: Optional[PlacesTool] = None,
        db_client: Optional[DubaiSQLiteClient] = None,
        llm: Optional[Any] = None
    ):
        self.db = db_client or DubaiSQLiteClient()
        self.places_tool = places_tool or PlacesTool(db_client=self.db)
        self.llm = llm if llm is not None else get_groq_llm(temperature=0.2)

    def plan_itinerary_logistics(
        self,
        constraints: UserConstraints,
        candidate_attractions: List[Dict[str, Any]],
        candidate_restaurants: List[Dict[str, Any]]
    ) -> Tuple[List[DayPlan], str]:
        """
        Builds the complete multi-day schedule from candidate places and constraints.
        Returns (days, recommended_hotel_area).
        """
        duration = constraints.trip_duration_days
        is_summer = constraints.travel_month in self.SUMMER_MONTHS if constraints.travel_month else False

        # 1. Generate district sequence templates for 1 to 7 days
        templates = self.places_tool.recommend_district_sequence(
            duration_days=duration,
            interests=constraints.interests
        )
        primary_districts = [t["primary_district"] for t in templates]

        # 2. Select optimal base hotel area
        base_hotel_area = self.places_tool.recommend_base_hotel_area(
            primary_districts=primary_districts,
            accommodation_tier=constraints.accommodation_tier
        )

        # 3. Cluster candidates by district
        attractions_by_dist = self.places_tool.cluster_places_by_district(candidate_attractions)
        restaurants_by_dist = self.places_tool.cluster_places_by_district(candidate_restaurants)

        # Track scheduled venue IDs across days to prevent duplicate visits
        scheduled_attraction_ids = set()
        day_plans: List[DayPlan] = []

        for template in templates:
            day_num = template["day_number"]
            district = template["primary_district"]
            theme = template["theme"]

            # Available attractions for this district
            available_attractions = [
                a for a in attractions_by_dist.get(district, [])
                if a["id"] not in scheduled_attraction_ids
            ]
            # Fallback if candidates were insufficient
            if len(available_attractions) < 2:
                db_more = self.db.get_attractions(district=district, limit=6)
                for a in db_more:
                    if a["id"] not in scheduled_attraction_ids and not any(x["id"] == a["id"] for x in available_attractions):
                        available_attractions.append(a)

            # Available restaurants for this district
            dist_restaurants = restaurants_by_dist.get(district, [])
            if not dist_restaurants:
                dist_restaurants = self.db.get_restaurants(district=district, limit=4)

            # Build activities for this day
            activities = self._build_daily_activities(
                day_num=day_num,
                district=district,
                attractions=available_attractions,
                restaurants=dist_restaurants,
                is_summer=is_summer,
                pacing=constraints.pacing_preference,
                scheduled_ids=scheduled_attraction_ids
            )

            # Calculate deterministic transit between consecutive activities
            activities = self._attach_transit_segments(activities, district, constraints.accommodation_tier)

            # Calculate daily total spend
            daily_spend = round(sum(
                a.cost_aed + (a.transit_to_next.fare_aed if a.transit_to_next else 0.0)
                for a in activities
            ), 2)

            day_plan = DayPlan(
                day_number=day_num,
                primary_district=district,
                theme=theme,
                hotel_area=base_hotel_area,
                activities=activities,
                daily_spend_aed=daily_spend
            )
            day_plans.append(day_plan)

        # Optionally refine day themes with Groq if available
        if self.llm:
            for dp in day_plans:
                refined = self._refine_theme_with_groq(dp, constraints)
                if refined:
                    dp.theme = refined

        return day_plans, base_hotel_area

    def _refine_theme_with_groq(self, day_plan: DayPlan, constraints: UserConstraints) -> Optional[str]:
        """Uses Groq to create an evocative, customized day theme reflecting the scheduled venues."""
        if not self.llm:
            return None
        try:
            places = [a.place_name for a in day_plan.activities]
            prompt = (
                f"Provide a 3-5 word evocative title theme for Day {day_plan.day_number} in {day_plan.primary_district} "
                f"visiting: {', '.join(places)}. Output ONLY the title, no extra text."
            )
            resp = self.llm.invoke([{"role": "user", "content": prompt}])
            content = extract_text_content(resp)
            clean = content.strip().strip('"').strip("'").strip("*")
            if 3 <= len(clean) <= 50:
                return clean
        except Exception:
            return None
        return None

    def generate_logistics_briefing(
        self,
        days: List[DayPlan],
        hotel_area: str,
        constraints: UserConstraints
    ) -> str:
        """
        Uses Groq (openai/gpt-oss-120b) to formulate an urban logistics and transit briefing
        explaining station connections, Nol card guidelines, and walking segments.
        """
        if not self.llm:
            total_transits = sum(1 for d in days for a in d.activities if a.transit_to_next)
            return (
                f"Base Hotel Neighborhood: {hotel_area}. "
                f"Planned {len(days)} single-district daily itineraries with {total_transits} "
                f"optimized RTA transit connections minimizing cross-city transfers."
            )

        try:
            day_summaries = []
            for d in days:
                acts = " -> ".join(a.place_name for a in d.activities)
                day_summaries.append(f"Day {d.day_number} ({d.primary_district}): {acts}")

            system_prompt = (
                "You are a Dubai urban mobility and transit planner. Provide a concise 2-sentence logistics briefing "
                "explaining the transit strategy (base lodging neighborhood, Nol metro / DTC taxi usage, and geographical grouping)."
            )
            user_content = (
                f"Base Hotel District: {hotel_area}\n"
                f"Accommodation/Transit Tier: {constraints.accommodation_tier}\n"
                f"Daily Routes:\n" + "\n".join(day_summaries)
            )
            response = self.llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ])
            content = extract_text_content(response)
            if content and len(content) > 20:
                return content
        except Exception as e:
            print(f"⚠️ Groq logistics briefing notice: {e}. Utilizing fallback summary.")

        return (
            f"Base Hotel Neighborhood: {hotel_area}. "
            f"Planned {len(days)} single-district daily itineraries minimizing cross-city travel times."
        )

    def _build_daily_activities(
        self,
        day_num: int,
        district: str,
        attractions: List[Dict[str, Any]],
        restaurants: List[Dict[str, Any]],
        is_summer: bool,
        pacing: str,
        scheduled_ids: set
    ) -> List[ActivitySlot]:
        """Constructs 3 to 4 sequential time slots for a single day."""
        slots: List[ActivitySlot] = []

        # -------------------------------------------------------------
        # Slot 1: Morning (09:30 AM) - Cultural/Iconic Sightseeing
        # -------------------------------------------------------------
        # In summer, if outdoor attraction exists, put it in the cool morning
        morning_att = None
        if is_summer:
            outdoor_candidates = [a for a in attractions if not a.get("is_indoor", False)]
            morning_att = outdoor_candidates[0] if outdoor_candidates else (attractions[0] if attractions else None)
        else:
            morning_att = attractions[0] if attractions else None

        if morning_att:
            scheduled_ids.add(morning_att["id"])
            attractions.remove(morning_att)
            slots.append(ActivitySlot(
                time_slot="morning",
                place_id=morning_att["id"],
                place_name=morning_att["name"],
                category="attraction",
                duration_mins=morning_att.get("recommended_duration_mins", 90),
                cost_aed=float(morning_att.get("admission_fee_aed", 0.0)),
                district=morning_att.get("district", district),
                lat=morning_att["lat"],
                lng=morning_att["lng"]
            ))

        # -------------------------------------------------------------
        # Slot 2: Afternoon (12:30 PM - 04:00 PM) - Lunch + Indoor Attraction
        # -------------------------------------------------------------
        # Dining venue
        if restaurants:
            lunch = restaurants[0]
            slots.append(ActivitySlot(
                time_slot="afternoon",
                place_id=lunch["id"],
                place_name=lunch["name"],
                category="dining",
                duration_mins=75,
                cost_aed=float(lunch.get("avg_cost_aed", 45.0)),
                district=lunch.get("district", district),
                lat=lunch["lat"],
                lng=lunch["lng"]
            ))

        # Afternoon Attraction (Enforce indoor during summer)
        afternoon_att = None
        if is_summer:
            indoor_candidates = [a for a in attractions if a.get("is_indoor", False)]
            if indoor_candidates:
                afternoon_att = indoor_candidates[0]
            else:
                # Query SQLite directly for verified indoor landmark in this district
                indoor_db = self.db.get_attractions(district=district, is_indoor=True, limit=3)
                for ind in indoor_db:
                    if ind["id"] not in scheduled_ids:
                        afternoon_att = ind
                        break
        else:
            afternoon_att = attractions[0] if attractions else None

        if afternoon_att and len(slots) < (3 if pacing == "relaxed" else 4):
            scheduled_ids.add(afternoon_att["id"])
            if afternoon_att in attractions:
                attractions.remove(afternoon_att)
            slots.append(ActivitySlot(
                time_slot="afternoon",
                place_id=afternoon_att["id"],
                place_name=afternoon_att["name"],
                category="attraction",
                duration_mins=afternoon_att.get("recommended_duration_mins", 90),
                cost_aed=float(afternoon_att.get("admission_fee_aed", 0.0)),
                district=afternoon_att.get("district", district),
                lat=afternoon_att["lat"],
                lng=afternoon_att["lng"]
            ))

        # -------------------------------------------------------------
        # Slot 3: Evening (06:00 PM - 09:00 PM) - Sunset / Waterfront / Evening Walk
        # -------------------------------------------------------------
        max_allowed = 3 if pacing == "relaxed" else 4
        if len(slots) < max_allowed and attractions:
            evening_att = attractions[0]
            scheduled_ids.add(evening_att["id"])
            slots.append(ActivitySlot(
                time_slot="evening",
                place_id=evening_att["id"],
                place_name=evening_att["name"],
                category="attraction",
                duration_mins=evening_att.get("recommended_duration_mins", 90),
                cost_aed=float(evening_att.get("admission_fee_aed", 0.0)),
                district=evening_att.get("district", district),
                lat=evening_att["lat"],
                lng=evening_att["lng"]
            ))

        return slots

    def _attach_transit_segments(
        self,
        activities: List[ActivitySlot],
        district: str,
        tier: str
    ) -> List[ActivitySlot]:
        """Calculates and attaches deterministic RTA transit segments between consecutive stops."""
        for i in range(len(activities) - 1):
            curr = activities[i]
            nxt = activities[i + 1]

            preferred_mode = "taxi" if tier == "luxury" else "metro"
            transit_seg = RTATransitEngine.build_transit_segment(
                origin_name=curr.place_name,
                dest_name=nxt.place_name,
                origin_lat=curr.lat,
                origin_lng=curr.lng,
                dest_lat=nxt.lat,
                dest_lng=nxt.lng,
                origin_district=curr.district,
                dest_district=nxt.district,
                preferred_mode=preferred_mode
            )
            curr.transit_to_next = transit_seg

        return activities
