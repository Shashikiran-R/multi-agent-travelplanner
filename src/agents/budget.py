"""
Budget Agent: Financial Ledger Formulation, Spending Variance Calculation,
and Cost-Cutting Swap Generation powered by Groq (with deterministic offline fallback).
Zero paid APIs ($0.00 cost).
"""

from typing import Dict, Any, List, Optional, Tuple
from src.models.request import UserConstraints
from src.models.budget import BudgetBreakdown
from src.models.itinerary import DayPlan
from src.tools.budget_tool import BudgetTool
from src.data_access.sqlite_client import DubaiSQLiteClient
from src.utils.llm_factory import get_groq_llm, extract_text_content


class BudgetAgent:
    """
    Travel Financial Analyst & Cost Optimization Specialist.
    1. Ingests municipal hotel benchmarks, attraction fees, and transit costs in AED.
    2. Formulates the complete itemized trip budget ledger.
    3. Calculates financial variance against user budget limits.
    4. Generates prioritized, high-impact substitution directives if spending exceeds budget.
    5. Formulates executive financial analysis and cost-cutting narratives via Groq (with deterministic fallback).
    """

    def __init__(
        self,
        budget_tool: Optional[BudgetTool] = None,
        db_client: Optional[DubaiSQLiteClient] = None,
        llm: Optional[Any] = None
    ):
        self.db = db_client or DubaiSQLiteClient()
        self.budget_tool = budget_tool or BudgetTool(db_client=self.db)
        self.llm = llm if llm is not None else get_groq_llm(temperature=0.1)
        self.last_financial_narrative: Optional[str] = None

    def calculate_budget(
        self,
        days: List[DayPlan],
        constraints: UserConstraints,
        hotel_district: str
    ) -> Tuple[BudgetBreakdown, float, List[Dict[str, Any]]]:
        """
        Computes itemized budget breakdown, detects cost delta, and generates swaps if necessary.
        Also formulates financial narrative via Groq when available.
        Returns (breakdown, cost_delta_aed, recommended_swaps).
        """
        # 1. Itemized calculation
        breakdown = self.budget_tool.calculate_itinerary_budget(
            days=days,
            hotel_district=hotel_district,
            hotel_tier=constraints.accommodation_tier,
            duration_days=constraints.trip_duration_days,
            budget_limit_aed=constraints.total_budget_aed
        )

        cost_delta_aed = round(max(0.0, breakdown.grand_total_aed - constraints.total_budget_aed), 2)
        swaps: List[Dict[str, Any]] = []

        # 2. If over budget, generate prioritized cost-cutting swaps
        if cost_delta_aed > 0.01:
            swaps = self.budget_tool.generate_cost_cutting_swaps(
                days=days,
                current_breakdown=breakdown,
                hotel_district=hotel_district,
                hotel_tier=constraints.accommodation_tier,
                duration_days=constraints.trip_duration_days
            )

        # 3. Generate financial narrative
        self.last_financial_narrative = self.generate_financial_narrative(
            breakdown=breakdown,
            cost_delta_aed=cost_delta_aed,
            swaps=swaps,
            constraints=constraints
        )

        return breakdown, cost_delta_aed, swaps

    def generate_financial_narrative(
        self,
        breakdown: BudgetBreakdown,
        cost_delta_aed: float,
        swaps: List[Dict[str, Any]],
        constraints: UserConstraints
    ) -> str:
        """
        Uses Groq (openai/gpt-oss-120b) to formulate an executive financial assessment in AED,
        explaining expense distribution and cost-cutting substitution rationale.
        """
        if not self.llm:
            if cost_delta_aed > 0:
                return (
                    f"Financial Notice: Projected total of AED {breakdown.grand_total_aed:.2f} exceeds "
                    f"budget limit of AED {constraints.total_budget_aed:.2f} by AED {cost_delta_aed:.2f}. "
                    f"Generated {len(swaps)} prioritized cost-cutting swaps to restore financial feasibility."
                )
            return (
                f"Financial Clearance: Projected spend of AED {breakdown.grand_total_aed:.2f} is within "
                f"budget limit of AED {constraints.total_budget_aed:.2f} with a buffer of "
                f"AED {breakdown.remaining_balance_aed:.2f}."
            )

        try:
            swap_notes = [f"- {s.get('description', 'Swap')}" for s in swaps[:3]]
            status_text = (
                f"Over Budget by AED {cost_delta_aed:.2f} (Target: AED {constraints.total_budget_aed:.2f}, Projected: AED {breakdown.grand_total_aed:.2f})"
                if cost_delta_aed > 0 else
                f"Within Budget (Target: AED {constraints.total_budget_aed:.2f}, Projected: AED {breakdown.grand_total_aed:.2f}, Buffer: AED {breakdown.remaining_balance_aed:.2f})"
            )

            system_prompt = (
                "You are an expert Dubai travel financial analyst. Provide a 2-sentence executive financial commentary "
                "in United Arab Emirates Dirham (AED). Highlight the largest expenditure categories and, if over budget, "
                "explain the recommended cost-cutting swaps."
            )
            user_content = (
                f"Financial Status: {status_text}\n"
                f"Breakdown:\n"
                f"- Lodging: AED {breakdown.accommodation_total_aed:.2f}\n"
                f"- Dining: AED {breakdown.dining_total_aed:.2f}\n"
                f"- Admissions: AED {breakdown.attractions_total_aed:.2f}\n"
                f"- Transit: AED {breakdown.transit_total_aed:.2f}\n"
                f"Recommended Swaps:\n" + ("\n".join(swap_notes) if swap_notes else "None required.")
            )
            response = self.llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ])
            content = extract_text_content(response)
            if content and len(content) > 20:
                return content
        except Exception as e:
            print(f"⚠️ Groq budget narrative notice: {e}. Utilizing fallback summary.")

        if cost_delta_aed > 0:
            return (
                f"Financial Notice: Projected total of AED {breakdown.grand_total_aed:.2f} exceeds "
                f"budget limit by AED {cost_delta_aed:.2f}. Recommended {len(swaps)} swaps."
            )
        return (
            f"Financial Clearance: Projected spend of AED {breakdown.grand_total_aed:.2f} is within "
            f"budget with AED {breakdown.remaining_balance_aed:.2f} surplus."
        )

    def apply_best_swap(
        self,
        days: List[DayPlan],
        swap: Dict[str, Any]
    ) -> Tuple[List[DayPlan], bool]:
        """
        Executes a swap action onto the day plans.
        """
        return self.budget_tool.apply_swap_to_itinerary(days, swap)
