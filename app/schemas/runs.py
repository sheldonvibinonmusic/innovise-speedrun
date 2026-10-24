"""Research Run Schemas.

Validates run execution responses, stage indicators, and audit event structures.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.common import RunStatus


class AuditEventResponse(BaseModel):
    """Structured representation of a research run audit event."""

    event_id: int = Field(..., description="Unique event identifier")
    run_id: str = Field(..., description="Associated research run ID")
    node_or_stage: str = Field(..., description="Workflow node or stage identifier")
    event_timestamp: datetime = Field(..., description="Timestamp of event occurrence")
    status_or_code: str = Field(..., description="Status classification (INFO, WARNING, ERROR)")
    duration_ms: Optional[int] = Field(default=None, description="Stage execution duration in milliseconds")
    details: Dict[str, Any] = Field(default_factory=dict, description="Metadata payload")
    model_or_parser_version: Optional[str] = Field(default=None, description="Model/parser version involved")


class RunResponse(BaseModel):
    """Payload contract for GET /api/runs/{run_id} and POST /api/runs response."""

    run_id: str = Field(..., description="Unique identifier for the research run", examples=["run_a1b2c3d4"])
    status: RunStatus = Field(..., description="Current lifecycle state of the research run")
    research_question: str = Field(..., description="Primary research inquiry")
    company_id: Optional[int] = Field(default=None, description="Internal company ID")
    company_ticker: Optional[str] = Field(default=None, description="Associated company ticker")
    jurisdiction: str = Field(default="US", description="Regulatory jurisdiction")
    current_stage: str = Field(default="initialization", description="Current execution stage")
    progress_percent: int = Field(default=0, ge=0, le=100, description="Completion percentage")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last state modification timestamp")
    error_summary: Optional[str] = Field(default=None, description="Diagnostic error summary if failed")
    requested_periods: List[str] = Field(default_factory=list, description="Target reporting periods")
    input_document_ids: List[str] = Field(default_factory=list, description="Input document identifiers")
    message: Optional[str] = Field(default=None, description="Human-readable status summary")


class RunTraceResponse(BaseModel):
    """Response containing the complete audit trail for a research run."""

    run_id: str = Field(..., description="Associated research run ID")
    total_events: int = Field(..., description="Total count of audit events")
    events: List[AuditEventResponse] = Field(..., description="Chronological audit records")
