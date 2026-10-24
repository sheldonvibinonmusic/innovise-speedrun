"""Report Schemas.

Validates synthesized report structures, metrics scorecards, and discrepancy ledgers.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.claims import ClaimSchema


class MetricTableItem(BaseModel):
    """Calculated metric item in financial scorecard."""
    metric_name: str
    calculated_value: str
    formula: str
    verification_status: str


class DiscrepancyItem(BaseModel):
    """Detected contradiction or accounting anomaly."""
    discrepancy_id: str
    title: str
    description: str
    severity: str  # HIGH, MEDIUM, LOW
    source_references: List[str] = Field(default_factory=list)


class ReportResponse(BaseModel):
    """Complete research and decision-support report structure."""
    report_id: str
    run_id: str
    company_ticker: Optional[str] = None
    title: str
    executive_summary: str
    metrics_table: List[MetricTableItem] = Field(default_factory=list)
    claims: List[ClaimSchema] = Field(default_factory=list)
    discrepancies: List[DiscrepancyItem] = Field(default_factory=list)
    published_at: datetime = Field(default_factory=datetime.utcnow)
