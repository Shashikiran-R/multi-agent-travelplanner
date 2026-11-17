"""
Orchestrator Agent: Natural Language Request Parser, Financial Feasibility Guardrail,
and Itinerary Synthesizer powered by Groq (with deterministic offline fallback).
Zero paid APIs ($0.00 cost).
"""

import re
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple

from src.models.request import UserConstraints
from src.models.itinerary import DayPlan, TripItinerary
from src.models.budget import BudgetBreakdown
from src.models.review import ReviewFeedback
from src.data_access.sqlite_client import DubaiSQLiteClient
from src.utils.llm_factory import get_groq_llm, is_groq_available, extract_text_content


class OrchestratorAgent:
    """
    Senior Travel Solutions Architect & Workflow Coordinator.
    - Utilizes Groq (openai/gpt-oss-120b) for natural language understanding and entity extraction.
    - Runs early rejection guardrail against mathematical baseline costs in Dubai.
    - Assembles final validated TripItinerary presentation models.
    """

    # Absolute minimum accommodation cost per night in Dubai (Budget tier in Old Dubai / Outskirts)
    MIN_NIGHTLY_LODGING_AED = 200.0  # 200 in Outskirts, 210 in Deira/Old Dubai
    # Absolute minimum daily subsistence cost (2 budget meals @ AED 35 + RTA Metro Silver Nol)
    MIN_DAILY_SUBSISTENCE_AED = 80.0  # AED 70 food + AED 10 transit

    def __init__(
        self,
        db_client: Optional[DubaiSQLiteClient] = None,
        llm: Optional[Any] = None
    ):
        self.db = db_client or DubaiSQLiteClient()
        self.llm = llm if llm is not None else get_groq_llm(temperature=0.1)

    def parse_prompt(
        self,
        raw_prompt: str,
        overrides: Optional[Dict[str, Any]] = None
    ) -> Tuple[UserConstraints, bool, Optional[str]]:
        """
        Parses free-text user prompt into structured UserConstraints using Groq LLM
        (or deterministic regex fallback when Groq is unavailable).
        Returns (constraints, is_rejected, rejection_reason).
        """
        overrides = overrides or {}
        extracted_data = {}

        # 1. Attempt parsing with Groq LLM if available
        if self.llm:
            try:
                system_prompt = (
                    "You are a Dubai travel concierge AI. Your job is to extract user trip constraints "
                    "from natural language into a clean JSON object.\n"
                    "Output ONLY valid JSON matching this schema:\n"
                    "{\n"
                    '  "trip_duration_days": int (1 to 7),\n'
                    '  "total_budget_aed": float (in United Arab Emirates Dirham AED; convert USD at 3.67 if given in $),\n'
                    '  "interests": list of strings (e.g. ["culture", "beach", "food", "views", "shopping", "adventure", "nature", "free"]),\n'
                    '  "accommodation_tier": "budget" | "midscale" | "luxury",\n'
                    '  "pacing_preference": "relaxed" | "moderate" | "fast-paced",\n'
                    '  "avoid_crowds": boolean,\n'
                    '  "travel_month": int (1 to 12) or null\n'
                    "}"
                )
                response = self.llm.invoke([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract travel constraints from this prompt:\n{raw_prompt}"}
                ])
                content = extract_text_content(response)
                # Strip markdown code blocks if present
                clean_json = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", content).strip()
                parsed = json.loads(clean_json)
                if isinstance(parsed, dict):
                    extracted_data = parsed
            except Exception as e:
                print(f"⚠️ Groq parse notice: {e}. Utilizing deterministic extraction fallback.")
                extracted_data = {}

        # 2. Deterministic Regex / Keyword Fallback for any missing fields
        deterministic_constraints = self._deterministic_extract(raw_prompt)

        # Merge extracted fields: overrides > groq > deterministic
        trip_duration = overrides.get("trip_duration_days") or extracted_data.get("trip_duration_days") or deterministic_constraints["trip_duration_days"]
        trip_duration = max(1, min(7, int(trip_duration)))

        total_budget = overrides.get("total_budget_aed") or extracted_data.get("total_budget_aed") or deterministic_constraints["total_budget_aed"]
        total_budget = float(total_budget)

        interests = overrides.get("interests") or extracted_data.get("interests") or deterministic_constraints["interests"]
        if not interests:
            interests = ["culture", "views", "food"]

        tier = overrides.get("accommodation_tier") or extracted_data.get("accommodation_tier") or deterministic_constraints["accommodation_tier"]
        if tier not in ["budget", "midscale", "luxury"]:
            tier = "midscale"

        pacing = overrides.get("pacing_preference") or extracted_data.get("pacing_preference") or deterministic_constraints["pacing_preference"]
        if pacing not in ["relaxed", "moderate", "fast-paced"]:
            pacing = "moderate"

        avoid_crowds = overrides.get("avoid_crowds")
        if avoid_crowds is None:
            raw_crowd = extracted_data.get("avoid_crowds")
            avoid_crowds = raw_crowd if raw_crowd is not None else deterministic_constraints["avoid_crowds"]
        avoid_crowds = bool(avoid_crowds)

        travel_month = overrides.get("travel_month") or extracted_data.get("travel_month") or deterministic_constraints["travel_month"]
        if travel_month is not None:
            travel_month = max(1, min(12, int(travel_month)))

        constraints = UserConstraints(
            trip_duration_days=trip_duration,
            total_budget_aed=total_budget,
            interests=interests,
            accommodation_tier=tier,
            pacing_preference=pacing,
            avoid_crowds=avoid_crowds,
            travel_month=travel_month
        )

        # 3. Early Rejection Guardrail Check
        is_rejected, rejection_reason = self.check_rejection_guardrail(constraints)
        return constraints, is_rejected, rejection_reason

    def _deterministic_extract(self, prompt: str) -> Dict[str, Any]:
        """Robust deterministic regex-based extractor."""
        p_lower = prompt.lower()

        # Duration
        duration = 3
        duration_match = re.search(r"(\d+)\s*(?:-| )*(?:day|days|night|nights)", p_lower)
        if duration_match:
            duration = int(duration_match.group(1))
        elif "weekend" in p_lower:
            duration = 2
        elif "week" in p_lower:
            duration = 7
        elif "stopover" in p_lower or "one day" in p_lower:
            duration = 1

        # Budget
        budget = 4000.0
        budget_match = re.search(r"(?:aed|dirhams?|dhs?)\s*[:=]?\s*([\d,]+(?:\.\d+)?)", p_lower)
        if not budget_match:
            budget_match = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:aed|dirhams?|dhs?)", p_lower)
        if not budget_match:
            usd_match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", p_lower) or re.search(r"([\d,]+(?:\.\d+)?)\s*usd", p_lower)
            if usd_match:
                budget = round(float(usd_match.group(1).replace(",", "")) * 3.6725, 2)
        elif budget_match:
            budget = float(budget_match.group(1).replace(",", ""))
        elif "luxury" in p_lower:
            budget = 8000.0
        elif "budget" in p_lower or "cheap" in p_lower:
            budget = 2500.0

        # Accommodation Tier
        if any(k in p_lower for k in ["luxury", "5 star", "resort", "suite", "lavish"]):
            tier = "luxury"
        elif any(k in p_lower for k in ["cheap", "budget", "hostel", "economy", "affordable"]):
            tier = "budget"
        else:
            tier = "midscale"

        # Interests
        interests = []
        tag_keywords = {
            "culture": ["culture", "heritage", "history", "museum", "souk", "old dubai", "tradition"],
            "beach": ["beach", "coast", "swimming", "sand", "jbr", "coastal", "sun"],
            "food": ["food", "dining", "cuisine", "gourmet", "restaurant", "culinary", "eat"],
            "adventure": ["adventure", "desert", "safari", "dune", "adrenaline", "waterpark"],
            "shopping": ["shopping", "mall", "souks", "fashion", "bazaar"],
            "views": ["view", "skyline", "burj khalifa", "observation", "viewpoint", "panorama"],
            "nature": ["nature", "wildlife", "flamingo", "sanctuary", "garden"],
            "free": ["free", "complimentary", "frugal", "low cost"]
        }
        for tag, kws in tag_keywords.items():
            if any(kw in p_lower for kw in kws):
                interests.append(tag)

        # Pacing
        if any(k in p_lower for k in ["relaxed", "slow", "chill", "leisurely"]):
            pacing = "relaxed"
        elif any(k in p_lower for k in ["packed", "fast", "intensive", "action-packed"]):
            pacing = "fast-paced"
        else:
            pacing = "moderate"

        # Month
        month = None
        month_map = {
            "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
            "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
            "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9,
            "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12
        }
        for m_name, m_num in month_map.items():
            if re.search(r"\b" + m_name + r"\b", p_lower):
                month = m_num
                break

        return {
            "trip_duration_days": duration,
            "total_budget_aed": budget,
            "interests": interests or ["culture", "views", "food"],
            "accommodation_tier": tier,
            "pacing_preference": pacing,
            "avoid_crowds": any(k in p_lower for k in ["avoid crowd", "quiet", "off the beaten path"]),
            "travel_month": month
        }

    def check_rejection_guardrail(self, constraints: UserConstraints) -> Tuple[bool, Optional[str]]:
        """
        Enforces mathematical feasibility guardrail grounded in seed_data.json baselines:
        Minimum Threshold = (Duration - 1) * AED 200 (Hotel) + Duration * AED 80 (Meals & Metro).
        """
        d = constraints.trip_duration_days
        nights = max(1, d - 1)
        min_lodging = nights * self.MIN_NIGHTLY_LODGING_AED
        min_subsistence = d * self.MIN_DAILY_SUBSISTENCE_AED
        min_threshold = round(min_lodging + min_subsistence, 2)

        if constraints.total_budget_aed < min_threshold:
            reason = (
                f"Budget Rejection: Your total budget of AED {constraints.total_budget_aed:.2f} is mathematically "
                f"insufficient for a {d}-day trip to Dubai. Based on real municipal benchmarks in our database, "
                f"the absolute minimum baseline is AED {min_threshold:.2f} "
                f"({nights} nights @ AED {self.MIN_NIGHTLY_LODGING_AED:.0f}/night economy lodging in Old Dubai/Deira, "
                f"plus AED {min_subsistence:.0f} for budget meals and RTA Metro Silver Nol transit). "
                f"Please increase your budget to at least AED {min_threshold:.2f} or adjust trip duration."
            )
            return True, reason

        return False, None

    def assemble_final_itinerary(
        self,
        constraints: UserConstraints,
        days: List[DayPlan],
        budget: BudgetBreakdown,
        review: ReviewFeedback,
        title: Optional[str] = None,
        summary: Optional[str] = None
    ) -> TripItinerary:
        """
        Synthesizes the validated planning components into a complete TripItinerary model.
        """
        trip_id = f"dxb_{uuid.uuid4().hex[:8]}"
        interests_str = ", ".join(i.capitalize() for i in constraints.interests[:3])
        default_title = f"{constraints.trip_duration_days}-Day Curated Dubai Experience ({interests_str})"
        
        status_label = "Fully Verified & Optimized" if review.passed else f"Approved with Notes (Round {review.revision_round})"
        default_summary = (
            f"Curated {constraints.trip_duration_days}-day itinerary across Dubai's core districts "
            f"with {constraints.accommodation_tier.capitalize()} accommodation based in {days[0].hotel_area if days else 'Downtown'}. "
            f"Financial Status: {status_label}. Projected total expenditure: AED {budget.grand_total_aed:.2f} "
            f"against user budget of AED {budget.budget_limit_aed:.2f}."
        )

        # Enhance summary via Groq if available
        if self.llm and not summary:
            try:
                res = self.llm.invoke([
                    {"role": "system", "content": "You are a luxury Dubai travel writer. Write a concise 2-sentence executive summary of this trip itinerary."},
                    {"role": "user", "content": f"Trip duration: {constraints.trip_duration_days} days. Total spend: AED {budget.grand_total_aed}. Districts: {[d.primary_district for d in days]}. Interests: {constraints.interests}"}
                ])
                summary_text = extract_text_content(res)
                if summary_text and len(summary_text) > 20:
                    default_summary = summary_text
            except Exception:
                pass

        return TripItinerary(
            trip_id=trip_id,
            title=title or default_title,
            summary=summary or default_summary,
            constraints=constraints,
            days=days,
            budget=budget,
            review=review
        )
