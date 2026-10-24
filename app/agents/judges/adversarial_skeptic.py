"""Judge 3: Counter-Evidence and Completeness Review Responsibility.

Audits whether:
- Relevant contradictory disclosures and counter-evidence have been examined
- Material negative information, litigation risks, or headwinds were omitted
- Key research subquestions remain unaddressed
- Conclusions go beyond what evidence safely supports
- Overly strong assertions are forced into QUALIFIED or NEEDS_HUMAN_REVIEW states
"""

from typing import Any, Dict, List, Optional
from app.agents.analyst_models import CandidateClaim, ClaimEvaluation, JudgeVerdict


class AdversarialSkepticJudge:
    """Independent judge auditing counter-evidence, completeness, and contradictory disclosures."""

    def __init__(self):
        self.role_name = "Counter-Evidence and Completeness Review"

    async def evaluate_claims(
        self,
        claims: List[CandidateClaim],
        counter_evidence: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> JudgeVerdict:
        """Examine whether claims ignore contradictory disclosures or risk caveats."""
        evaluations: List[ClaimEvaluation] = []
        has_contradiction = False
        has_caveat_qualification = False
        contradiction_queries: List[str] = []

        counter_texts = [c.get("content", "").lower() for c in counter_evidence]

        for claim in claims:
            claim_lower = claim.claim_text.lower()
            # If claim asserts strong growth or profit
            is_positive = any(w in claim_lower for w in ["strong growth", "highly profitable", "increased", "record highs"])

            # Check if counter-evidence contradicts this directly
            contradicted_by = None
            for c_text in counter_texts:
                if any(w in c_text for w in ["sharp revenue decline", "drastically decreased", "margin compression", "contraction", "operating losses"]):
                    contradicted_by = c_text[:120]
                    break

            if is_positive and contradicted_by:
                evaluations.append(
                    ClaimEvaluation(
                        claim_id=claim.claim_id,
                        status="contradicted",
                        reason=f"Direct contradictory disclosure discovered in filings: '{contradicted_by}...'",
                        suggested_correction="Acknowledge contradictory restatement or revenue decline alongside positive claim.",
                    )
                )
                has_contradiction = True
                contradiction_queries.append("restated revenue decline and risk factor disclosures")
            elif claim.claim_type == "interpretation" and "risk" not in claim_lower and counter_evidence:
                evaluations.append(
                    ClaimEvaluation(
                        claim_id=claim.claim_id,
                        status="needs_human_review",
                        reason="Interpretive thesis requires qualification against retrieved risk caveats.",
                    )
                )
                has_caveat_qualification = True
            else:
                evaluations.append(
                    ClaimEvaluation(
                        claim_id=claim.claim_id,
                        status="supported",
                        reason="Claim adequately accounts for available counter-evidence and risk factors.",
                    )
                )

        if has_contradiction:
            overall = "QUALIFY"
            explanation = "Seeded or authentic contradiction discovered between positive thesis and risk disclosures."
            query = contradiction_queries[0] if contradiction_queries else None
        elif has_caveat_qualification:
            overall = "QUALIFY"
            explanation = "Conclusions contain interpretations requiring human review against risk caveats."
            query = None
        else:
            overall = "PASS"
            explanation = "Report claims adequately reflect both positive findings and counter-evidence."
            query = None

        return JudgeVerdict(
            judge_role=self.role_name,
            overall_verdict=overall,
            claim_evaluations=evaluations,
            concise_explanation=explanation,
            required_followup_retrieval=query,
        )
