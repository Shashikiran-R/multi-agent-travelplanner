"""
Review Agent: Itinerary Quality Assurance Inspector & Constraint Auditor powered by Ollama
(nemotron-3-ultra) with deterministic offline fallback.
Executes deterministic validation checks (budget, pacing, geographic coherence,
transit feasibility, and summer thermal safety) and emits structured ReviewFeedback with
Ollama QA commentary.
Zero paid APIs ($0.00 cost).
"""

from typing import Dict, Any, List, Optional
from src.models.request import UserConstraints
from src.models.budget import BudgetBreakdown
from src.models.review import ReviewFeedback
from src.models.itinerary import DayPlan, TripItinerary
from src.tools.validation_tool import ValidationTool
from src.data_access.sqlite_client import DubaiSQLiteClient
from src.utils.llm_factory import get_ollama_llm, extract_text_content


class ReviewAgent:
    """
    Itinerary Quality Assurance Inspector & Auditor.
    1. Audits candidate plans against 6 hard rules (budget, pacing, districts, transit, duplicates, heat).
    2. Synthesizes findings using Ollama (nemotron-3-ultra) to generate
       an independent quality audit commentary and traveler advisory.
    3. Emits structured ReviewFeedback reports.
    4. Directs the revision node with actionable cost-cutting and rescheduling swaps.
    """

    def __init__(
        self,
        validation_tool: Optional[ValidationTool] = None,
        db_client: Optional[DubaiSQLiteClient] = None,
        llm: Optional[Any] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.db = db_client or DubaiSQLiteClient()
        self.validation_tool = validation_tool or ValidationTool(db_client=self.db)
        self.llm = llm if llm is not None else get_ollama_llm(
            temperature=0.1,
            base_url=base_url,
            api_key=api_key
        )

    def audit_itinerary_plan(
        self,
        days: List[DayPlan],
        budget: BudgetBreakdown,
        constraints: UserConstraints,
        revision_round: int = 0
    ) -> ReviewFeedback:
        """
        Runs comprehensive deterministic constraint checks and produces formal feedback,
        enhanced with Ollama (nemotron-3-ultra) QA commentary when available.
        """
        feedback = self.validation_tool.audit_plan(
            days=days,
            budget=budget,
            constraints=constraints,
            revision_round=revision_round
        )

        ollama_commentary = self._generate_ollama_audit_notes(
            feedback=feedback,
            days=days,
            budget=budget,
            constraints=constraints
        )
        if ollama_commentary:
            feedback.audit_notes = ollama_commentary

        return feedback

    def audit_full_itinerary(
        self,
        itinerary: TripItinerary,
        revision_round: int = 0
    ) -> ReviewFeedback:
        """Audits an assembled TripItinerary."""
        feedback = self.validation_tool.audit_itinerary(
            itinerary=itinerary,
            revision_round=revision_round
        )

        ollama_commentary = self._generate_ollama_audit_notes(
            feedback=feedback,
            days=itinerary.days,
            budget=itinerary.budget,
            constraints=itinerary.constraints
        )
        if ollama_commentary:
            feedback.audit_notes = ollama_commentary

        return feedback

    def _generate_ollama_audit_notes(
        self,
        feedback: ReviewFeedback,
        days: List[DayPlan],
        budget: BudgetBreakdown,
        constraints: UserConstraints
    ) -> Optional[str]:
        """
        Uses Ollama (nemotron-3-ultra) to synthesize audit findings into
        an authoritative quality assurance report and traveler guidance.
        """
        if not self.llm:
            if feedback.passed:
                return (
                    f"Deterministic Audit Verdict: PASSED. All 6 constraint suites satisfied "
                    f"(budget, pacing, district coherence, transit <= 60m, duplicate checks, thermal safety)."
                )
            return (
                f"Deterministic Audit Verdict: REVISION REQUIRED. Detected {len(feedback.structured_violations)} violation(s). "
                f"Issues: {'; '.join(feedback.violations[:3])}."
            )

        try:
            violations_summary = [f"- [{v.rule_name}] {v.message}" for v in feedback.structured_violations]
            system_prompt = (
                "You are the Chief Quality Assurance Inspector for Dubai travel planning powered by nemotron-3-ultra. "
                "Analyze the audit findings of this proposed itinerary. If the itinerary passed all rules, "
                "provide a concise commendation confirming its viability and pacing. If there are violations, "
                "clearly explain why each violation represents a risk in Dubai (e.g. summer heat exhaustion, "
                "cross-city traffic delays, or budget overruns) and endorse the corrective substitutions."
            )
            user_content = (
                f"Audit Status: {'PASSED' if feedback.passed else 'VIOLATIONS DETECTED'}\n"
                f"Revision Round: {feedback.revision_round}\n"
                f"Trip Duration: {constraints.trip_duration_days} days\n"
                f"Travel Month: {constraints.travel_month or 'Winter/Standard'}\n"
                f"Budget Limit: AED {budget.budget_limit_aed:.2f} | Grand Total: AED {budget.grand_total_aed:.2f} (Delta: AED {feedback.cost_delta_aed:.2f})\n"
                f"Violations:\n" + ("\n".join(violations_summary) if violations_summary else "None (All checks passed)\n") +
                f"Recommended Swaps:\n" + ("\n".join(feedback.recommended_swaps) if feedback.recommended_swaps else "None required\n")
            )
            response = self.llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ])
            content = extract_text_content(response)
            if content and len(content) > 20:
                return content
        except Exception as e:
            print(f"⚠️ Ollama review notice: {e}. Utilizing fallback audit notes.")

        if feedback.passed:
            return "Audit Passed: Itinerary satisfies all Dubai municipal, transit, and thermal constraints."
        return f"Audit Notice: {len(feedback.violations)} issues detected requiring revision."

    # Backwards-compatible alias
    _generate_gemini_audit_notes = _generate_ollama_audit_notes
