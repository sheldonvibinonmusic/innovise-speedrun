"""Repository layer for structured domain entity access.

Encapsulates database operations for Companies, Documents, DocumentChunks,
ResearchRuns, RunEvents, and FinancialFacts.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    Company,
    Document,
    DocumentChunk,
    EvidenceRelationship,
    FinancialFact,
    ResearchClaim,
    ResearchReport,
    ResearchRun,
    RunEvent,
)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Repository:
    """Synchronous repository providing transactional persistence operations."""

    def __init__(self, db: Session):
        self.db = db

    # --- Company Operations ---

    def get_company_by_id(self, company_id: int) -> Optional[Company]:
        """Fetch company by internal integer ID."""
        return self.db.get(Company, company_id)

    def get_company_by_ticker(self, ticker: str) -> Optional[Company]:
        """Fetch company by stock ticker symbol."""
        stmt = select(Company).where(Company.ticker == ticker.upper())
        return self.db.scalars(stmt).first()

    def create_company(
        self,
        name: str,
        ticker: Optional[str] = None,
        jurisdiction: str = "US",
        external_source_id: Optional[str] = None,
    ) -> Company:
        """Create and commit a new corporate entity."""
        company = Company(
            name=name,
            ticker=ticker.upper() if ticker else None,
            jurisdiction=jurisdiction,
            external_source_id=external_source_id,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    # --- Document Operations ---

    def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """Fetch document by unique string ID."""
        return self.db.get(Document, document_id)

    def get_document_by_hash(self, sha256_hash: str) -> Optional[Document]:
        """Find existing document with identical content hash (deduplication)."""
        stmt = select(Document).where(Document.sha256_hash == sha256_hash)
        return self.db.scalars(stmt).first()

    def get_documents_by_company(self, company_id: int) -> List[Document]:
        """Fetch all documents registered for a company."""
        stmt = select(Document).where(Document.company_id == company_id)
        return list(self.db.scalars(stmt).all())

    def create_document(
        self,
        document_id: str,
        original_filename: str,
        stored_path: str,
        sha256_hash: str,
        source_type: str = "user_upload",
        company_id: Optional[int] = None,
        title: Optional[str] = None,
        document_type: str = "10-K",
        jurisdiction: str = "US",
        reporting_period: Optional[str] = None,
        source_url: Optional[str] = None,
        source_identifier: Optional[str] = None,
        extraction_warnings: Optional[str] = None,
        ingestion_status: str = "REGISTERED",
    ) -> Document:
        """Register a new document in the authoritative registry."""
        doc = Document(
            id=document_id,
            company_id=company_id,
            source_type=source_type,
            source_url=source_url,
            source_identifier=source_identifier,
            original_filename=original_filename,
            stored_path=stored_path,
            sha256_hash=sha256_hash,
            title=title or original_filename,
            document_type=document_type,
            jurisdiction=jurisdiction,
            reporting_period=reporting_period,
            extraction_warnings=extraction_warnings,
            ingestion_status=ingestion_status,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def update_document_status(
        self,
        document_id: str,
        status: str,
        page_count: Optional[int] = None,
        extraction_warnings: Optional[str] = None,
        parser_version: Optional[str] = None,
    ) -> Optional[Document]:
        """Update ingestion status and warnings for a document."""
        doc = self.get_document_by_id(document_id)
        if doc:
            doc.ingestion_status = status
            if page_count is not None:
                doc.page_count = page_count
            if extraction_warnings is not None:
                doc.extraction_warnings = extraction_warnings
            if parser_version is not None:
                doc.parser_version = parser_version
            self.db.commit()
            self.db.refresh(doc)
        return doc

    # --- Document Chunk Operations ---

    def create_chunk(
        self,
        chunk_id: str,
        document_id: str,
        page_number: int,
        chunk_index: int,
        content: str,
        chunk_type: str = "narrative",
        section_title: Optional[str] = None,
        token_count: int = 0,
        qdrant_point_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DocumentChunk:
        """Create a single document chunk."""
        chunk = DocumentChunk(
            id=chunk_id,
            document_id=document_id,
            page_number=page_number,
            chunk_index=chunk_index,
            chunk_type=chunk_type,
            section_title=section_title,
            content=content,
            token_count=token_count,
            qdrant_point_id=qdrant_point_id,
        )
        if metadata:
            chunk.metadata_dict = metadata
        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    def bulk_create_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Efficiently persist a collection of chunks."""
        self.db.add_all(chunks)
        self.db.commit()

    def get_chunks_by_document(self, document_id: str) -> List[DocumentChunk]:
        """Retrieve all ordered chunks for a document."""
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        return list(self.db.scalars(stmt).all())

    def get_chunks_by_ids(self, chunk_ids: List[str]) -> List[DocumentChunk]:
        """Retrieve chunks by their IDs."""
        if not chunk_ids:
            return []
        stmt = select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids))
        return list(self.db.scalars(stmt).all())

    def get_chunk_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Retrieve a single chunk by ID."""
        return self.db.get(DocumentChunk, chunk_id)

    def delete_chunks_by_document(self, document_id: str) -> int:
        """Idempotently clear existing chunks for a document before re-indexing."""
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    # --- Financial Fact Operations ---

    def create_fact(
        self,
        metric_name: str,
        numeric_value: Decimal,
        company_id: Optional[int] = None,
        source_document_id: Optional[str] = None,
        currency: str = "USD",
        unit_scale: str = "ONES",
        period_type: str = "annual",
        period_start_date: Optional[datetime] = None,
        period_end_date: Optional[datetime] = None,
        instant_date: Optional[datetime] = None,
        reporting_scope: str = "consolidated",
        accounting_basis: str = "GAAP",
        page_number: Optional[int] = None,
        table_reference: Optional[str] = None,
        extraction_method: str = "table_parser",
        validation_status: str = "UNVERIFIED",
    ) -> FinancialFact:
        """Create a canonical financial fact with exact provenance."""
        fact = FinancialFact(
            company_id=company_id,
            source_document_id=source_document_id,
            metric_name=metric_name,
            numeric_value=numeric_value,
            currency=currency,
            unit_scale=unit_scale,
            period_type=period_type,
            period_start_date=period_start_date,
            period_end_date=period_end_date,
            instant_date=instant_date,
            reporting_scope=reporting_scope,
            accounting_basis=accounting_basis,
            page_number=page_number,
            table_reference=table_reference,
            extraction_method=extraction_method,
            validation_status=validation_status,
        )
        self.db.add(fact)
        self.db.commit()
        self.db.refresh(fact)
        return fact

    def bulk_create_facts(self, facts: List[FinancialFact]) -> None:
        """Efficiently persist a collection of financial facts."""
        self.db.add_all(facts)
        self.db.commit()

    def get_facts_by_company(
        self, company_id: int, metric_name: Optional[str] = None
    ) -> List[FinancialFact]:
        """Query structured facts for a company, optionally filtered by metric."""
        stmt = select(FinancialFact).where(FinancialFact.company_id == company_id)
        if metric_name:
            stmt = stmt.where(FinancialFact.metric_name == metric_name)
        return list(self.db.scalars(stmt).all())

    def get_facts_by_document(self, document_id: str) -> List[FinancialFact]:
        """Query facts extracted from a specific document."""
        stmt = select(FinancialFact).where(FinancialFact.source_document_id == document_id)
        return list(self.db.scalars(stmt).all())

    def delete_facts_by_document(self, document_id: str) -> int:
        """Idempotently clear existing facts for a document before re-extraction."""
        stmt = delete(FinancialFact).where(FinancialFact.source_document_id == document_id)
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    # --- Research Run Operations ---

    def get_run_by_id(self, run_id: str) -> Optional[ResearchRun]:
        """Fetch research run by ID."""
        return self.db.get(ResearchRun, run_id)

    def create_run(
        self,
        run_id: str,
        research_question: str,
        company_id: Optional[int] = None,
        jurisdiction: str = "US",
        requested_periods: Optional[List[str]] = None,
        input_document_ids: Optional[List[str]] = None,
        status: str = "pending",
    ) -> ResearchRun:
        """Create a new research run with initialized status."""
        run = ResearchRun(
            id=run_id,
            research_question=research_question,
            company_id=company_id,
            jurisdiction=jurisdiction,
            status=status,
        )
        run.requested_periods = requested_periods or []
        run.input_document_ids = input_document_ids or []
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_run_status(
        self, run_id: str, status: str, error_summary: Optional[str] = None
    ) -> Optional[ResearchRun]:
        """Update run status and optional error summary."""
        run = self.get_run_by_id(run_id)
        if run:
            run.status = status
            if error_summary is not None:
                run.error_summary = error_summary
            run.updated_at = utc_now()
            self.db.commit()
            self.db.refresh(run)
        return run

    # --- Run Event Operations ---

    def create_event(
        self,
        run_id: str,
        node_or_stage: str,
        status_or_code: str = "INFO",
        details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
        model_or_parser_version: Optional[str] = None,
    ) -> RunEvent:
        """Record an immutable audit event for a research run."""
        event = RunEvent(
            run_id=run_id,
            node_or_stage=node_or_stage,
            status_or_code=status_or_code,
            duration_ms=duration_ms,
            model_or_parser_version=model_or_parser_version,
        )
        event.details = details or {}
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_events_by_run_id(self, run_id: str) -> List[RunEvent]:
        """Fetch chronological audit trail for a research run."""
        stmt = select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.event_timestamp)
        return list(self.db.scalars(stmt).all())

    # --- Evidence Relationship Operations ---

    def create_relationship(
        self,
        source_id: str,
        source_type: str,
        target_id: str,
        target_type: str,
        relationship_type: str,
        document_id: Optional[str] = None,
        page_number: Optional[int] = None,
        reporting_period: Optional[str] = None,
        confidence_score: Decimal = Decimal("1.0"),
        validation_status: str = "candidate",
        extraction_method: str = "deterministic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvidenceRelationship:
        """Persist a source-grounded graph relationship between financial entities."""
        import json
        rel = EvidenceRelationship(
            source_id=source_id,
            source_type=source_type,
            target_id=target_id,
            target_type=target_type,
            relationship_type=relationship_type,
            document_id=document_id,
            page_number=page_number,
            reporting_period=reporting_period,
            confidence_score=confidence_score,
            validation_status=validation_status,
            extraction_method=extraction_method,
            metadata_json=json.dumps(metadata or {}),
        )
        self.db.add(rel)
        self.db.commit()
        self.db.refresh(rel)
        return rel

    def get_relationships_by_entity(
        self, entity_id: str, relationship_type: Optional[str] = None
    ) -> List[EvidenceRelationship]:
        """Retrieve 1-hop relationships where entity is source or target."""
        stmt = select(EvidenceRelationship).where(
            (EvidenceRelationship.source_id == entity_id) | (EvidenceRelationship.target_id == entity_id)
        )
        if relationship_type:
            stmt = stmt.where(EvidenceRelationship.relationship_type == relationship_type)
        return list(self.db.scalars(stmt).all())

    def traverse_evidence_subgraph(
        self, seed_entity_ids: List[str], max_hops: int = 2, max_nodes: int = 50
    ) -> List[EvidenceRelationship]:
        """Bounded multi-hop traversal along verified entity connections."""
        visited_entities = set(seed_entity_ids)
        current_layer = set(seed_entity_ids)
        discovered_relationships: List[EvidenceRelationship] = []

        for _ in range(max_hops):
            if not current_layer or len(discovered_relationships) >= max_nodes:
                break
            stmt = select(EvidenceRelationship).where(
                (EvidenceRelationship.source_id.in_(current_layer))
                | (EvidenceRelationship.target_id.in_(current_layer))
            )
            layer_rels = list(self.db.scalars(stmt).all())
            next_layer = set()
            for r in layer_rels:
                if r not in discovered_relationships:
                    discovered_relationships.append(r)
                if r.source_id not in visited_entities:
                    next_layer.add(r.source_id)
                    visited_entities.add(r.source_id)
                if r.target_id not in visited_entities:
                    next_layer.add(r.target_id)
                    visited_entities.add(r.target_id)
                if len(discovered_relationships) >= max_nodes:
                    break
            current_layer = next_layer

        return discovered_relationships

    # --- Research Claim Operations ---

    def create_claim(
        self,
        claim_id: str,
        run_id: str,
        claim_text: str,
        claim_type: str = "reported_fact",
        materiality: str = "MEDIUM",
        evidence_references: Optional[List[str]] = None,
        fact_ids: Optional[List[int]] = None,
        calculation_id: Optional[str] = None,
        verification_status: str = "needs_human_review",
        verification_notes: Optional[str] = None,
    ) -> ResearchClaim:
        """Persist or update a claim for multi-judge auditing and report generation."""
        existing = self.db.scalars(select(ResearchClaim).where(ResearchClaim.id == claim_id)).first()
        if existing:
            existing.run_id = run_id
            existing.claim_text = claim_text
            existing.claim_type = claim_type
            existing.materiality = materiality
            existing.calculation_id = calculation_id
            existing.verification_status = verification_status
            existing.verification_notes = verification_notes
            existing.evidence_references = evidence_references or []
            existing.fact_ids = fact_ids or []
            self.db.commit()
            self.db.refresh(existing)
            return existing

        claim = ResearchClaim(
            id=claim_id,
            run_id=run_id,
            claim_text=claim_text,
            claim_type=claim_type,
            materiality=materiality,
            calculation_id=calculation_id,
            verification_status=verification_status,
            verification_notes=verification_notes,
        )
        claim.evidence_references = evidence_references or []
        claim.fact_ids = fact_ids or []
        self.db.add(claim)
        self.db.commit()
        self.db.refresh(claim)
        return claim

    def get_claims_by_run_id(self, run_id: str) -> List[ResearchClaim]:
        """Fetch all claims associated with a research run."""
        stmt = select(ResearchClaim).where(ResearchClaim.run_id == run_id)
        return list(self.db.scalars(stmt).all())

    def update_claim_verification(
        self, claim_id: str, status: str, notes: Optional[str] = None
    ) -> Optional[ResearchClaim]:
        """Update audit verdict for a claim."""
        stmt = select(ResearchClaim).where(ResearchClaim.id == claim_id)
        claim = self.db.scalars(stmt).first()
        if claim:
            claim.verification_status = status
            if notes is not None:
                claim.verification_notes = notes
            self.db.commit()
            self.db.refresh(claim)
        return claim

    # --- Research Report Operations ---

    def create_or_update_report(
        self,
        report_id: str,
        run_id: str,
        executive_summary: str,
        report_markdown: str,
        structured_data: Dict[str, Any],
        verification_status: str = "VERIFIED",
        quality_score: Optional[Decimal] = None,
    ) -> ResearchReport:
        """Persist synthesized research report."""
        stmt = select(ResearchReport).where(ResearchReport.run_id == run_id)
        report = self.db.scalars(stmt).first()
        if not report:
            report = ResearchReport(
                id=report_id,
                run_id=run_id,
                executive_summary=executive_summary,
                report_markdown=report_markdown,
                verification_status=verification_status,
                quality_score=quality_score,
            )
            report.structured_data = structured_data
            self.db.add(report)
        else:
            report.executive_summary = executive_summary
            report.report_markdown = report_markdown
            report.structured_data = structured_data
            report.verification_status = verification_status
            if quality_score is not None:
                report.quality_score = quality_score
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_report_by_run_id(self, run_id: str) -> Optional[ResearchReport]:
        """Retrieve persisted report by run_id."""
        stmt = select(ResearchReport).where(ResearchReport.run_id == run_id)
        return self.db.scalars(stmt).first()
