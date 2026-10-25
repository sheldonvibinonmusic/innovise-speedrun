"""Document Upload and Registration Routes.

Endpoints:
- POST /api/documents/upload (Safe multipart PDF upload, registration, and optional pipeline processing)
- POST /api/documents/{document_id}/process (Explicit trigger for parsing & indexing)
- GET /api/documents/{document_id} (Retrieve document status, chunk count, and facts)
"""

import hashlib
import os
from pathlib import Path
import re
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_repository
from app.config import settings
from app.db.models import Document
from app.db.repository import Repository
from app.db.session import get_db
from app.ingestion.document_registry import ingestion_service
from app.ingestion.quality_checks import (
    assess_document_content,
    generate_page_summaries,
    load_document_summary_sidecar,
    save_document_summary_sidecar,
)
from app.schemas.documents import (
    DocumentAssessmentSchema,
    DocumentMetadataResponse,
    DocumentPagesResponse,
    DocumentProcessResponse,
    DocumentUploadResponse,
    PageSummarySchema,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


def sanitize_filename(filename: str) -> str:
    """Sanitize user-provided filename to prevent path traversal or filesystem corruption."""
    clean = os.path.basename(filename)
    clean = re.sub(r"[^\w\.\-\_]", "_", clean)
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".pptx"):
        ext = ".pdf"
    if not clean or clean.startswith("."):
        clean = f"document_{uuid.uuid4().hex[:8]}{ext}"
    return clean


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and register financial PDF documents",
    description="Validates PDF signature, enforces size bounds, computes SHA-256, and registers in SQLite.",
)
async def upload_documents(
    files: List[UploadFile] = File(..., description="One or more PDF files to upload"),
    company_ticker: Optional[str] = Form(None, description="Optional associated stock ticker"),
    reporting_period: Optional[str] = Form(None, description="Optional fiscal period (e.g., FY24)"),
    document_type: str = Form("10-K", description="Document type (10-K, 10-Q, Annual Report)"),
    jurisdiction: str = Form("US", description="Regulatory jurisdiction"),
    process_now: bool = Form(True, description="Immediately parse, chunk, and index into hybrid RAG"),
    db: Session = Depends(get_db),
    repo: Repository = Depends(get_repository),
):
    """Safely stream, validate, hash, persist, and optionally index uploaded PDF documents."""
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files uploaded. At least one PDF document is required.",
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024

    # Resolve company ID if ticker provided
    company_id = None
    if company_ticker:
        company = repo.get_company_by_ticker(company_ticker)
        if company:
            company_id = company.id
        else:
            new_comp = repo.create_company(
                name=company_ticker.upper(),
                ticker=company_ticker.upper(),
                jurisdiction=jurisdiction,
            )
            company_id = new_comp.id

    registered_docs: List[DocumentMetadataResponse] = []

    for file in files:
        original_name = file.filename or "uploaded_file.pdf"
        sanitized_name = sanitize_filename(original_name)

        hasher = hashlib.sha256()
        total_bytes = 0
        header_bytes = b""
        chunk_size = 64 * 1024
        temp_destination = settings.upload_dir / f"tmp_{uuid.uuid4().hex}_{sanitized_name}"

        try:
            with open(temp_destination, "wb") as f_out:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break

                    if len(header_bytes) < 1024:
                        header_bytes += chunk[: 1024 - len(header_bytes)]

                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"File '{original_name}' exceeds maximum permitted upload limit of {settings.max_upload_mb} MB.",
                        )

                    hasher.update(chunk)
                    f_out.write(chunk)

            if total_bytes == 0:
                if temp_destination.exists():
                    temp_destination.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Uploaded file '{original_name}' is empty (0 bytes).",
                )

            is_pdf = header_bytes.startswith(b"%PDF-")
            is_pptx = header_bytes.startswith(b"PK\x03\x04") and (sanitized_name.lower().endswith(".pptx") or original_name.lower().endswith(".pptx"))

            if not (is_pdf or is_pptx):
                if temp_destination.exists():
                    temp_destination.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file format for '{original_name}'. The file signature does not match a valid PDF document or supported PowerPoint presentation.",
                )

            sha256_digest = hasher.hexdigest()

            # Check for duplicate
            existing_doc = repo.get_document_by_hash(sha256_digest)
            if existing_doc:
                if temp_destination.exists():
                    temp_destination.unlink()

                chunks_count = len(repo.get_chunks_by_document(existing_doc.id))
                facts_count = len(repo.get_facts_by_document(existing_doc.id))

                dup_classification = None
                if existing_doc.ingestion_status == "NON_FINANCIAL":
                    dup_classification = "NON_FINANCIAL"
                elif existing_doc.ingestion_status == "NEEDS_REVIEW":
                    dup_classification = "UNCERTAIN"
                elif existing_doc.ingestion_status in ("INDEXED", "PARTIALLY_PROCESSED"):
                    dup_classification = "FINANCIAL"

                registered_docs.append(
                    DocumentMetadataResponse(
                        document_id=existing_doc.id,
                        filename=existing_doc.original_filename,
                        file_size_bytes=total_bytes,
                        sha256_hash=existing_doc.sha256_hash,
                        status=existing_doc.ingestion_status,
                        classification=dup_classification,
                        source_type=existing_doc.source_type,
                        jurisdiction=existing_doc.jurisdiction,
                        reporting_period=existing_doc.reporting_period,
                        page_count=existing_doc.page_count,
                        chunks_indexed=chunks_count,
                        facts_extracted=facts_count,
                        warnings="Duplicate document detected. Reusing existing registered document record.",
                        is_duplicate=True,
                        registered_at=existing_doc.retrieval_timestamp,
                    )
                )
                continue

            doc_id = f"doc_{uuid.uuid4().hex[:12]}"
            permanent_name = f"{sha256_digest[:16]}_{sanitized_name}"
            permanent_path = settings.upload_dir / permanent_name

            if temp_destination.exists():
                temp_destination.replace(permanent_path)

            try:
                db_doc = repo.create_document(
                    document_id=doc_id,
                    original_filename=original_name,
                    stored_path=str(permanent_path),
                    sha256_hash=sha256_digest,
                    source_type="user_upload",
                    company_id=company_id,
                    document_type="Presentation" if is_pptx and document_type == "10-K" else document_type,
                    jurisdiction=jurisdiction,
                    reporting_period=reporting_period,
                    ingestion_status="REGISTERED",
                    extraction_warnings="Registered in document store.",
                )
            except Exception as db_err:
                if permanent_path.exists():
                    permanent_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database registration failed for '{original_name}': {str(db_err)}",
                )

            # Trigger processing if requested
            chunks_count = 0
            facts_count = 0
            page_count = None
            doc_status = "REGISTERED"
            classification_val = None
            warnings_text = db_doc.extraction_warnings

            if process_now:
                proc_res = ingestion_service.process_document(doc_id, db)
                doc_status = proc_res.get("status", "FAILED")
                classification_val = proc_res.get("classification")
                chunks_count = proc_res.get("chunks_indexed", 0)
                facts_count = proc_res.get("facts_extracted", 0)
                page_count = proc_res.get("page_count")
                if proc_res.get("warnings"):
                    warnings_text = "; ".join(proc_res["warnings"])

            registered_docs.append(
                DocumentMetadataResponse(
                    document_id=db_doc.id,
                    filename=db_doc.original_filename,
                    file_size_bytes=total_bytes,
                    sha256_hash=db_doc.sha256_hash,
                    status=doc_status,
                    classification=classification_val,
                    source_type=db_doc.source_type,
                    jurisdiction=db_doc.jurisdiction,
                    reporting_period=db_doc.reporting_period,
                    page_count=page_count,
                    chunks_indexed=chunks_count,
                    facts_extracted=facts_count,
                    warnings=warnings_text,
                    is_duplicate=False,
                    registered_at=db_doc.retrieval_timestamp,
                )
            )

        except HTTPException:
            if temp_destination.exists():
                temp_destination.unlink()
            raise
        except Exception as exc:
            if temp_destination.exists():
                temp_destination.unlink()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred while processing '{original_name}': {str(exc)}",
            )

    return DocumentUploadResponse(
        uploaded_documents=registered_docs,
        message=f"Successfully processed {len(registered_docs)} document(s).",
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessResponse,
    summary="Process registered document through ingestion & indexing pipeline",
)
def process_registered_document(
    document_id: str,
    db: Session = Depends(get_db),
    repo: Repository = Depends(get_repository),
):
    """Trigger document layout parsing, fact extraction, and hybrid RAG indexing."""
    doc = repo.get_document_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    proc_res = ingestion_service.process_document(document_id, db)
    assessment_data = proc_res.get("assessment")
    assessment_schema = None
    if assessment_data:
        assessment_schema = DocumentAssessmentSchema(
            classification=assessment_data.get("classification", "UNCERTAIN"),
            signals=assessment_data.get("signals", []),
            warnings=assessment_data.get("warnings", []),
            heuristic_score=assessment_data.get("heuristic_score", 0.0),
        )

    return DocumentProcessResponse(
        document_id=document_id,
        status=proc_res.get("status", "FAILED"),
        classification=proc_res.get("classification"),
        page_count=proc_res.get("page_count", 0),
        chunks_indexed=proc_res.get("chunks_indexed", 0),
        facts_extracted=proc_res.get("facts_extracted", 0),
        warnings=proc_res.get("warnings", []),
        assessment=assessment_schema,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentMetadataResponse,
    summary="Retrieve document metadata and ingestion status",
)
def get_document_details(
    document_id: str,
    repo: Repository = Depends(get_repository),
):
    """Get metadata, page count, and indexing status for a document."""
    doc = repo.get_document_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    chunks_count = len(repo.get_chunks_by_document(document_id))
    facts_count = len(repo.get_facts_by_document(document_id))
    stored_path = Path(doc.stored_path)
    file_size = stored_path.stat().st_size if stored_path.exists() else 0

    classification = None
    if doc.ingestion_status == "NON_FINANCIAL":
        classification = "NON_FINANCIAL"
    elif doc.ingestion_status == "NEEDS_REVIEW":
        classification = "UNCERTAIN"
    elif doc.ingestion_status in ("INDEXED", "PARTIALLY_PROCESSED"):
        classification = "FINANCIAL"
    else:
        sidecar = load_document_summary_sidecar(stored_path)
        if sidecar and "assessment" in sidecar:
            classification = sidecar["assessment"].get("classification")

    return DocumentMetadataResponse(
        document_id=doc.id,
        filename=sanitize_filename(doc.original_filename),
        file_size_bytes=file_size,
        sha256_hash=doc.sha256_hash,
        status=doc.ingestion_status,
        classification=classification,
        source_type=doc.source_type,
        jurisdiction=doc.jurisdiction,
        reporting_period=doc.reporting_period,
        page_count=doc.page_count,
        chunks_indexed=chunks_count,
        facts_extracted=facts_count,
        warnings=doc.extraction_warnings,
        is_duplicate=False,
        registered_at=doc.retrieval_timestamp,
    )


