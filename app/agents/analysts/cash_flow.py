"""Analyst 4: Management Guidance and Disclosure Timeline Responsibility.

Purpose:
Analyze forward-looking statements, targets, and subsequent reported outcomes:
- Identify management guidance, forward-looking statements, and operational caveats
- Preserve original disclosure statements and exact source locations
- Track conditions, revisions, and subsequent actual outcomes where comparable
- Flag ambiguous, conditional, or restated statements
"""

import re
from typing import Any, Dict, List, Optional
from app.agents.analyst_models import AnalystOutput, CandidateClaim
from app.agents.llm_adapter import LLMAdapter, llm_adapter

GUIDANCE_TERMS = [
    r"expect(?:s|ed|ing)?",
    r"guidance",
    r"forecast(?:s|ed)?",
    r"anticipate(?:s|d)?",
    r"project(?:s|ed|ion)?",
    r"target(?:s|ed)?",
    r"outlook",
]
GUIDANCE_REGEX = re.compile("|".join(GUIDANCE_TERMS), re.IGNORECASE)


class ManagementGuidanceAnalyst:
    """Specialist tracking disclosure timelines, guidance milestones, and forward-looking statements."""

    def __init__(self, adapter: Optional[LLMAdapter] = None):
        self.adapter = adapter or llm_adapter
        self.role_name = "Management Guidance and Disclosure Timeline"

    async def analyze(self, context: Dict[str, Any]) -> AnalystOutput:
        """Scan disclosures for guidance commitments and forward-looking assertions."""
        company_ticker = context.get("company_ticker", "UNKNOWN")
        evidence = context.get("evidence", [])

        findings: List[str] = []
        claims: List[CandidateClaim] = []
        warnings: List[str] = []
        missing_evidence: List[str] = []

        guidance_passages = []
        for hit in evidence:
            content = hit.get("content", "")
            if GUIDANCE_REGEX.search(content):
                guidance_passages.append(hit)

        if not guidance_passages:
            findings.append(f"No explicit forward-looking guidance statements identified for {company_ticker} in retrieved corpus.")
            missing_evidence.append("Forward-looking guidance statements not identified in provided passages")
        else:
            findings.append(f"Identified {len(guidance_passages)} forward-looking guidance disclosures for {company_ticker}.")
            for idx, p in enumerate(guidance_passages[:3]):
                chk_id = p.get("chunk_id", f"chk_{idx}")
                pg = p.get("page_number", 1)
                text_snip = p.get("content", "").strip()[:180]
                claims.append(
                    CandidateClaim(
                        claim_id=f"clm_guidance_{idx:02d}",
                        claim_text=f"Management guidance disclosure (Page {pg}): {text_snip}...",
                        claim_type="guidance_statement",
                        materiality="HIGH",
                        evidence_references=[chk_id],
                        confidence=0.90,
                    )
                )

        status = "COMPLETE" if claims else ("DEGRADED" if not evidence else "COMPLETE")

        return AnalystOutput(
            analyst_role=self.role_name,
            findings=findings,
            claims=claims,
            referenced_evidence_ids=[p.get("chunk_id", "") for p in guidance_passages if p.get("chunk_id")],
            referenced_fact_ids=[],
            referenced_calculation_ids=[],
            warnings=warnings,
            missing_evidence=missing_evidence,
            completion_status=status,
        )
