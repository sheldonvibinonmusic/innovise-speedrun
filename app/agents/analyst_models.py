"""Agent Persona Definitions & Analyst/Judge Structured Output Models.

Defines typed Pydantic contracts for:
- 7 Specialized Financial Analysts
- 3 Tripartite Verification Judges
- Research Quality Supervisor ("The Third Eye")
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class CandidateClaim(BaseModel):
    """Factual or analytical assertion formulated by a specialist analyst."""
    claim_id: str = Field(..., description="Unique claim identifier, e.g., clm_rev_growth_01")
    claim_text: str = Field(..., description="The substantive statement or finding")
    claim_type: Literal[
        "reported_fact",
        "calculated_metric",
        "interpretation",
        "risk_factor",
        "guidance_statement",
    ] = Field(default="reported_fact")
    materiality: Literal["HIGH", "MEDIUM", "LOW"] = Field(default="MEDIUM")
    evidence_references: List[str] = Field(
        default_factory=list,
        description="List of supporting chunk IDs or citation references",
    )
    fact_references: List[int] = Field(
        default_factory=list,
        description="IDs of underlying FinancialFact records in SQLite",
    )
    calculation_id: Optional[str] = Field(
        default=None,
        description="ID of deterministic calculation result if applicable",
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Analyst confidence score grounded in evidence clarity",
    )


class AnalystOutput(BaseModel):
    """Standardized output schema returned by each specialist financial analyst."""
    analyst_role: str = Field(..., description="Identifiable role of the specialist")
    findings: List[str] = Field(default_factory=list, description="Synthesized bullet-point takeaways")
    claims: List[CandidateClaim] = Field(default_factory=list, description="Discrete factual/calculated claims")
    referenced_evidence_ids: List[str] = Field(default_factory=list, description="All chunk IDs utilized")
    referenced_fact_ids: List[int] = Field(default_factory=list, description="All FinancialFact IDs utilized")
    referenced_calculation_ids: List[str] = Field(default_factory=list, description="All calculation IDs utilized")
    warnings: List[str] = Field(default_factory=list, description="Warnings and limitations")
    missing_evidence: List[str] = Field(default_factory=list, description="Explicitly identified evidence gaps")
    completion_status: Literal["COMPLETE", "DEGRADED", "FAILED", "UNAVAILABLE"] = Field(default="COMPLETE")


class ClaimEvaluation(BaseModel):
    """Individual verdict on a single claim by a verification judge."""
    claim_id: str
    status: Literal["supported", "contradicted", "insufficient_evidence", "needs_human_review"]
    reason: str
    suggested_correction: Optional[str] = None


class JudgeVerdict(BaseModel):
    """Evaluation envelope returned by a verification judge."""
    judge_role: Literal[
        "Evidence and Citation Verification",
        "Numerical and Temporal Integrity",
        "Counter-Evidence and Completeness Review",
    ]
    overall_verdict: Literal["PASS", "QUALIFY", "RETRIEVE_MORE", "BLOCK", "INDETERMINATE"]
    claim_evaluations: List[ClaimEvaluation] = Field(default_factory=list)
    concise_explanation: str = Field(..., description="Rationale for verdict tied to evidence/facts")
    required_followup_retrieval: Optional[str] = Field(
        default=None,
        description="Specific query or gap if follow-up search is required",
    )


class SupervisorDecision(BaseModel):
    """Control-flow decision emitted by the Research Quality Supervisor ("The Third Eye")."""
    action: Literal[
        "CONTINUE",
        "REPAIR_RETRIEVAL",
        "RETRY_OPERATION",
        "MARK_DEGRADED_COVERAGE",
        "ESCALATE",
        "STOP",
    ]
    reason: str
    failed_condition: Optional[str] = None
    target_stage: Optional[str] = None
    repair_query: Optional[str] = None
    remaining_retries: int = 1
    unresolved_uncertainties: List[str] = Field(default_factory=list)
