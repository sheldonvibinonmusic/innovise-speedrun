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
    is_duplicate: bool = Field(default=False, description="Whether this document was previously registered")
    registered_at: datetime = Field(default_factory=datetime.utcnow, description="Registration timestamp")


class DocumentUploadResponse(BaseModel):
    """Response envelope for POST /api/documents/upload."""

    uploaded_documents: List[DocumentMetadataResponse] = Field(
        ..., description="List of registered documents in this batch"
    )
    message: str = Field(..., description="Summary status message")


class DocumentProcessResponse(BaseModel):
    """Response envelope for POST /api/documents/{document_id}/process."""
    document_id: str
    status: str
    page_count: int
    chunks_indexed: int
    facts_extracted: int
    warnings: List[str] = Field(default_factory=list)
