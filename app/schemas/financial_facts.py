"""Financial Fact Schemas.

Validates structured numerical facts, units, and source references.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class FinancialFactSchema(BaseModel):
    """Normalized numerical financial fact."""

    id: Optional[int] = Field(default=None, description="Database fact identifier")
    company_id: Optional[int] = Field(default=None, description="Associated company ID")
    metric_name: str = Field(..., description="Canonical metric identifier", example="TotalRevenue")
    numeric_value: Decimal = Field(..., description="Exact numerical value with decimal precision")
    currency: str = Field(default="USD", description="Currency ISO code")
    unit_scale: str = Field(default="ONES", description="Scale factor: ONES, THOUSANDS, MILLIONS, BILLIONS")
    period_type: str = Field(default="annual", description="Period granularity: annual, quarterly, instant")
    reporting_scope: str = Field(default="consolidated", description="Consolidated or parent entity scope")
    accounting_basis: str = Field(default="GAAP", description="Accounting standard: GAAP or IFRS")
    source_document_id: Optional[str] = Field(default=None, description="Source Document ID")
    page_number: Optional[int] = Field(default=None, description="Source page number")
    table_reference: Optional[str] = Field(default=None, description="Table name or header")
    validation_status: str = Field(default="UNVERIFIED", description="Verification gate status")
