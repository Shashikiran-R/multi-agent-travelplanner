"""
Pydantic V2 Schemas for Cost Itemization and Budget Breakdown in AED.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator


class CostItem(BaseModel):
    """
    Individual itemized expenditure record.
    """
    category: Literal["accommodation", "dining", "attraction", "transit", "misc"]
    item_name: str
    cost_aed: float = Field(..., ge=0.0)
    day_number: Optional[int] = Field(None, ge=1)
    is_estimated: bool = Field(default=False)
    notes: Optional[str] = None


class BudgetBreakdown(BaseModel):
    """
    Complete category-wise financial ledger for the proposed trip.
    """
    accommodation_total_aed: float = Field(..., ge=0.0, description="Total hotel cost for (days - 1) nights")
    dining_total_aed: float = Field(..., ge=0.0, description="Estimated total food and beverage expenditure")
    attractions_total_aed: float = Field(..., ge=0.0, description="Total admissions and ticket fees")
    transit_total_aed: float = Field(..., ge=0.0, description="Total Metro, Taxi, and public transit fares")
    grand_total_aed: float = Field(..., ge=0.0, description="Sum of all category expenditures")
    budget_limit_aed: float = Field(..., gt=0.0, description="Target budget ceiling specified by user")
    remaining_balance_aed: float = Field(..., description="budget_limit_aed - grand_total_aed (can be negative if over budget)")
    is_within_budget: bool = Field(..., description="True if grand_total_aed <= budget_limit_aed")
    itemized_records: List[CostItem] = Field(default_factory=list, description="Detailed itemized cost ledger")

    @classmethod
    def calculate(
        cls,
        accommodation: float,
        dining: float,
        attractions: float,
        transit: float,
        budget_limit: float,
        records: Optional[List[CostItem]] = None
    ) -> "BudgetBreakdown":
        """
        Factory helper to compute sums, remaining balance, and budget compliance flag.
        """
        acc = round(accommodation, 2)
        din = round(dining, 2)
        att = round(attractions, 2)
        tra = round(transit, 2)
        limit = round(budget_limit, 2)
        
        grand = round(acc + din + att + tra, 2)
        balance = round(limit - grand, 2)
        within = grand <= limit

        return cls(
            accommodation_total_aed=acc,
            dining_total_aed=din,
            attractions_total_aed=att,
            transit_total_aed=tra,
            grand_total_aed=grand,
            budget_limit_aed=limit,
            remaining_balance_aed=balance,
            is_within_budget=within,
            itemized_records=records or []
        )
