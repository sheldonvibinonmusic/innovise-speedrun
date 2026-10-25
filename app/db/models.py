"""SQLAlchemy ORM Data Models.

Defines the core relational schema for the Trustworthy Financial Research System:
- Company: Corporate entity metadata and tickers
- Document: Registered source filings and uploaded PDFs
- DocumentChunk: Page-aware and table-aware segmented passages
- ResearchRun: Multi-agent research job tracking and status
- RunEvent: Granular audit trail and stage timing
- FinancialFact: Canonical, decimal-precision financial data points
"""

from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""
    pass


class Company(Base):
    """Corporate entity record."""

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    ticker = Column(String(32), unique=True, index=True, nullable=True)
    jurisdiction = Column(String(64), default="US", nullable=False)
    external_source_id = Column(String(128), index=True, nullable=True)  # e.g., SEC CIK
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    documents = relationship("Document", back_populates="company", cascade="all, delete-orphan")
    runs = relationship("ResearchRun", back_populates="company")
    facts = relationship("FinancialFact", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Company id={self.id} ticker={self.ticker} name={self.name}>"


class Document(Base):
    """Source filing or uploaded financial disclosure."""

    __tablename__ = "documents"

    id = Column(String(64), primary_key=True)  # doc_<uuid>
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    source_type = Column(String(64), nullable=False)  # "user_upload", "sec_edgar"
    source_url = Column(Text, nullable=True)
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(Text, nullable=False)
    sha256_hash = Column(String(64), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=True)
    document_type = Column(String(64), default="10-K", nullable=False)  # 10-K, 10-Q, ANNUAL_REPORT, etc.
    publication_date = Column(DateTime, nullable=True)
    reporting_period = Column(String(64), nullable=True)  # e.g., FY2024, Q3-2024
    jurisdiction = Column(String(64), default="US", nullable=False)
    source_identifier = Column(String(128), nullable=True)  # e.g., SEC Accession Number
    version = Column(String(32), default="1.0", nullable=False)
    retrieval_timestamp = Column(DateTime, default=utc_now, nullable=False)
    page_count = Column(Integer, nullable=True)
    ingestion_status = Column(String(64), default="REGISTERED", nullable=False)  # REGISTERED, PARSING, PARSED, INDEXING, INDEXED, PARTIALLY_PROCESSED, FAILED
    extraction_warnings = Column(Text, nullable=True)
    parser_version = Column(String(64), nullable=True)

    # Relationships
    company = relationship("Company", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index")
    facts = relationship("FinancialFact", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.original_filename} status={self.ingestion_status}>"


class DocumentChunk(Base):
    """Page-aware and table-aware segmented passage for dense and lexical indexing."""

    __tablename__ = "document_chunks"

    id = Column(String(64), primary_key=True)  # chk_<uuid>
    document_id = Column(String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_type = Column(String(32), default="narrative", nullable=False)  # narrative, table, footnote, heading
    section_title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, default=0, nullable=False)
    qdrant_point_id = Column(String(64), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)  # JSON-encoded extra metadata
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="chunks")

    @property
    def metadata_dict(self) -> Dict[str, Any]:
        if not self.metadata_json:
            return {}
        try:
            return json.loads(self.metadata_json)
        except Exception:
            return {}

    @metadata_dict.setter
    def metadata_dict(self, value: Dict[str, Any]) -> None:
        self.metadata_json = json.dumps(value or {})

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} doc={self.document_id} p={self.page_number} type={self.chunk_type}>"


