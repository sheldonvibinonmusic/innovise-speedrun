"""Common Enums, Error Envelopes, and Base Schemas.

Trustworthy Multi-Agent Financial Research System.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Standard lifecycle states for research runs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class GateStatus(str, Enum):
    """Deterministic verification gate verdicts."""
    PASS = "PASS"
    QUALIFY = "QUALIFY"
    RETRIEVE_MORE = "RETRIEVE_MORE"
    BLOCK = "BLOCK"
    INDETERMINATE = "INDETERMINATE"


class ErrorDetail(BaseModel):
    """Structured error detail representation."""
    code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Human-readable error explanation")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional contextual diagnostic metadata")


class ErrorResponse(BaseModel):
    """Standardized top-level error response envelope."""
    error: ErrorDetail


class HealthResponse(BaseModel):
    """System health and diagnostic status response."""
    status: str = Field(..., examples=["healthy"])
    version: str = Field(..., examples=["0.1.0"])
    environment: str = Field(..., examples=["development"])
    database_connected: bool = Field(..., examples=[True])
    optional_components: Dict[str, bool] = Field(
        default_factory=dict,
        description="Configuration status of optional components (LLM, Qdrant, etc.)",
    )
