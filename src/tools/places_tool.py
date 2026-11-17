"""
Places Search, Geographical District Clustering, and Venue Discovery Tool.
Interacts with the local SQLite repository to filter attractions and dining spots
by user preferences, crowd avoidance, and geographic coherence.
"""

from typing import List, Dict, Any, Optional
from src.data_access.sqlite_client import DubaiSQLiteClient


class PlacesTool:
    """
    Domain tool used by the Destination and Logistics agents to query verified Dubai places,
    cluster venues geographically, and recommend daily district sequences.
    """

    def __init__(self, db_client: Optional[DubaiSQLiteClient] = None):
        self.db = db_client or DubaiSQLiteClient()

    def search_attractions(
        self,
        district: Optional[str] = None,
        interests: Optional[List[str]] = None,
        max_fee: Optional[float] = None,
        is_indoor: Optional[bool] = None,
        avoid_crowds: bool = False,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieves matching attractions filtered by district, interest tags, fee limit,
        and indoor/crowd preferences.
        """
        all_matches = self.db.get_attractions(
            district=district,
            interest_tags=interests,
            max_fee=max_fee,
            is_indoor=is_indoor
        )

        if avoid_crowds:
            # Sort low and medium crowd places first
            crowd_rank = {"low": 1, "medium": 2, "high": 3}
            all_matches.sort(key=lambda x: crowd_rank.get(x.get("crowd_level", "medium"), 2))

        return all_matches[:limit]

    def search_restaurants(
        self,
        district: Optional[str] = None,
        price_tier: Optional[str] = None,
        cuisine: Optional[str] = None,
        max_cost: Optional[float] = None,
        limit: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Retrieves matching restaurants filtered by district, price tier, cuisine, and cost.
        """
        results = self.db.get_restaurants(
            district=district,
            price_tier=price_tier,
            cuisine=cuisine,
            max_cost=max_cost
        )
        return results[:limit]

    def get_place_by_id(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Finds a venue by unique ID."""
        return self.db.get_attraction_by_id(place_id)

    def get_indoor_attractions(
        self,
        district: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieves verified indoor air-conditioned attractions, ideal for summer afternoons
        when outdoor temperatures exceed 41°C.
        """
        return self.search_attractions(district=district, is_indoor=True, limit=limit)

    def get_free_attractions(
        self,
        district: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-rated attractions with zero admission fee (e.g. souks, public fountains,
        free heritage neighborhoods, public beaches).
        """
        return self.search_attractions(district=district, max_fee=0.0, limit=limit)

    def get_district_summary(self) -> Dict[str, Dict[str, int]]:
        """
        Returns a breakdown of attraction and dining venues available in each of the
        5 official Dubai tourism districts.
        """
        all_attractions = self.db.get_attractions()
        all_restaurants = self.db.get_restaurants()
        
        summary: Dict[str, Dict[str, int]] = {}
        for a in all_attractions:
            dist = a.get("district", "Downtown & DIFC")
            if dist not in summary:
                summary[dist] = {"attractions": 0, "restaurants": 0}
            summary[dist]["attractions"] += 1
            
        for r in all_restaurants:
            dist = r.get("district", "Downtown & DIFC")
            if dist not in summary:
                summary[dist] = {"attractions": 0, "restaurants": 0}
            summary[dist]["restaurants"] += 1
            
        return summary

    @staticmethod
    def cluster_places_by_district(places: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Groups a list of places into geographical district buckets to avoid cross-city commutes.
        """
        clusters: Dict[str, List[Dict[str, Any]]] = {}
        for p in places:
            dist = p.get("district", "Downtown & DIFC")
            if dist not in clusters:
                clusters[dist] = []
            clusters[dist].append(p)
        return clusters

    @staticmethod
    def recommend_district_sequence(duration_days: int, interests: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """
        Generates an optimized day-by-day district assignment and thematic focus
        based on total trip duration and traveler interests.
        """
        interests = [i.lower() for i in (interests or [])]
        is_beach_first = "beach" in interests and "culture" not in interests

        # District sequence templates tailored for 1 to 7 days
        all_templates = [
            {
                "day_number": 1,
                "primary_district": "Old Dubai & Creek",
                "theme": "Historic Creekside Culture, Traditional Souks & Heritage",
                "suggested_hotel_area": "Deira & Bur Dubai"
            },
            {
                "day_number": 2,
                "primary_district": "Downtown & DIFC",
                "theme": "Futuristic Architecture, Iconic Skylines & Modern Wonders",
                "suggested_hotel_area": "Downtown & Business Bay"
            },
            {
                "day_number": 3,
                "primary_district": "Dubai Marina & JBR",
                "theme": "Coastal Seaside Promenade, JBR Sands & Bluewaters Island",
                "suggested_hotel_area": "Dubai Marina & JBR"
            },
            {
                "day_number": 4,
                "primary_district": "Palm Jumeirah & Jumeirah",
                "theme": "Island Panoramas, Madinat Waterways & Beachfront Vistas",
                "suggested_hotel_area": "Palm Jumeirah & Jumeirah"
            },
            {
                "day_number": 5,
                "primary_district": "Desert & Outskirts",
                "theme": "Arabian Desert Conservation, Golden Dunes & Wildlife",
                "suggested_hotel_area": "Downtown & Business Bay"
            },
            {
                "day_number": 6,
                "primary_district": "Downtown & DIFC",
                "theme": "Art, Contemporary Innovation & World-Class Dining",
                "suggested_hotel_area": "Downtown & Business Bay"
            },
            {
                "day_number": 7,
                "primary_district": "Old Dubai & Creek",
                "theme": "Cultural Immersion, Hidden Museums & Farewell Abra Voyage",
                "suggested_hotel_area": "Deira & Bur Dubai"
            }
        ]

        if is_beach_first:
            # Swap days 1 and 3 so coastal areas are experienced first
            all_templates[0], all_templates[2] = all_templates[2], all_templates[0]
            all_templates[0]["day_number"] = 1
            all_templates[2]["day_number"] = 3

        return all_templates[:duration_days]

    def recommend_base_hotel_area(self, primary_districts: List[str], accommodation_tier: str) -> str:
        """
        Identifies the single most practical base lodging neighborhood to minimize overall
        commute times and match the user's budget tier.
        """
        tier = accommodation_tier.lower()
        if tier == "budget":
            # Deira / Bur Dubai or Al Barsha provide highest density of budget hotels near Metro
            return "Old Dubai & Creek" if "Old Dubai & Creek" in primary_districts else "Downtown & DIFC"
        elif tier == "luxury":
            return "Dubai Marina & JBR" if "Dubai Marina & JBR" in primary_districts else "Downtown & DIFC"
        else:
            # Midscale: Downtown/Business Bay offers central location for all districts
            return "Downtown & DIFC"
