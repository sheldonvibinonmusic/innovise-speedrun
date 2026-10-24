"""Financial Table Extraction and Canonical Fact Normalization.

Extracts structured tables and canonical financial facts (Revenue, Net Income,
Operating Cash Flow, Balance Sheet items) with exact decimal precision and provenance.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, List, Optional, Tuple

from app.db.models import FinancialFact
from app.ingestion.parser import ParsedDocument, ParsedTable

# Standard financial metric aliases mapped to canonical concept names
CANONICAL_METRIC_MAP: Dict[str, str] = {
    # Revenue concepts
    "total revenue": "TotalRevenue",
    "revenue": "TotalRevenue",
    "revenues": "TotalRevenue",
    "total net sales": "TotalRevenue",
    "net sales": "TotalRevenue",
    "sales": "TotalRevenue",
    # Operating Income
    "operating income": "OperatingIncome",
    "operating profit": "OperatingIncome",
    "income from operations": "OperatingIncome",
    # Net Income
    "net income": "NetIncome",
    "net earnings": "NetIncome",
    "net income (loss)": "NetIncome",
    "net loss": "NetIncome",
    # Cash Flow
    "cash provided by operating activities": "OperatingCashFlow",
    "net cash provided by operating activities": "OperatingCashFlow",
    "operating cash flow": "OperatingCashFlow",
    "cash from operations": "OperatingCashFlow",
    "capital expenditures": "CapitalExpenditures",
    "additions to property, plant and equipment": "CapitalExpenditures",
    "payments for property, plant and equipment": "CapitalExpenditures",
    # Balance Sheet
    "cash and cash equivalents": "CashAndCashEquivalents",
    "total cash and cash equivalents": "CashAndCashEquivalents",
    "total assets": "TotalAssets",
    "total liabilities": "TotalLiabilities",
    "stockholders' equity": "StockholdersEquity",
    "shareholders' equity": "StockholdersEquity",
    "total stockholders' equity": "StockholdersEquity",
    "long-term debt": "LongTermDebt",
    "total debt": "TotalDebt",
}


def parse_clean_decimal(raw_val: str, scale_multiplier: Decimal = Decimal("1.0")) -> Optional[Decimal]:
    """Parse raw string into Decimal, handling currency symbols, commas, and negative parentheses."""
    if not raw_val or not isinstance(raw_val, str):
        return None

    clean = raw_val.strip()
    if clean in ("-", "—", "N/A", "NA", ""):
        return None

    is_negative = False
    if clean.startswith("(") and clean.endswith(")"):
        is_negative = True
        clean = clean[1:-1].strip()
    elif clean.startswith("-"):
        is_negative = True
        clean = clean[1:].strip()

    # Remove currency symbols and formatting commas
    clean = re.sub(r"[\$,\s]", "", clean)

    try:
        val = Decimal(clean) * scale_multiplier
        return -val if is_negative else val
    except (InvalidOperation, ValueError):
        return None


def detect_scale_and_currency(text: str) -> Tuple[Decimal, str, str]:
    """Detect scale multiplier (ONES, THOUSANDS, MILLIONS, BILLIONS) and currency from headers."""
    lower = text.lower()
    currency = "USD"
    if "inr" in lower or "rupee" in lower or "₹" in lower:
        currency = "INR"
    elif "eur" in lower or "€" in lower:
        currency = "EUR"

    scale_mult = Decimal("1.0")
    scale_name = "ONES"

    if "in millions" in lower or "in millions," in lower or "(millions)" in lower:
        scale_mult = Decimal("1000000")
        scale_name = "MILLIONS"
    elif "in thousands" in lower or "(thousands)" in lower:
        scale_mult = Decimal("1000")
        scale_name = "THOUSANDS"
    elif "in billions" in lower or "(billions)" in lower:
        scale_mult = Decimal("1000000000")
        scale_name = "BILLIONS"
    elif "in crore" in lower or "in crores" in lower:
        scale_mult = Decimal("10000000")
        scale_name = "CRORES"

    return scale_mult, scale_name, currency


class TableExtractor:
    """Extracts standardized tabular data and converts recognized accounting line items to facts."""

    def extract_facts_from_tables(
        self,
        tables: List[ParsedTable],
        document_id: str,
        company_id: Optional[int] = None,
        default_period: Optional[str] = None,
    ) -> List[FinancialFact]:
        """Convert recognizable financial table rows into canonical FinancialFact objects."""
        extracted_facts: List[FinancialFact] = []

        for table in tables:
            headers = [h.strip() for h in table.headers if h.strip()]
            header_str = " ".join(headers) + " " + (table.title or "")
            scale_mult, scale_name, currency = detect_scale_and_currency(header_str)

            for row in table.rows:
                if not row or len(row) < 2:
                    continue

                line_item = row[0].strip().lower()
                # Check for matching canonical metric
                matched_metric = None
                for alias, canonical in CANONICAL_METRIC_MAP.items():
                    if alias in line_item or line_item == alias:
                        matched_metric = canonical
                        break

                if not matched_metric:
                    continue

                # Parse subsequent columns as values
                for col_idx in range(1, len(row)):
                    raw_val = row[col_idx]
                    dec_val = parse_clean_decimal(raw_val, scale_mult)
                    if dec_val is None:
                        continue

                    # Attempt to resolve period from header if available
                    col_period = default_period or "FY"
                    if col_idx < len(table.headers):
                        cand_header = table.headers[col_idx].strip()
                        if re.search(r"\b20\d{2}\b", cand_header):
                            col_period = cand_header

                    fact = FinancialFact(
                        company_id=company_id,
                        source_document_id=document_id,
                        metric_name=matched_metric,
                        numeric_value=dec_val,
                        currency=currency,
                        unit_scale=scale_name,
                        period_type="annual" if "Q" not in str(col_period) else "quarterly",
                        reporting_scope="consolidated",
                        accounting_basis="GAAP",
                        page_number=table.page_number,
                        table_reference=table.title or f"Table_p{table.page_number}",
                        extraction_method="table_parser",
                        validation_status="UNVERIFIED",
                    )
                    extracted_facts.append(fact)

        return extracted_facts
