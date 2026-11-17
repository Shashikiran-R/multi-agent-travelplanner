"""
Destination Research Agent: Dubai Concierge & Cultural Discovery Specialist powered by Groq
(with deterministic offline fallback).
Zero paid APIs ($0.00 cost).
"""

from typing import Dict, Any, List, Optional
from src.models.request import UserConstraints
from src.tools.places_tool import PlacesTool
from src.data_access.sqlite_client import DubaiSQLiteClient
from src.utils.llm_factory import get_groq_llm, extract_text_content


class DestinationAgent:
    """
    Dubai Local Concierge & Cultural Specialist.
    Researches verified local venues, applies summer climate adaptations,
    and curates candidate attractions and dining options using Groq
    (with deterministic offline fallback).
    """

    SUMMER_MONTHS = {6, 7, 8, 9}  # June, July, August, September

    def __init__(
        self,
        places_tool: Optional[PlacesTool] = None,
        db_client: Optional[DubaiSQLiteClient] = None,
        llm: Optional[Any] = None
    ):
        self.db = db_client or DubaiSQLiteClient()
        self.places_tool = places_tool or PlacesTool(db_client=self.db)
        self.llm = llm if llm is not None else get_groq_llm(temperature=0.3)

    def research_destinations(
        self,
        constraints: UserConstraints,
        target_districts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Gathers candidate attractions and restaurants matching user preferences and climate.
        Enriches candidate findings with Groq-powered concierge notes when available.
        """
        # If target districts not provided, use all available districts
        all_districts = target_districts or self.db.get_all_districts()
        is_summer = constraints.travel_month in self.SUMMER_MONTHS if constraints.travel_month else False

        candidate_attractions: List[Dict[str, Any]] = []
        candidate_restaurants: List[Dict[str, Any]] = []

        # Map price tier
        price_tier = constraints.accommodation_tier

        # Query candidates for each target district
        for dist in all_districts:
            # 1. Attractions Search
            # For summer, retrieve indoor attractions first
            if is_summer:
                indoor_places = self.places_tool.search_attractions(
                    district=dist,
                    interests=constraints.interests,
                    is_indoor=True,
                    avoid_crowds=constraints.avoid_crowds,
                    limit=4
                )
                candidate_attractions.extend(indoor_places)

            # Retrieve general attractions for cooler morning/evening slots
            general_places = self.places_tool.search_attractions(
                district=dist,
                interests=constraints.interests,
                avoid_crowds=constraints.avoid_crowds,
                limit=6
            )
            for p in general_places:
                if not any(existing["id"] == p["id"] for existing in candidate_attractions):
                    candidate_attractions.append(p)

            # 2. Restaurants Search matching user tier
            restaurants = self.places_tool.search_restaurants(
                district=dist,
                price_tier=price_tier,
                limit=4
            )
            # If fewer than 2 results for that tier, fallback to midscale or any tier
            if len(restaurants) < 2 and price_tier != "midscale":
                restaurants.extend(self.places_tool.search_restaurants(
                    district=dist,
                    price_tier="midscale",
                    limit=2
                ))
            candidate_restaurants.extend(restaurants)

        # Climate advisory notes if summer
        climate_advisory = None
        if is_summer:
            profile = self.db.get_climate_profile(constraints.travel_month)
            avg_high = profile.get("avg_high_c", 41.3) if profile else 41.3
            climate_advisory = (
                f"Summer Season Advisory (Month {constraints.travel_month}): Average high temperatures reach {avg_high}°C. "
                f"Afternoon activities (11:30 AM to 04:30 PM) have been filtered to prioritize air-conditioned indoor venues "
                f"(e.g., Museum of the Future, Dubai Mall, Green Planet, Ski Dubai)."
            )

        # Generate concierge highlights via Groq if available
        concierge_notes = self._generate_concierge_notes(
            candidate_attractions=candidate_attractions,
            candidate_restaurants=candidate_restaurants,
            constraints=constraints,
            is_summer=is_summer
        )

        return {
            "candidate_attractions": candidate_attractions,
            "candidate_restaurants": candidate_restaurants,
            "total_attractions_found": len(candidate_attractions),
            "total_restaurants_found": len(candidate_restaurants),
            "is_summer_adapted": is_summer,
            "climate_advisory": climate_advisory,
            "concierge_notes": concierge_notes
        }

    def _generate_concierge_notes(
        self,
        candidate_attractions: List[Dict[str, Any]],
        candidate_restaurants: List[Dict[str, Any]],
        constraints: UserConstraints,
        is_summer: bool
    ) -> str:
        """
        Uses Groq (openai/gpt-oss-120b) to generate local insider concierge highlights
        (signature dishes, cultural etiquette, timing advice).
        """
        if not self.llm:
            return (
                f"Curated {len(candidate_attractions)} attractions and {len(candidate_restaurants)} dining venues "
                f"matching traveler interests ({', '.join(constraints.interests)}) across Dubai's core districts."
            )

        try:
            sample_att = [a["name"] for a in candidate_attractions[:6]]
            sample_rest = [f"{r['name']} ({r.get('cuisine', 'Local')})" for r in candidate_restaurants[:6]]

            system_prompt = (
                "You are an elite Dubai concierge specialist. Based on the selected candidate attractions "
                "and authentic dining venues from our verified Dubai catalog, provide concise local insider advice "
                "in 3 brief bullet points (covering highlight activities, signature dishes to order, and cultural/timing tips)."
            )
            user_content = (
                f"Traveler Interests: {constraints.interests}\n"
                f"Accommodation/Dining Tier: {constraints.accommodation_tier}\n"
                f"Travel Month: {constraints.travel_month or 'Winter/Standard'}\n"
                f"Summer Season: {'Yes (Prioritizing indoor venues during heat)' if is_summer else 'No'}\n"
                f"Selected Attractions: {', '.join(sample_att)}\n"
                f"Selected Restaurants: {', '.join(sample_rest)}"
            )
            response = self.llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ])
            content = extract_text_content(response)
            if content and len(content) > 20:
                return content
        except Exception as e:
            print(f"⚠️ Groq destination curation notice: {e}. Utilizing fallback summary.")

        return (
            f"Curated {len(candidate_attractions)} attractions and {len(candidate_restaurants)} dining venues "
            f"matching traveler interests ({', '.join(constraints.interests)}) across Dubai's core districts."
        )
