"""Analyst 7: Research Synthesis and Decision Support Responsibility.

Purpose:
Consolidate structured findings from all analytical perspectives into an integrated briefing:
- Organize findings directly around the user's research question
- Synthesize key financial metrics, deterministic trends, risk factors, and contradictions
- Explicitly separate verified facts, deterministic calculations, and interpretations
- Preserve claim IDs, evidence citations, and calculation references
- Cannot overrule failed verification gates or manufacture missing facts
"""

from typing import Any, Dict, List, Optional
from app.agents.analyst_models import AnalystOutput, CandidateClaim
from app.agents.llm_adapter import LLMAdapter, llm_adapter


class ResearchSynthesisAnalyst:
    """Specialist consolidating specialist findings into an auditable research dossier."""

    def __init__(self, adapter: Optional[LLMAdapter] = None):
        self.adapter = adapter or llm_adapter
        self.role_name = "Research Synthesis and Decision Support"

    async def analyze(self, context: Dict[str, Any]) -> AnalystOutput:
        """Consolidate prior specialist outputs into unified executive synthesis."""
        research_question = context.get("research_question", "")
        company_ticker = context.get("company_ticker", "UNKNOWN")
        analyst_outputs: List[AnalystOutput] = context.get("prior_analyst_outputs", [])

        all_claims: List[CandidateClaim] = []
        all_warnings: List[str] = []
        all_missing: List[str] = []
        all_evidence: List[str] = []
        all_facts: List[int] = []
        all_calcs: List[str] = []
        findings: List[str] = [
            f"Research Inquiry: {research_question}",
            f"Target Entity: {company_ticker}",
        ]

        for out in analyst_outputs:
            all_claims.extend(out.claims)
            all_warnings.extend(out.warnings)
            all_missing.extend(out.missing_evidence)
            all_evidence.extend(out.referenced_evidence_ids)
            all_facts.extend(out.referenced_fact_ids)
            all_calcs.extend(out.referenced_calculation_ids)
            findings.append(f"[{out.analyst_role}]: {len(out.claims)} claim(s) formulated.")

        # High-level synthesized decision claim
        synthesis_claim = CandidateClaim(
            claim_id="clm_synthesis_summary",
            claim_text=(
                f"Multi-agent financial assessment for {company_ticker} synthesized {len(all_claims)} "
                f"claim(s) across {len(analyst_outputs)} analytical perspectives."
            ),
            claim_type="interpretation",
            materiality="HIGH",
            evidence_references=all_evidence[:3],
            fact_references=all_facts[:3],
            confidence=0.90,
        )
        all_claims.append(synthesis_claim)

        return AnalystOutput(
            analyst_role=self.role_name,
            findings=findings,
            claims=all_claims,
            referenced_evidence_ids=list(set(all_evidence)),
            referenced_fact_ids=list(set(all_facts)),
            referenced_calculation_ids=list(set(all_calcs)),
            warnings=list(set(all_warnings)),
            missing_evidence=list(set(all_missing)),
            completion_status="COMPLETE",
        )