@router.get(
    "/{document_id}/pages",
    response_model=DocumentPagesResponse,
    summary="Retrieve page-by-page extraction summaries and assessment",
    description="Returns grounded, extractive page summaries, table counts, character stats, and content classification.",
)
def get_document_pages(
    document_id: str,
    repo: Repository = Depends(get_repository),
):
    """Retrieve structured page-by-page extraction summaries for a document."""
    doc = repo.get_document_by_id(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    stored_path = Path(doc.stored_path)
    if not stored_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file for '{document_id}' is not accessible on disk.",
        )

    # Attempt to load sidecar JSON
    sidecar = load_document_summary_sidecar(stored_path)
    if sidecar and "assessment" in sidecar and "pages" in sidecar:
        assessment_data = sidecar["assessment"]
        pages_data = sidecar["pages"]
    else:
        # Generate dynamically if sidecar is not present
        parsed_doc = ingestion_service.parser.parse_document(stored_path)
        assessment = assess_document_content(parsed_doc)
        page_summaries = generate_page_summaries(parsed_doc)
        save_document_summary_sidecar(stored_path, assessment, page_summaries)
        assessment_data = assessment.to_dict()
        pages_data = [p.to_dict() for p in page_summaries]

    assessment_schema = DocumentAssessmentSchema(
        classification=assessment_data.get("classification", "UNCERTAIN"),
        signals=assessment_data.get("signals", []),
        warnings=assessment_data.get("warnings", []),
        heuristic_score=assessment_data.get("heuristic_score", 0.0),
    )

    page_schemas = [
        PageSummarySchema(
            page_number=p.get("page_number", idx + 1),
            summary=p.get("summary", ""),
            content_kind=p.get("content_kind", "text"),
            table_count=p.get("table_count", 0),
            extracted_characters=p.get("extracted_characters", 0),
            warnings=p.get("warnings", []),
            summary_method=p.get("summary_method", "extractive_heuristic"),
        )
        for idx, p in enumerate(pages_data)
    ]

    return DocumentPagesResponse(
        document_id=doc.id,
        original_filename=sanitize_filename(doc.original_filename),
        page_count=len(page_schemas) or (doc.page_count or 0),
        summary_method="extractive_heuristic",
        assessment=assessment_schema,
        pages=page_schemas,
    )
