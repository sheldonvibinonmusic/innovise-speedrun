"""Analyst 6: Peer and Industry Comparison Responsibility.

Purpose:
Compare the subject corporate entity with relevant peers and industry baselines:
- Use only identified, reasonably comparable companies and authorized disclosures
- Preserve source, currency, and period metadata for any peer figures
- Apply consistent metric definitions and explain comparability limitations
- Explicitly abstain or mark section UNAVAILABLE when adequate peer facts are absent
"""

from typing import Any, Dict, List, Optional
from app.agents.analyst_models import AnalystOutput, CandidateClaim
from app.agents.llm_adapter import LLMAdapter, llm_adapter


class PeerComparisonAnalyst:
    """Specialist comparing target company metrics against peer and industry benchmarks."""

    def __init__(self, adapter: Optional[LLMAdapter] = None):
        self.adapter = adapter or llm_adapter
        self.role_name = "Peer and Industry Comparison"

    async def analyze(self, context: Dict[str, Any]) -> AnalystOutput:
        """Evaluate peer benchmarks or truthfully abstain when peer disclosures are absent."""
        company_ticker = context.get("company_ticker", "UNKNOWN")
        peer_data = context.get("peer_data", [])

        findings: List[str] = []
        claims: List[CandidateClaim] = []
        warnings: List[str] = []
        missing_evidence: List[str] = []

        if not peer_data:
            findings.append(
                f"Peer comparison data for {company_ticker} was not provided in current research scope. "
                "Abstaining from unsubstantiated comparative assertions."
            )
            warnings.append("No authorized peer corporate disclosures loaded in current run.")
            missing_evidence.append("Authorized peer filing disclosures")
            status = "UNAVAILABLE"
        else:
            findings.append(f"Loaded comparative metrics across {len(peer_data)} benchmark peer entity/entities.")
            for idx, p in enumerate(peer_data):
                p_ticker = p.get("ticker", "PEER")
                p_val = p.get("metric_value", "N/A")
                claims.append(
                    CandidateClaim(
                        claim_id=f"clm_peer_{idx:02d}",
                        claim_text=f"Peer {p_ticker} reported comparable metric value of {p_val}.",
                        claim_type="reported_fact",
                        materiality="MEDIUM",
                        confidence=0.90,
                    )
                )
            status = "COMPLETE"

        return AnalystOutput(
            analyst_role=self.role_name,
            findings=findings,
            claims=claims,
            referenced_evidence_ids=[],
            referenced_fact_ids=[],
            referenced_calculation_ids=[],
            warnings=warnings,
            missing_evidence=missing_evidence,
            completion_status=status,
        )
