"""Workflow State Definitions.

Defines the strongly typed state dictionary passed through the LangGraph workflow:
- Run parameters and company scope
- Ingestion and discovery manifests
- Subquestions, multi-hop evidence, and structured facts
- Deterministic calculation results
- Specialist analyst findings and candidate claims
- Judge verdicts and Supervisor decision trail
- Final synthesized report and verification statuses
"""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class ResearchWorkflowState(TypedDict, total=False):
    """Global state schema for the research workflow graph."""
    # Run identification & scope
    run_id: str
    research_question: str
    company_name: Optional[str]
    company_ticker: str
    jurisdiction: str
    requested_periods: List[str]
    acquisition_mode: str  # "upload", "website_discovery", "sec_edgar", "combined"
    seed_website_url: Optional[str]

    # Discovery & Document Ingestion
    source_manifest: Dict[str, Any]
    document_ids: List[str]
    documents_ready: bool

    # Subquestions & Multi-Hop Evidence
    subquestions: List[str]
    evidence: List[Dict[str, Any]]
    counter_evidence: List[Dict[str, Any]]
    financial_facts: List[Dict[str, Any]]

    # Deterministic Calculations
    calculations: List[Dict[str, Any]]

    # Specialist Analysts (7 Roles)
    analyst_outputs: List[Dict[str, Any]]
    candidate_claims: List[Dict[str, Any]]

    # Tripartite Verification Judges
    judge_verdicts: List[Dict[str, Any]]

    # Quality Supervisor ("The Third Eye")
    supervisor_decisions: List[Dict[str, Any]]
    remaining_repair_budget: int
    unresolved_uncertainties: List[str]

    # Workflow Execution Control & Output
    current_stage: str
    warnings: List[str]
    errors: List[str]
    report: Optional[Dict[str, Any]]
    report_markdown: Optional[str]
    verification_status: str  # "VERIFIED", "QUALIFIED", "NEEDS_REVIEW", "BLOCKED", "INDETERMINATE"
