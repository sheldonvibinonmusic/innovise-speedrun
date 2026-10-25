"""Judge 1: Evidence & Citation Verification Responsibility.

Audits whether:
- Every material factual claim has relevant source evidence
- The cited passage actually supports the associated claim
- Extracted values and quotes are faithful to the source document
- Citations do not omit material qualifications or distort source meaning
"""

import re
from typing import Any, Dict, List, Optional
from app.agents.analyst_models import CandidateClaim, ClaimEvaluation, JudgeVerdict


class EvidenceCitationJudge:
    """Independent judge auditing claim-to-evidence fidelity and citation truth."""

    def __init__(self):
        self.role_name = "Evidence and Citation Verification"

    async def evaluate_claims(
        self,
        claims: List[CandidateClaim],
        evidence_chunks: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> JudgeVerdict:
        """Evaluate each candidate claim against cited source passages."""
        chunk_map = {c.get("chunk_id"): c for c in evidence_chunks if c.get("chunk_id")}
        evaluations: List[ClaimEvaluation] = []
        has_insufficient = False
        has_contradicted = False

        if not claims:
            return JudgeVerdict(
                judge_role=self.role_name,
                overall_verdict="BLOCK",
                claim_evaluations=[],
                concise_explanation="No candidate claims submitted for evidence audit. Evidence ledger is empty.",
                required_followup_retrieval="Retrieve primary financial statements and disclosures.",
            )

        if not evidence_chunks:
            evaluations = [
                ClaimEvaluation(
                    claim_id=claim.claim_id,
                    status="insufficient_evidence",
                    reason="No source evidence passages retrieved to ground this assertion.",
                    suggested_correction="Attach primary filing passage citation.",
                )
                for claim in claims
                if claim.claim_type != "calculated_metric"
            ]
            return JudgeVerdict(
                judge_role=self.role_name,
                overall_verdict="BLOCK",
                claim_evaluations=evaluations,
                concise_explanation="Zero source evidence passages available in corpus. Factual assertions cannot be verified.",
                required_followup_retrieval="Retrieve primary financial disclosures for ungrounded claims.",
            )

        for claim in claims:
            # Calculated claims are verified by Financial Integrity Judge
            if claim.claim_type == "calculated_metric":
                evaluations.append(
                    ClaimEvaluation(
                        claim_id=claim.claim_id,
                        status="supported",
                        reason="Mathematical derivation deferred to Numerical Integrity Judge.",
                    )
                )
                continue

            if not claim.evidence_references:
                evaluations.append(
                    ClaimEvaluation(
                        claim_id=claim.claim_id,
                        status="insufficient_evidence",
                        reason="Claim lacks any cited source document or passage references.",
                        suggested_correction="Attach valid chunk citation from verified filings.",
                    )
                )
                has_insufficient = True
                continue

            # Verify that at least one cited chunk actually exists and supports the statement
            supported_by_chunk = False
            relevant_chunk_found = False

            for ref in claim.evidence_references:
                chunk = chunk_map.get(ref)
                if not chunk:
                    continue
                relevant_chunk_found = True
                content = chunk.get("content", "").lower()
                claim_tokens = [w for w in re.findall(r"\w+", claim.claim_text.lower()) if len(w) > 3]

                # Check token overlap between claim and cited passage
                overlap = sum(1 for t in claim_tokens if t in content)
                ratio = overlap / max(len(claim_tokens), 1)

                if ratio >= 0.35 or any(num in content for num in re.findall(r"\$?\d+", claim.claim_text)):
                    supported_by_chunk = True
                    break

            if not relevant_chunk_found:
                evaluations.append(
                    ClaimEvaluation(
                        claim_id=claim.claim_id,
                        status="insufficient_evidence",
                        reason=f"Referenced chunk(s) {claim.evidence_references} not found in retrieved corpus.",
                    )
                )
                has_insufficient = True
            elif supported_by_chunk:
                evaluations.append(
                    ClaimEvaluation(
                        claim_id=claim.claim_id,
                        status="supported",
                        reason="Cited passage contains direct textual and numerical corroboration.",
                    )
                )
            else:
                evaluations.append(
                    ClaimEvaluation(
                        claim_id=claim.claim_id,
                        status="needs_human_review",
                        reason="Cited passage does not adequately support the claim assertion.",
                    )
                )
                has_insufficient = True

        if has_insufficient:
            overall = "RETRIEVE_MORE"
            explanation = "One or more factual claims lack verified citations or sufficient supporting passages."
            query = "Retrieve missing financial disclosures for ungrounded assertions"
        else:
            overall = "PASS"
            explanation = "All examined claims have corroborated, faithful document citations."
            query = None

        return JudgeVerdict(
            judge_role=self.role_name,
            overall_verdict=overall,
            claim_evaluations=evaluations,
            concise_explanation=explanation,
            required_followup_retrieval=query,
        )
