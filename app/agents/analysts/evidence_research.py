"""Analyst 1: Financial Research and Source Coverage Responsibility.

Purpose:
Establish what evidence and documentation is available for the research question.
Responsibilities:
- Review the source manifest and relevant document metadata.
- Check that requested reporting periods and source types are represented.
- Identify missing or inaccessible documents and date/period gaps.
- Select relevant evidence and produce source-coverage findings.
- Return structured AnalystOutput without silently marking missing material complete.
"""

from typing import Any, Dict, List, Optional
from app.agents.analyst_models import AnalystOutput, CandidateClaim
from app.agents.llm_adapter import LLMAdapter, llm_adapter


class SourceCoverageAnalyst:
    """Specialist responsible for auditing document completeness and evidentiary coverage."""

    def __init__(self, adapter: Optional[LLMAdapter] = None):
        self.adapter = adapter or llm_adapter
        self.role_name = "Financial Research and Source Coverage"

    async def analyze(self, context: Dict[str, Any]) -> AnalystOutput:
        """Evaluate source coverage against requested question and periods."""
        research_question = context.get("research_question", "")
        company_ticker = context.get("company_ticker", "UNKNOWN")
        requested_periods = set(context.get("requested_periods", []))
        evidence = context.get("evidence", [])
        documents = context.get("documents", [])

        # Audit available periods in discovered/uploaded documents
        available_periods = set()
        for doc in documents:
            if isinstance(doc, dict) and doc.get("reporting_period"):
                available_periods.add(doc["reporting_period"])
            elif hasattr(doc, "reporting_period") and doc.reporting_period:
                available_periods.add(doc.reporting_period)

        missing_periods = list(requested_periods - available_periods)
        warnings: List[str] = []
        missing_evidence: List[str] = []

        if missing_periods:
            msg = f"Missing requested reporting periods: {', '.join(missing_periods)}"
            warnings.append(msg)
            missing_evidence.append(msg)

        if not evidence and not documents:
            warnings.append("Zero supporting documents or evidence chunks available in scope.")
            missing_evidence.append("Complete evidentiary absence")

        # Formulate findings
        findings = [
            f"Examined {len(documents)} document(s) and {len(evidence)} evidence passage(s) for {company_ticker}.",
            f"Represented reporting periods: {', '.join(available_periods) if available_periods else 'None recorded'}.",
        ]
        if missing_periods:
            findings.append(f"Coverage deficit identified for period(s): {', '.join(missing_periods)}.")

        claims = [
            CandidateClaim(
                claim_id=f"clm_cov_{i:02d}",
                claim_text=f"Filings available for {company_ticker} cover period {p}.",
                claim_type="reported_fact",
                materiality="MEDIUM",
                evidence_references=[e.get("chunk_id", "") for e in evidence[:2]],
                confidence=1.0,
            )
            for i, p in enumerate(available_periods)
        ]

        status = "DEGRADED" if missing_periods or not evidence else "COMPLETE"

        return AnalystOutput(
            analyst_role=self.role_name,
            findings=findings,
            claims=claims,
            referenced_evidence_ids=[e.get("chunk_id", "") for e in evidence if e.get("chunk_id")],
            referenced_fact_ids=[],
            referenced_calculation_ids=[],
            warnings=warnings,
            missing_evidence=missing_evidence,
            completion_status=status,
        )
