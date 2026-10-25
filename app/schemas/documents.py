"""Document and File Upload Schemas.

Validates document registration responses, file hashes, and metadata contracts.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class DocumentMetadataResponse(BaseModel):
    """Metadata response describing a registered document."""

    document_id: str = Field(..., description="Unique immutable document ID")
    filename: str = Field(..., description="Original uploaded filename")
    file_size_bytes: int = Field(..., description="File size in bytes")
    sha256_hash: str = Field(..., description="Hexadecimal SHA-256 content digest")
    status: str = Field(default="REGISTERED", description="Ingestion pipeline state")
    source_type: str = Field(default="user_upload", description="Source of the document")
    jurisdiction: str = Field(default="US", description="Legal/regulatory jurisdiction")
    reporting_period: Optional[str] = Field(default=None, description="Filing fiscal period")
    page_count: Optional[int] = Field(default=None, description="Total document pages")
    chunks_indexed: int = Field(default=0, description="Total chunks indexed in Qdrant & BM25")
    facts_extracted: int = Field(default=0, description="Structured financial facts extracted")
    warnings: Optional[str] = Field(default=None, description="Ingestion warnings or notes")
    classification: Optional[str] = Field(default=None, description="FINANCIAL, NON_FINANCIAL, or UNCERTAIN")
    is_duplicate: bool = Field(default=False, description="Whether this document was previously registered")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="Registration timestamp")


class DocumentUploadResponse(BaseModel):
    """Response envelope for POST /api/documents/upload."""

    uploaded_documents: List[DocumentMetadataResponse] = Field(
        ..., description="List of registered documents in this batch"
    )
    message: str = Field(..., description="Summary status message")


class DocumentAssessmentSchema(BaseModel):
    """Schema for document financial assessment."""
    classification: str = Field(..., description="FINANCIAL, NON_FINANCIAL, or UNCERTAIN")
    signals: List[str] = Field(default_factory=list, description="Content-grounded evidence signals")
    warnings: List[str] = Field(default_factory=list, description="Quality and extraction warnings")
    heuristic_score: float = Field(default=0.0, description="Heuristic financial confidence score (0.0 - 1.0)")


class PageSummarySchema(BaseModel):
    """Schema for an individual page extraction summary."""
    page_number: int = Field(..., description="1-based page index")
    summary: str = Field(..., description="Extractive summary snippet for the page")
    content_kind: str = Field(..., description="text, table, mixed, or no_extractable_text")
    table_count: int = Field(default=0, description="Number of detected tables on this page")
    extracted_characters: int = Field(default=0, description="Total characters extracted from this page")
    warnings: List[str] = Field(default_factory=list, description="Page-specific extraction warnings")
    summary_method: str = Field(default="extractive_heuristic", description="Summary generation method")


class DocumentPagesResponse(BaseModel):
    """Response envelope for GET /api/documents/{document_id}/pages."""
    document_id: str = Field(..., description="Unique document ID")
    original_filename: str = Field(..., description="Original filename without server path exposure")
    page_count: int = Field(default=0, description="Total page count")
    summary_method: str = Field(default="extractive_heuristic", description="Method used to produce summaries")
    assessment: DocumentAssessmentSchema = Field(..., description="Document content assessment")
    pages: List[PageSummarySchema] = Field(default_factory=list, description="Ordered list of page summaries")


class DocumentProcessResponse(BaseModel):
    """Response envelope for POST /api/documents/{document_id}/process."""
    document_id: str
    status: str
    classification: Optional[str] = Field(default=None, description="FINANCIAL, NON_FINANCIAL, or UNCERTAIN")
    page_count: int
    chunks_indexed: int
    facts_extracted: int
    warnings: List[str] = Field(default_factory=list)
    assessment: Optional[DocumentAssessmentSchema] = Field(default=None, description="Assessment details if available")
