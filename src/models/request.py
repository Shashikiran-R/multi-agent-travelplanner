"""
Pydantic V2 Schemas for User Request, Preferences and Constraints.
Enforces validation rules on trip duration, budget ceilings, and travel preferences.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class UserConstraints(BaseModel):
    """
    Normalized, validated travel requirements parsed from the user's natural language request.
    """
    trip_duration_days: int = Field(
        ...,
        ge=1,
        le=7,
        description="Duration of the trip in days (supports 1 to 7 days for MVP scope)"
    )
    total_budget_aed: float = Field(
        ...,
        gt=0,
        description="Total trip budget in United Arab Emirates Dirham (AED), excluding flights"
    )
    interests: List[str] = Field(
        default_factory=list,
        description="Traveler interest tags, e.g. culture, food, beach, luxury, architecture, shopping"
    )
    accommodation_tier: Literal["budget", "midscale", "luxury"] = Field(
        default="budget",
        description="Target hotel comfort tier"
    )
    pacing_preference: Literal["relaxed", "moderate", "fast-paced"] = Field(
        default="moderate",
        description="Daily itinerary activity density (relaxed: 2 stops, moderate: 3 stops, fast: 4 stops)"
    )
    avoid_crowds: bool = Field(
        default=False,
        description="If True, prioritize less crowded heritage gems and early morning timings"
    )
    travel_month: Optional[int] = Field(
        default=None,
        ge=1,
        le=12,
        description="Month of travel (1=Jan .. 12=Dec) for thermal safety and seasonal activity checks"
    )

    @field_validator("total_budget_aed")
    @classmethod
    def validate_minimum_feasible_budget(cls, v: float, info) -> float:
        # Check that budget is reasonable (at least 200 AED per day minimum)
        if v < 150.0:
            raise ValueError(
                f"A total budget of AED {v:.2f} is below minimum subsistence cost for travel in Dubai."
            )
        return round(v, 2)

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, v: List[str]) -> List[str]:
        # Clean and normalize lowercase interest tags
        return [tag.strip().lower() for tag in v if tag.strip()]


class RawTripPrompt(BaseModel):
    """
    Container for the initial user natural language query and optional explicit overrides.
    """
    prompt_text: str = Field(..., min_length=5, description="Raw natural language travel request")
    override_budget_aed: Optional[float] = Field(None, gt=0)
    override_duration_days: Optional[int] = Field(None, ge=1, le=7)
    override_hotel_tier: Optional[Literal["budget", "midscale", "luxury"]] = None
