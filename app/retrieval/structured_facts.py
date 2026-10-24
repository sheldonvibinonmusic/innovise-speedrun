"""Structured Financial Fact Retrieval.

Queries normalized accounting facts directly from SQLite to guarantee 100% numerical
truth for explicit financial metric queries, completely bypassing semantic approximation.
"""

from decimal import Decimal
import re
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Company, FinancialFact
from app.ingestion.tables import CANONICAL_METRIC_MAP


def extract_metric_from_query(query: str) -> Optional[str]:
    """Identify if the search query asks for a specific canonical financial metric."""
    q_lower = query.lower()
    for alias, canonical in CANONICAL_METRIC_MAP.items():
        if alias in q_lower:
            return canonical
    return None


def _format_decimal(val: Any) -> str:
    s = str(val)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


class StructuredFactRetriever:
    """Retrieves verified accounting facts from relational database."""

    def __init__(self, db: Session):
        self.db = db

    def search_facts(
        self,
        query: str,
        company_ticker: Optional[str] = None,
        period: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find authoritative tabular facts matching the query or metric."""
        metric_name = extract_metric_from_query(query)

        stmt = select(FinancialFact)

        if company_ticker:
            stmt = stmt.join(Company, FinancialFact.company_id == Company.id).where(
                Company.ticker == company_ticker.upper()
            )

        if metric_name:
            stmt = stmt.where(FinancialFact.metric_name == metric_name)

        if period:
            # Check if period matches table_reference or period_type
            stmt = stmt.where(
                (FinancialFact.table_reference.contains(period))
                | (FinancialFact.period_type == period)
            )

        results = list(self.db.scalars(stmt.limit(limit)).all())

        return [
            {
                "fact_id": f.id,
                "metric_name": f.metric_name,
                "numeric_value": _format_decimal(f.numeric_value),
                "currency": f.currency,
                "unit_scale": f.unit_scale,
                "period_type": f.period_type,
                "document_id": f.source_document_id,
                "page_number": f.page_number,
                "table_reference": f.table_reference,
                "validation_status": f.validation_status,
                "source_type": "structured_sqlite",
            }
            for f in results
        ]
