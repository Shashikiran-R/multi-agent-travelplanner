"""
Pydantic V2 Models Package for Dubai AI Travel Planner.
Exports all request, budget, review, and itinerary schemas.
"""

from src.models.request import UserConstraints, RawTripPrompt
from src.models.budget import CostItem, BudgetBreakdown
from src.models.review import ViolationItem, ReviewFeedback
from src.models.itinerary import (
    AttractionItem,
    RestaurantItem,
    TransitSegment,
    ActivitySlot,
    DayPlan,
    TripItinerary,
)

__all__ = [
    "UserConstraints",
    "RawTripPrompt",
    "CostItem",
    "BudgetBreakdown",
    "ViolationItem",
    "ReviewFeedback",
    "AttractionItem",
    "RestaurantItem",
    "TransitSegment",
    "ActivitySlot",
    "DayPlan",
    "TripItinerary",
]
