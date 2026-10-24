"""Request & Response Validation Schemas.

Enforces parameter bounds and required fields for API endpoints:
- Research run creation
- Document upload metadata
- Company discovery lookup & coverage manifest
- Hybrid retrieval querying
- Human review sign-off
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class CreateRunRequest(BaseModel):
    """Payload contract for POST /api/runs."""

    research_question: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="The primary financial investigation inquiry or directive.",
        examples=["Analyze operating cash flow stability and debt maturity headroom for FY24."],
    )
    company_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Legal or commercial name of the corporate entity.",
        examples=["Microsoft Corporation"],
    )
    company_ticker: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Stock ticker symbol where applicable.",
        examples=["MSFT"],
    )
    company_id: Optional[int] = Field(
        default=None,
        description="Internal database ID of a pre-existing Company record.",
    )
    jurisdiction: str = Field(
        default="US",
        max_length=64,
        description="Regulatory jurisdiction of the subject company.",
        examples=["US"],
    )
    reporting_periods: List[str] = Field(
        default_factory=list,
        description="Target reporting periods for analysis (e.g., ['FY2023', 'FY2024']).",
    )
    analytical_areas: List[str] = Field(
        default_factory=list,
        description="Specific analytical lenses requested (e.g., ['profitability', 'cash_flow']).",
    )
    document_ids: List[str] = Field(
        default_factory=list,
        description="List of pre-uploaded Document IDs to include in the research scope.",
    )

    @field_validator("company_ticker")
    @classmethod
    def normalize_ticker(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v.strip().upper()
        return None

    @field_validator("research_question")
    @classmethod
    def validate_non_empty_question(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Research question cannot be blank or whitespace.")
        return clean


class CompanyDiscoverRequest(BaseModel):
    """Payload contract for POST /api/company/discover."""

    ticker_or_cik: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Stock ticker symbol or SEC CIK number.",
        examples=["AAPL"],
    )
    jurisdiction: str = Field(
        default="US",
        description="Jurisdiction code (e.g. 'US', 'IN').",
        examples=["US"],
    )
    filing_types: List[str] = Field(
        default=["10-K", "10-Q"],
        description="Filing categories to search.",
    )
    period: Optional[str] = Field(
        default=None,
        description="Optional fiscal year/period filter (e.g., '2024').",
        examples=["2024"],
    )
    max_periods: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum recent filing periods to fetch.",
    )


class DiscoveredFilingSchema(BaseModel):
    """Schema representing an individual discovered SEC filing."""
    accession_number: str
    form: str
    filing_date: str
    report_date: Optional[str] = None
    primary_document: str
    document_url: str
    fiscal_period: Optional[str] = None


class CompanyDiscoverResponse(BaseModel):
    """Coverage manifest response for POST /api/company/discover."""
    company_name: str
    cik: str
    ticker: str
    jurisdiction: str = "US"
    coverage_status: str  # COVERAGE_AVAILABLE, NO_FILINGS, AMBIGUOUS_COMPANY, UNSUPPORTED_JURISDICTION
    requested_period: Optional[str] = None
    available_periods: List[str] = Field(default_factory=list)
    discovered_filings: List[DiscoveredFilingSchema] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RetrievalQueryRequest(BaseModel):
    """Payload contract for POST /api/retrieval/search."""

    query: str = Field(..., min_length=2, description="Research or evidence query")
    company_ticker: Optional[str] = Field(default=None, description="Optional company ticker filter")
    document_id: Optional[str] = Field(default=None, description="Optional document ID filter")
    reporting_period: Optional[str] = Field(default=None, description="Optional reporting period filter")
    top_k: int = Field(default=10, ge=1, le=50, description="Max evidence chunks to retrieve")
    include_structured_facts: bool = Field(default=True, description="Query tabular facts in SQLite")
    include_counter_evidence: bool = Field(default=False, description="Search disconfirming disclosures")


class EvidenceItemSchema(BaseModel):
    """Single retrieved evidence item."""
    chunk_id: str
    document_id: str
    page_number: int
    chunk_type: str
    section_title: Optional[str] = None
    content: str
    company_ticker: Optional[str] = None
    reporting_period: Optional[str] = None
    score: float
    retrieval_routes: List[str] = Field(default_factory=list)
    dense_score: Optional[float] = None
    bm25_score: Optional[float] = None
    rerank_score: Optional[float] = None


class RetrievalQueryResponse(BaseModel):
    """Response payload for hybrid search."""
    query: str
    evidence: List[EvidenceItemSchema] = Field(default_factory=list)
    structured_facts: List[Dict[str, Any]] = Field(default_factory=list)
    counter_evidence: List[EvidenceItemSchema] = Field(default_factory=list)
    total_candidates: int
    warning: Optional[str] = None


class SubmitReviewRequest(BaseModel):
    """Payload contract for POST /api/runs/{run_id}/review."""

    overall_decision: str = Field(
        ...,
        description="Human sign-off decision: APPROVED, QUALIFIED, or REJECTED.",
        examples=["APPROVED"],
    )
    reviewer_name: str = Field(
        ...,
        min_length=2,
        max_length=128,
        description="Name or identifier of the reviewing analyst.",
        examples=["Senior Analyst"],
    )
    comments: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Reviewer rationale or audit remarks.",
    )
    claim_overrides: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Claim-level override actions or qualification badges.",
    )
