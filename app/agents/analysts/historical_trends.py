"""Analyst 3: Historical Trends and Financial Ratios Responsibility.

Purpose:
Analyze financial performance across comparable reporting periods:
- Compare multi-period historical values on a consistent accounting basis
- Calculate supported growth rates and trajectory ratios deterministically
- Identify material changes and unusual financial variances
- Never compare values with incompatible periods or accounting scopes without explicit reconciliation
"""

from typing import Any, Dict, List, Optional
from app.agents.analyst_models import AnalystOutput, CandidateClaim
from app.agents.llm_adapter import LLMAdapter, llm_adapter
from app.finance.calculations import calculate_revenue_growth


class HistoricalTrendsAnalyst:
    """Specialist analyzing multi-period trajectory, growth rates, and financial trends."""

    def __init__(self, adapter: Optional[LLMAdapter] = None):
        self.adapter = adapter or llm_adapter
        self.role_name = "Historical Trends and Financial Ratios"

    async def analyze(self, context: Dict[str, Any]) -> AnalystOutput:
        """Evaluate multi-period trend metrics and calculate growth trajectories."""
        company_ticker = context.get("company_ticker", "UNKNOWN")
        facts = context.get("financial_facts", [])
        evidence = context.get("evidence", [])

        rev_facts = [
            f for f in facts
            if (f.metric_name if hasattr(f, "metric_name") else f.get("metric_name")) == "TotalRevenue"
        ]

        findings: List[str] = []
        claims: List[CandidateClaim] = []
        referenced_calcs: List[str] = []
        referenced_facts: List[int] = []
        warnings: List[str] = []
        missing_evidence: List[str] = []

        if len(rev_facts) >= 2:
            fact_cur = rev_facts[0]
            fact_prior = rev_facts[1]
            growth_calc = calculate_revenue_growth(fact_cur, fact_prior)

            if growth_calc.validation_outcome == "VALID":
                referenced_calcs.append(growth_calc.calculation_id)
                referenced_facts.extend(growth_calc.source_fact_ids)
                findings.append(
                    f"Revenue growth for {company_ticker} was {growth_calc.formatted_result} "
                    f"({growth_calc.reporting_period})."
                )
                claims.append(
                    CandidateClaim(
                        claim_id="clm_trend_rev_growth",
                        claim_text=f"Total Revenue increased by {growth_calc.formatted_result} across comparable periods.",
                        claim_type="calculated_metric",
                        materiality="HIGH",
                        calculation_id=growth_calc.calculation_id,
                        fact_references=growth_calc.source_fact_ids,
                        confidence=1.0,
                    )
                )
            else:
                warnings.extend(growth_calc.warnings)
        else:
            findings.append("Insufficient multi-period revenue facts for longitudinal trend calculation.")
            missing_evidence.append("Prior period revenue comparison baseline missing")

        # Scan narrative evidence for trend disclosures
        for hit in evidence[:3]:
            content = hit.get("content", "")
            if any(term in content.lower() for term in ["increased", "growth", "declined", "momentum", "expanded"]):
                claims.append(
                    CandidateClaim(
                        claim_id=f"clm_trend_narrative_{hit.get('chunk_id')}",
                        claim_text=f"Management reported operational momentum in: {content[:140]}...",
                        claim_type="interpretation",
                        materiality="MEDIUM",
                        evidence_references=[hit.get("chunk_id", "")],
                        confidence=0.85,
                    )
                )

        status = "COMPLETE" if claims else ("DEGRADED" if warnings else "UNAVAILABLE")

        return AnalystOutput(
            analyst_role=self.role_name,
            findings=findings,
            claims=claims,
            referenced_evidence_ids=[e.get("chunk_id", "") for e in evidence if e.get("chunk_id")],
            referenced_fact_ids=referenced_facts,
            referenced_calculation_ids=referenced_calcs,
            warnings=warnings,
            missing_evidence=missing_evidence,
            completion_status=status,
        )
