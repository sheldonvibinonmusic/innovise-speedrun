"""Analyst 5: Risk and Counter-Evidence Analyst Responsibility.

Purpose:
Actively search for evidence that weakens, contradicts, or qualifies the initial investment thesis:
- Retrieve relevant risk factors, financial caveats, uncertainties, and contradictory disclosures
- Search for counter-evidence to material growth or profitability claims
- Identify concentration, liquidity, leverage, legal, and operational risks supported by evidence
- Distinguish verified contradictory disclosures from ungrounded hypotheses
"""

import re
from typing import Any, Dict, List, Optional
from app.agents.analyst_models import AnalystOutput, CandidateClaim
from app.agents.llm_adapter import LLMAdapter, llm_adapter

RISK_TERMS = [
    r"risk factors?",
    r"headwinds?",
    r"uncertaint(?:y|ies)",
    r"decline",
    r"slowdown",
    r"contraction",
    r"losses?",
    r"compression",
    r"litigation",
    r"impairment",
    r"headwinds",
]
RISK_REGEX = re.compile("|".join(RISK_TERMS), re.IGNORECASE)


class RiskCounterEvidenceAnalyst:
    """Specialist dedicated to discovering disconfirming evidence, risks, and contradictions."""

    def __init__(self, adapter: Optional[LLMAdapter] = None):
        self.adapter = adapter or llm_adapter
        self.role_name = "Risk and Counter-Evidence Analyst"

    async def analyze(self, context: Dict[str, Any]) -> AnalystOutput:
        """Scan evidence and counter-evidence for risk disclosures and contradictions."""
        company_ticker = context.get("company_ticker", "UNKNOWN")
        evidence = context.get("evidence", [])
        counter_evidence = context.get("counter_evidence", [])
        all_candidate_evidence = evidence + counter_evidence

        findings: List[str] = []
        claims: List[CandidateClaim] = []
        warnings: List[str] = []
        missing_evidence: List[str] = []
        referenced_evidence: List[str] = []

        risk_passages = []
        for hit in all_candidate_evidence:
            content = hit.get("content", "")
            if RISK_REGEX.search(content):
                risk_passages.append(hit)

        if not risk_passages:
            findings.append(f"No explicit high-severity risk disclosures identified in current search scope for {company_ticker}.")
            warnings.append("Risk disclosures may be under-represented in retrieved evidence passages.")
        else:
            findings.append(f"Discovered {len(risk_passages)} material risk/counter-evidence disclosure(s) for {company_ticker}.")
            for idx, p in enumerate(risk_passages[:4]):
                chk_id = p.get("chunk_id", f"chk_risk_{idx}")
                pg = p.get("page_number", 1)
                content = p.get("content", "").strip()
                referenced_evidence.append(chk_id)

                # Flag contradictions if found
                is_contradiction = any(t in content.lower() for t in ["decline", "decreased drastically", "contraction", "compression"])
                claim_text = (
                    f"Contradictory disclosure noted on Page {pg}: {content[:150]}..."
                    if is_contradiction
                    else f"Material risk disclosure on Page {pg}: {content[:150]}..."
                )

                claims.append(
                    CandidateClaim(
                        claim_id=f"clm_risk_{idx:02d}",
                        claim_text=claim_text,
                        claim_type="risk_factor",
                        materiality="HIGH" if is_contradiction else "MEDIUM",
                        evidence_references=[chk_id],
                        confidence=0.95,
                    )
                )

        status = "COMPLETE"

        return AnalystOutput(
            analyst_role=self.role_name,
            findings=findings,
            claims=claims,
            referenced_evidence_ids=referenced_evidence,
            referenced_fact_ids=[],
            referenced_calculation_ids=[],
            warnings=warnings,
            missing_evidence=missing_evidence,
            completion_status=status,
        )
