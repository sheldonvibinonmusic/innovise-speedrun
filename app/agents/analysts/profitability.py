"""Analyst 2: Financial Statements and Metrics Responsibility.

Purpose:
Analyze reported financial facts and accounting statements:
- Work from validated financial facts and relevant source passages
- Examine revenue, operating income, net income, cash flow, and balance sheet line items
- Identify mismatches in units, currencies, periods, and accounting definitions
- Rely strictly on deterministic calculation services rather than free-form arithmetic
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.agents.analyst_models import AnalystOutput, CandidateClaim
from app.agents.llm_adapter import LLMAdapter, llm_adapter
from app.finance.calculations import calculate_net_margin, calculate_operating_margin


class FinancialStatementsAnalyst:
    """Specialist analyzing reported line items, profitability metrics, and margin quality."""

    def __init__(self, adapter: Optional[LLMAdapter] = None):
        self.adapter = adapter or llm_adapter
        self.role_name = "Financial Statements and Metrics"

    async def analyze(self, context: Dict[str, Any]) -> AnalystOutput:
        """Examine reported metrics and compute core profitability margins deterministically."""
        company_ticker = context.get("company_ticker", "UNKNOWN")
        facts = context.get("financial_facts", [])
        evidence = context.get("evidence", [])

        # Index facts by metric_name
        facts_by_metric: Dict[str, List[Any]] = {}
        for f in facts:
            mname = f.metric_name if hasattr(f, "metric_name") else f.get("metric_name")
            facts_by_metric.setdefault(mname, []).append(f)

        findings: List[str] = []
        claims: List[CandidateClaim] = []
        referenced_facts: List[int] = []
        referenced_calcs: List[str] = []
        warnings: List[str] = []
        missing_evidence: List[str] = []

        rev_facts = facts_by_metric.get("TotalRevenue", [])
        op_facts = facts_by_metric.get("OperatingIncome", [])
        net_facts = facts_by_metric.get("NetIncome", [])

        if not rev_facts:
            missing_evidence.append("TotalRevenue fact not found in tabular disclosures")
            warnings.append("Absence of TotalRevenue facts impedes full margin analysis")
        else:
            latest_rev = rev_facts[0]
            fid = latest_rev.id if hasattr(latest_rev, "id") else latest_rev.get("fact_id", 0)
            val = latest_rev.numeric_value if hasattr(latest_rev, "numeric_value") else latest_rev.get("numeric_value")
            curr = latest_rev.currency if hasattr(latest_rev, "currency") else latest_rev.get("currency", "USD")
            scale = latest_rev.unit_scale if hasattr(latest_rev, "unit_scale") else latest_rev.get("unit_scale", "ONES")
            pg = latest_rev.page_number if hasattr(latest_rev, "page_number") else latest_rev.get("page_number", 1)

            findings.append(f"Reported Total Revenue for {company_ticker}: {val} {curr} ({scale}, Page {pg}).")
            if fid:
                referenced_facts.append(fid)

            claims.append(
                CandidateClaim(
                    claim_id="clm_metric_rev_01",
                    claim_text=f"{company_ticker} reported Total Revenue of {val} {curr} ({scale}).",
                    claim_type="reported_fact",
                    materiality="HIGH",
                    fact_references=[fid] if fid else [],
                    evidence_references=[e.get("chunk_id", "") for e in evidence[:1] if e.get("chunk_id")],
                    confidence=1.0,
                )
            )

        # Compute deterministic operating margin if facts present
        if rev_facts and op_facts:
            latest_rev = rev_facts[0]
            latest_op = op_facts[0]
            op_calc = calculate_operating_margin(latest_op, latest_rev)
            if op_calc.validation_outcome == "VALID":
                referenced_calcs.append(op_calc.calculation_id)
                findings.append(f"Operating Margin computed deterministically: {op_calc.formatted_result}.")
                claims.append(
                    CandidateClaim(
                        claim_id="clm_metric_op_margin",
                        claim_text=f"Deterministic Operating Margin is {op_calc.formatted_result}.",
                        claim_type="calculated_metric",
                        materiality="HIGH",
                        calculation_id=op_calc.calculation_id,
                        fact_references=op_calc.source_fact_ids,
                        confidence=1.0,
                    )
                )
            else:
                warnings.extend(op_calc.warnings)

        # Compute deterministic net margin if facts present
        if rev_facts and net_facts:
            latest_rev = rev_facts[0]
            latest_net = net_facts[0]
            net_calc = calculate_net_margin(latest_net, latest_rev)
            if net_calc.validation_outcome == "VALID":
                referenced_calcs.append(net_calc.calculation_id)
                findings.append(f"Net Profit Margin computed deterministically: {net_calc.formatted_result}.")
                claims.append(
                    CandidateClaim(
                        claim_id="clm_metric_net_margin",
                        claim_text=f"Deterministic Net Margin is {net_calc.formatted_result}.",
                        claim_type="calculated_metric",
                        materiality="HIGH",
                        calculation_id=net_calc.calculation_id,
                        fact_references=net_calc.source_fact_ids,
                        confidence=1.0,
                    )
                )
            else:
                warnings.extend(net_calc.warnings)

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
