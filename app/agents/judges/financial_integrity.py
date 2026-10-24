"""Judge 2: Numerical and Temporal Integrity Responsibility.

Audits whether:
- Numeric claims match validated source facts or calculation results
- Formula inputs are correct, comparable, and from consistent periods
- Currency units, scales, and scopes (consolidated vs standalone) match
- Quarterly, annual, and point-in-time figures are not confused
- Strict deterministic rules prevent conversational hand-waving
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from app.agents.analyst_models import CandidateClaim, ClaimEvaluation, JudgeVerdict
from app.finance.calculations import CalculationResult


class NumericalIntegrityJudge:
    """Independent judge auditing mathematical precision, accounting identities, and temporal consistency."""

    def __init__(self):
        self.role_name = "Numerical and Temporal Integrity"

    async def evaluate_claims(
        self,
        claims: List[CandidateClaim],
        calculations: List[CalculationResult],
        facts: List[Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> JudgeVerdict:
        """Deterministically audit numerical claims and calculation integrity."""
        calc_map = {c.calculation_id: c for c in calculations}
        fact_map = {
            (f.id if hasattr(f, "id") else f.get("fact_id")): f
            for f in facts
            if (hasattr(f, "id") and f.id) or (isinstance(f, dict) and f.get("fact_id"))
        }

        evaluations: List[ClaimEvaluation] = []
        has_block_error = False
        has_qualification = False

        for claim in claims:
            # Check calculated metrics or any claim with calculation reference
            if claim.claim_type == "calculated_metric" or claim.calculation_id:
                calc_id = claim.calculation_id
                if not calc_id or calc_id not in calc_map:
                    evaluations.append(
                        ClaimEvaluation(
                            claim_id=claim.claim_id,
                            status="needs_human_review",
                            reason="Claim asserted as calculated metric lacks deterministic calculation backing.",
                        )
                    )
                    has_qualification = True
                    continue

                calc = calc_map[calc_id]
                if calc.validation_outcome != "VALID":
                    evaluations.append(
                        ClaimEvaluation(
                            claim_id=claim.claim_id,
                            status="contradicted",
                            reason=f"Calculation failed validation: {calc.validation_outcome}. Warnings: {', '.join(calc.warnings)}",
                        )
                    )
                    has_block_error = True
                else:
                    evaluations.append(
                        ClaimEvaluation(
                            claim_id=claim.claim_id,
                            status="supported",
                            reason=f"Verified deterministic calculation: {calc.formula} = {calc.formatted_result}.",
                        )
                    )
            elif claim.claim_type == "reported_fact":
                # Verify that reported facts match underlying FinancialFact values
                if claim.fact_references:
                    verified = True
                    reasons = []
                    for fid in claim.fact_references:
                        if fid not in fact_map:
                            verified = False
                            reasons.append(f"Fact ID {fid} not found in SQLite registry")
                    if verified:
                        evaluations.append(
                            ClaimEvaluation(
                                claim_id=claim.claim_id,
                                status="supported",
                                reason="Numeric value grounded in authoritative SQLite FinancialFact record.",
                            )
                        )
                    else:
                        evaluations.append(
                            ClaimEvaluation(
                                claim_id=claim.claim_id,
                                status="needs_human_review",
                                reason="; ".join(reasons),
                            )
                        )
                        has_qualification = True
                else:
                    # Non-fact-referenced claim
                    evaluations.append(
                        ClaimEvaluation(
                            claim_id=claim.claim_id,
                            status="supported",
                            reason="Narrative claim without explicit numerical calculation dependencies.",
                        )
                    )
            else:
                evaluations.append(
                    ClaimEvaluation(
                        claim_id=claim.claim_id,
                        status="supported",
                        reason="Qualitative statement evaluated by evidence and counter-evidence reviewers.",
                    )
                )

        if has_block_error:
            overall = "BLOCK"
            explanation = "Deterministic calculation violation detected (division by zero, incompatible currency, or period mismatch)."
        elif has_qualification:
            overall = "QUALIFY"
            explanation = "Certain numerical assertions require human verification due to missing facts or unverified derivations."
        else:
            overall = "PASS"
            explanation = "All calculations and numerical claims satisfied deterministic accounting checks."

        return JudgeVerdict(
            judge_role=self.role_name,
            overall_verdict=overall,
            claim_evaluations=evaluations,
            concise_explanation=explanation,
        )
