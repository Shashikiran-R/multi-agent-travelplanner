"""
Pydantic V2 Schemas for Complete Itinerary, Day Plans, and Activities.
Models the final output contract presented to the traveler.
"""

from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field

from src.models.request import UserConstraints
from src.models.budget import BudgetBreakdown
from src.models.review import ReviewFeedback


class AttractionItem(BaseModel):
    """
    Normalized attraction representation.
    """
    id: str
    name: str
    category: str
    district: str
    lat: float
    lng: float
    admission_fee_aed: float = Field(default=0.0, ge=0.0)
    recommended_duration_mins: int = Field(default=90, gt=0)
    crowd_level: Literal["low", "medium", "high"] = "medium"
    is_indoor: bool = False
    opening_hours: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    description: str = ""


class RestaurantItem(BaseModel):
    """
    Dining venue representation.
    """
    id: str
    name: str
    cuisine: str
    district: str
    price_tier: Literal["budget", "midscale", "luxury"]
    avg_cost_aed: float = Field(..., gt=0.0)
    lat: float
    lng: float
    tags: List[str] = Field(default_factory=list)


class TransitSegment(BaseModel):
    """
    Transit step connecting two consecutive activity locations.
    """
    origin: str
    destination: str
    mode: Literal["metro", "taxi", "bus", "walk"]
    duration_mins: int = Field(..., ge=0)
    fare_aed: float = Field(default=0.0, ge=0.0)
    distance_km: Optional[float] = None
    notes: Optional[str] = None


class ActivitySlot(BaseModel):
    """
    Scheduled activity slot in a day's itinerary.
    """
    time_slot: Literal["morning", "afternoon", "evening"]
    place_id: str
    place_name: str
    category: Literal["attraction", "dining", "leisure", "transit"]
    duration_mins: int = Field(..., gt=0)
    cost_aed: float = Field(default=0.0, ge=0.0)
    district: str
    lat: float
    lng: float
    dwell_time_label: Optional[str] = None
    transit_to_next: Optional[TransitSegment] = None


class DayPlan(BaseModel):
    """
    Complete single-day itinerary plan.
    """
    day_number: int = Field(..., ge=1, le=7)
    date_label: Optional[str] = None
    primary_district: str
    theme: str
    activities: List[ActivitySlot] = Field(default_factory=list)
    daily_spend_aed: float = Field(default=0.0, ge=0.0)
    hotel_area: str = Field(..., description="Recommended base hotel neighborhood for this night")
    transit_summary: Optional[str] = None


class TripItinerary(BaseModel):
    """
    The top-level comprehensive multi-day itinerary object returned by the LangGraph engine.
    """
    trip_id: str
    title: str
    summary: str
    constraints: UserConstraints
    days: List[DayPlan]
    budget: BudgetBreakdown
    review: ReviewFeedback
    created_at: Optional[str] = None
    data_sources_used: List[str] = Field(
        default_factory=lambda: ["Local Curated SQLite ($0.00)", "OpenStreetMap Overpass", "Dubai RTA Math Engine", "Open-Meteo"]
    )
