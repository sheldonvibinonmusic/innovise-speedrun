"""Claim and Citation Schemas.

Validates analytical claims, citations, and judge evaluations.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.common import GateStatus


class CitationSchema(BaseModel):
    """Grounding citation linking a claim to a source document excerpt."""
    document_id: str
    page_number: int
    source_text_excerpt: str
    relevance_score: Optional[float] = None


class ClaimSchema(BaseModel):
    """Analytical assertion evaluated by verification judges."""
    claim_id: str
    analyst_role: str
    statement: str
    status: GateStatus = GateStatus.INDETERMINATE
    confidence_score: Optional[float] = None
    citation: Optional[CitationSchema] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