class ResearchRun(Base):
    """Multi-agent research and decision-support execution run."""

    __tablename__ = "research_runs"

    id = Column(String(64), primary_key=True)  # run_<uuid>
    research_question = Column(Text, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    jurisdiction = Column(String(64), default="US", nullable=False)
    requested_periods_raw = Column(Text, nullable=True)  # JSON-encoded string
    input_document_ids_raw = Column(Text, nullable=True)  # JSON-encoded string
    status = Column(String(64), default="pending", nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    error_summary = Column(Text, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="runs")
    events = relationship("RunEvent", back_populates="run", cascade="all, delete-orphan", order_by="RunEvent.event_timestamp")
    report = relationship("ResearchReport", back_populates="run", uselist=False, cascade="all, delete-orphan")
    claims = relationship("ResearchClaim", back_populates="run", cascade="all, delete-orphan")

    @property
    def requested_periods(self) -> List[str]:
        if not self.requested_periods_raw:
            return []
        try:
            return json.loads(self.requested_periods_raw)
        except Exception:
            return []

    @requested_periods.setter
    def requested_periods(self, value: List[str]) -> None:
        self.requested_periods_raw = json.dumps(value or [])

    @property
    def input_document_ids(self) -> List[str]:
        if not self.input_document_ids_raw:
            return []
        try:
            return json.loads(self.input_document_ids_raw)
        except Exception:
            return []

    @input_document_ids.setter
    def input_document_ids(self, value: List[str]) -> None:
        self.input_document_ids_raw = json.dumps(value or [])

    def __repr__(self) -> str:
        return f"<ResearchRun id={self.id} status={self.status}>"


class RunEvent(Base):
    """Granular audit event emitted during research run execution."""

    __tablename__ = "run_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    node_or_stage = Column(String(128), nullable=False)
    event_timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)
    duration_ms = Column(Integer, nullable=True)
    status_or_code = Column(String(64), default="INFO", nullable=False)  # INFO, WARNING, ERROR, SUCCESS
    details_raw = Column(Text, nullable=True)  # JSON-encoded metadata
    model_or_parser_version = Column(String(64), nullable=True)

    # Relationships
    run = relationship("ResearchRun", back_populates="events")

    @property
    def details(self) -> Dict[str, Any]:
        if not self.details_raw:
            return {}
        try:
            return json.loads(self.details_raw)
        except Exception:
            return {"raw": self.details_raw}

    @details.setter
    def details(self, value: Dict[str, Any]) -> None:
        self.details_raw = json.dumps(value or {})

    def __repr__(self) -> str:
        return f"<RunEvent id={self.id} run_id={self.run_id} stage={self.node_or_stage}>"


class FinancialFact(Base):
    """Deterministic, normalized financial fact with exact provenance."""

    __tablename__ = "financial_facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True)
    metric_name = Column(String(128), nullable=False, index=True)
    numeric_value = Column(Numeric(precision=20, scale=4), nullable=False)
    currency = Column(String(16), default="USD", nullable=False)
    unit_scale = Column(String(32), default="ONES", nullable=False)  # ONES, THOUSANDS, MILLIONS, BILLIONS
    period_type = Column(String(32), default="annual", nullable=False)  # annual, quarterly, instant
    period_start_date = Column(DateTime, nullable=True)
    period_end_date = Column(DateTime, nullable=True)
    instant_date = Column(DateTime, nullable=True)
    reporting_scope = Column(String(64), default="consolidated", nullable=False)
    accounting_basis = Column(String(64), default="GAAP", nullable=False)
    source_document_id = Column(String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)
    page_number = Column(Integer, nullable=True)
    table_reference = Column(String(255), nullable=True)
    extraction_method = Column(String(64), default="table_parser", nullable=False)
    validation_status = Column(String(64), default="UNVERIFIED", nullable=False)

    # Relationships
    company = relationship("Company", back_populates="facts")
    document = relationship("Document", back_populates="facts")

    @property
    def reporting_period(self) -> Optional[str]:
        if self.table_reference and ":" in self.table_reference:
            parts = self.table_reference.split(":", 1)
            if parts[1].strip():
                return parts[1].strip()
        if self.period_end_date:
            return f"FY{self.period_end_date.strftime('%y')}"
        if self.document and self.document.reporting_period:
            return self.document.reporting_period
        return self.table_reference

    def __repr__(self) -> str:
        return f"<FinancialFact metric={self.metric_name} value={self.numeric_value} {self.currency}>"


class EvidenceRelationship(Base):
    """Source-linked entity and evidence relationship in the financial graph."""

    __tablename__ = "evidence_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(128), nullable=False, index=True)
    source_type = Column(String(64), nullable=False)  # company, document, financial_fact, claim, calculation
    target_id = Column(String(128), nullable=False, index=True)
    target_type = Column(String(64), nullable=False)
    relationship_type = Column(String(64), nullable=False, index=True)  # has_fact, contains_fact, supports_claim, contradicts_claim, derived_from_fact, depends_on_calc
    document_id = Column(String(64), nullable=True, index=True)
    page_number = Column(Integer, nullable=True)
    reporting_period = Column(String(64), nullable=True)
    confidence_score = Column(Numeric(precision=5, scale=4), default=Decimal("1.0"), nullable=False)
    validation_status = Column(String(32), default="candidate", nullable=False)  # candidate, verified, refuted
    extraction_method = Column(String(64), default="deterministic", nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    def __repr__(self) -> str:
        return f"<EvidenceRelationship {self.source_id} -[{self.relationship_type}]-> {self.target_id}>"


class ResearchClaim(Base):
    """Structured, verified analytical or factual claim linked to research run."""

    __tablename__ = "research_claims"

    id = Column(String(64), primary_key=True)  # clm_<uuid>
    run_id = Column(String(64), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(64), default="reported_fact", nullable=False)  # reported_fact, calculated_metric, interpretation, risk_factor
    materiality = Column(String(32), default="MEDIUM", nullable=False)  # HIGH, MEDIUM, LOW
    evidence_references_raw = Column(Text, nullable=True)  # JSON-encoded array of chunk_ids/citations
    fact_ids_raw = Column(Text, nullable=True)  # JSON-encoded array of fact_ids
    calculation_id = Column(String(64), nullable=True)
    verification_status = Column(String(64), default="needs_human_review", nullable=False, index=True)  # supported, contradicted, insufficient_evidence, needs_human_review
    verification_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    run = relationship("ResearchRun", back_populates="claims")

    @property
    def evidence_references(self) -> List[str]:
        if not self.evidence_references_raw:
            return []
        try:
            return json.loads(self.evidence_references_raw)
        except Exception:
            return []

    @evidence_references.setter
    def evidence_references(self, value: List[str]) -> None:
        self.evidence_references_raw = json.dumps(value or [])

    @property
    def fact_ids(self) -> List[int]:
        if not self.fact_ids_raw:
            return []
        try:
            return json.loads(self.fact_ids_raw)
        except Exception:
            return []

    @fact_ids.setter
    def fact_ids(self, value: List[int]) -> None:
        self.fact_ids_raw = json.dumps(value or [])

    def __repr__(self) -> str:
        return f"<ResearchClaim id={self.id} status={self.verification_status}>"


class ResearchReport(Base):
    """Persisted multi-agent research synthesis report."""

    __tablename__ = "research_reports"

    id = Column(String(64), primary_key=True)  # rep_<uuid>
    run_id = Column(String(64), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    executive_summary = Column(Text, nullable=False)
    report_markdown = Column(Text, nullable=False)
    structured_data_raw = Column(Text, nullable=True)  # JSON-encoded full report structure
    verification_status = Column(String(64), default="INDETERMINATE", nullable=False)  # VERIFIED, QUALIFIED, NEEDS_REVIEW, BLOCKED, INDETERMINATE
    quality_score = Column(Numeric(precision=5, scale=4), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    run = relationship("ResearchRun", back_populates="report")

    @property
    def structured_data(self) -> Dict[str, Any]:
        if not self.structured_data_raw:
            return {}
        try:
            return json.loads(self.structured_data_raw)
        except Exception:
            return {}

    @structured_data.setter
    def structured_data(self, value: Dict[str, Any]) -> None:
        self.structured_data_raw = json.dumps(value or {})

    def __repr__(self) -> str:
        return f"<ResearchReport id={self.id} run_id={self.run_id} status={self.verification_status}>"
