"""Document Registry & Pipeline Ingestion Service.

Coordinates the shared ingestion pipeline across both manual uploads and SEC discoveries:
PDF File -> Validation -> Parsing -> Table/Fact Extraction -> Chunking -> Indexing -> INDEXED
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.db.models import Document
from app.db.repository import Repository
from app.ingestion.chunking import DocumentChunker
from app.ingestion.parser import DocumentParser, ParsedDocument
from app.ingestion.quality_checks import (
    assess_document_content,
    generate_page_summaries,
    save_document_summary_sidecar,
)
from app.ingestion.tables import TableExtractor
from app.retrieval.service import RetrievalService, retrieval_service


class DocumentIngestionService:
    """Manages parsing, fact extraction, and indexing of registered financial documents."""

    def __init__(
        self,
        parser: Optional[DocumentParser] = None,
        table_extractor: Optional[TableExtractor] = None,
        chunker: Optional[DocumentChunker] = None,
        retrieval: Optional[RetrievalService] = None,
    ):
        self.parser = parser or DocumentParser()
        self.table_extractor = table_extractor or TableExtractor()
        self.chunker = chunker or DocumentChunker()
        self.retrieval = retrieval or retrieval_service

    def process_document(
        self,
        document_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """Execute the end-to-end ingestion and indexing pipeline for a registered document."""
        repo = Repository(db)
        doc = repo.get_document_by_id(document_id)

        if not doc:
            raise ValueError(f"Document '{document_id}' does not exist in registry.")

        file_path = Path(doc.stored_path)
        if not file_path.exists():
            repo.update_document_status(
                document_id=document_id,
                status="FAILED",
                extraction_warnings=f"Stored file '{file_path}' not found on disk.",
            )
            return {"status": "FAILED", "error": "File not found on disk"}

        # 1. Update status to PARSING
        repo.update_document_status(document_id=document_id, status="PARSING")

        # 2. Parse Document Layout & Text (PDF or PPTX)
        parsed_doc = self.parser.parse_document(file_path=file_path, document_id=document_id)

        if parsed_doc.status == "FAILED":
            err_msg = "; ".join(parsed_doc.warnings) or "Failed to parse PDF document."
            repo.update_document_status(
                document_id=document_id,
                status="FAILED",
                page_count=parsed_doc.page_count,
                extraction_warnings=err_msg,
                parser_version=parsed_doc.parser_version,
            )
            return {"status": "FAILED", "error": err_msg}

        # 3. Assess document content & generate page summaries
        assessment = assess_document_content(parsed_doc)
        page_summaries = generate_page_summaries(parsed_doc)

        # Save sidecar JSON atomically within the upload directory
        save_document_summary_sidecar(
            stored_doc_path=file_path,
            assessment=assessment,
            pages=page_summaries,
        )

        all_warnings = list(parsed_doc.warnings)
        for w in assessment.warnings:
            if w not in all_warnings:
                all_warnings.append(w)
        warnings_str = "; ".join(all_warnings) if all_warnings else None

        # Content classification gate: block non-financial or uncertain documents from fact extraction and RAG indexing
        if assessment.classification in ("NON_FINANCIAL", "UNCERTAIN"):
            # Clean up any prior facts/chunks if document was re-processed
            repo.delete_facts_by_document(document_id)
            repo.delete_chunks_by_document(document_id)
            self.retrieval.vector_store.delete_document_vectors(document_id)

            status = "NON_FINANCIAL" if assessment.classification == "NON_FINANCIAL" else "NEEDS_REVIEW"
            repo.update_document_status(
                document_id=document_id,
                status=status,
                page_count=parsed_doc.page_count,
                extraction_warnings=warnings_str,
                parser_version=parsed_doc.parser_version,
            )
            return {
                "document_id": document_id,
                "status": status,
                "classification": assessment.classification,
                "page_count": parsed_doc.page_count,
                "chunks_indexed": 0,
                "facts_extracted": 0,
                "warnings": all_warnings,
                "assessment": assessment.to_dict(),
            }

        # 4. Document confirmed financial: Update status to PARSED
        repo.update_document_status(
            document_id=document_id,
            status="PARSED",
            page_count=parsed_doc.page_count,
            parser_version=parsed_doc.parser_version,
        )

        company_ticker = doc.company.ticker if doc.company else None

        # 5. Extract Canonical Financial Facts from Tables
        extracted_facts = self.table_extractor.extract_facts_from_tables(
            tables=parsed_doc.tables,
            document_id=document_id,
            company_id=doc.company_id,
            default_period=doc.reporting_period,
        )

        # 6. Create Page-Aware and Table-Aware Chunks
        chunks = self.chunker.chunk_document(
            doc=parsed_doc,
            company_ticker=company_ticker,
            reporting_period=doc.reporting_period,
        )

        # 7. Update status to INDEXING
        repo.update_document_status(document_id=document_id, status="INDEXING")

        # Idempotently clear prior facts & chunks for this document
        repo.delete_facts_by_document(document_id)
        repo.delete_chunks_by_document(document_id)
        self.retrieval.vector_store.delete_document_vectors(document_id)

        # Persist new facts & chunks to SQLite
        if extracted_facts:
            repo.bulk_create_facts(extracted_facts)
        if chunks:
            repo.bulk_create_chunks(chunks)

        # 8. Dense & Lexical Indexing
        if chunks:
            self.retrieval.index_document_chunks(
                chunks=chunks,
                company_ticker=company_ticker,
                reporting_period=doc.reporting_period,
            )

        # 9. Set final status
        final_status = "INDEXED" if parsed_doc.status == "COMPLETE" else "PARTIALLY_PROCESSED"

        repo.update_document_status(
            document_id=document_id,
            status=final_status,
            page_count=parsed_doc.page_count,
            extraction_warnings=warnings_str,
            parser_version=parsed_doc.parser_version,
        )

        return {
            "document_id": document_id,
            "status": final_status,
            "classification": assessment.classification,
            "page_count": parsed_doc.page_count,
            "chunks_indexed": len(chunks),
            "facts_extracted": len(extracted_facts),
            "warnings": all_warnings,
            "assessment": assessment.to_dict(),
        }


# Global default ingestion service
ingestion_service = DocumentIngestionService()
