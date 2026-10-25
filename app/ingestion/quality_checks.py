"""Ingestion Quality, Content Assessment, and Page-by-Page Extraction Summaries.

Provides explainable rule-based document assessment to prevent non-financial documents
from entering financial fact extraction or financial vector/lexical retrieval indices.
Generates extractive, grounded page-by-page extraction summaries for every parsed page.
"""

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple

from app.config import settings
from app.ingestion.parser import ParsedDocument, ParsedPage, ParsedTable

# Recognizable regulatory filing and financial statement patterns
STRONG_STATEMENT_HEADERS = [
    r"\b(?:form\s+)?10-[kq]\b",
    r"\bform\s+20-f\b",
    r"\bform\s+8-k\b",
    r"\bannual\s+report\b",
    r"\bquarterly\s+report\b",
    r"\bconsolidated\s+statements?\s+of\s+(?:operations|income|earnings|loss)\b",
    r"\bconsolidated\s+balance\s+sheets?\b",
    r"\bconsolidated\s+statements?\s+of\s+cash\s+flows?\b",
    r"\bstatements?\s+of\s+financial\s+position\b",
    r"\bstatements?\s+of\s+stockholders['’]?\s+equity\b",
    r"\bstatements?\s+of\s+shareholders['’]?\s+equity\b",
    r"\bnotes\s+to\s+(?:consolidated\s+)?financial\s+statements\b",
    r"\bsecurities\s+and\s+exchange\s+commission\b",
    r"\binvestor\s+(?:presentation|strategic\s+overview|overview|deck)\b",
    r"\bearnings\s+(?:presentation|release|call|results)\b",
    r"\bfinancial\s+results\b",
    r"\boperating\s+performance\b",
]

# Canonical financial line item categories
ACCOUNTING_LINE_ITEMS = {
    "revenue": [
        r"\btotal\s+revenues?\b",
        r"\bnet\s+sales\b",
        r"\boperating\s+revenues?\b",
        r"\bnet\s+revenues?\b",
        r"\brevenues?\s+from\s+contracts\b",
        r"\bsegment\s+revenue\b",
        r"\bcloud\s+(?:segment\s+)?revenue\b",
        r"\brevenues?\b",
    ],
    "cost_margin": [
        r"\bcost\s+of\s+(?:sales|revenues?|goods\s+sold)\b",
        r"\bgross\s+profit\b",
        r"\bgross\s+margin\b",
        r"\boperating\s+margin\b",
        r"\bprofit\s+margin\b",
        r"\bmargin\s+durability\b",
    ],
    "operating_results": [
        r"\boperating\s+income\b",
        r"\bincome\s+from\s+operations\b",
        r"\boperating\s+expenses?\b",
        r"\bresearch\s+and\s+development\b",
        r"\bselling,\s+general\s+and\s+administrative\b",
        r"\boperating\s+performance\b",
        r"\boperating\s+results\b",
    ],
    "net_income": [
        r"\bnet\s+income\b",
        r"\bnet\s+earnings\b",
        r"\bnet\s+loss(?:es)?\b",
        r"\bearnings\s+per\s+share\b",
        r"\bdiluted\s+eps\b",
    ],
    "balance_sheet": [
        r"\btotal\s+assets\b",
        r"\bcurrent\s+assets\b",
        r"\btotal\s+liabilities\b",
        r"\bcurrent\s+liabilities\b",
        r"\bstockholders['’]?\s+equity\b",
        r"\bshareholders['’]?\s+equity\b",
        r"\bretained\s+earnings\b",
        r"\blong-term\s+debt\b",
        r"\bcash\s+and\s+cash\s+equivalents\b",
    ],
    "cash_flow": [
        r"\bcash\s+(?:provided\s+by|used\s+in)\s+operating\s+activities\b",
        r"\boperating\s+cash\s+flows?\b",
        r"\bcapital\s+expenditures\b",
        r"\badditions\s+to\s+property[,\s]+plant\b",
        r"\bpayments\s+for\s+property\s+and\s+equipment\b",
        r"\bfinancing\s+activities\b",
        r"\binvesting\s+activities\b",
    ],
}

PERIOD_REGEX = re.compile(
    r"\b(?:FY\s*['’`]?\d{2,4}|20\d{2}|19\d{2}|three\s+months\s+ended|twelve\s+months\s+ended|quarter\s+ended|fiscal\s+year)\b",
    re.IGNORECASE,
)
CURRENCY_VALUE_REGEX = re.compile(
    r"(?:\$\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?|\(\s*\$?\s*\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*\))",
)


@dataclass
class DocumentAssessment:
    """Structured assessment of a document's financial disclosure content."""

    classification: str  # "FINANCIAL", "NON_FINANCIAL", "UNCERTAIN"
    signals: List[str]
    warnings: List[str]
    heuristic_score: float  # Uncalibrated score (0.0 - 1.0) indicating signal strength

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PageSummaryRecord:
    """Ordered extraction summary for an individual document page."""

    page_number: int
    summary: str
    content_kind: str  # "text", "table", "mixed", "no_extractable_text"
    table_count: int
    extracted_characters: int
    warnings: List[str]
    summary_method: str = "extractive_heuristic"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def assess_document_content(parsed_doc: ParsedDocument) -> DocumentAssessment:
    """Assess whether a parsed document is a genuine financial disclosure.

    Evaluates content independently across full text and structured tables:
    - Never uses filename, ticker, reporting_period, or default document_type as evidence.
    - Avoids false positives on isolated dollar signs or the lone word 'financial'.
    """
    signals: List[str] = []
    warnings: List[str] = list(parsed_doc.warnings)

    total_chars = len(parsed_doc.full_text.strip())
    total_pages = parsed_doc.page_count or len(parsed_doc.pages)

    if total_pages == 0 or total_chars == 0:
        return DocumentAssessment(
            classification="UNCERTAIN",
            signals=["Document contains zero extractable digital text."],
            warnings=["No digital text extracted; document may be blank, scanned image, or corrupted."],
            heuristic_score=0.0,
        )

    full_lower = parsed_doc.full_text.lower()

    # 1. Statement and filing header signals
    detected_headers = []
    for pat in STRONG_STATEMENT_HEADERS:
        m = re.search(pat, full_lower)
        if m:
            detected_headers.append(m.group(0).strip())

    if detected_headers:
        unique_headers = list(dict.fromkeys(detected_headers))[:4]
        signals.append(f"Identified regulatory/accounting disclosure headings: {', '.join(unique_headers)}")

    # 2. Accounting line item category breadth
    detected_categories: Dict[str, List[str]] = {}
    for cat, patterns in ACCOUNTING_LINE_ITEMS.items():
        cat_matches = []
        for pat in patterns:
            m = re.search(pat, full_lower)
            if m:
                cat_matches.append(m.group(0).strip())
        if cat_matches:
            detected_categories[cat] = cat_matches

    if detected_categories:
        summary_cats = [f"{k} ({len(v)} term(s))" for k, v in detected_categories.items()]
        signals.append(f"Detected core accounting line items across categories: {', '.join(summary_cats)}")

    # 3. Numeric financial tables with period/year headers or accounting headers
    financial_tables_count = 0
    table_details = []
    for tbl in parsed_doc.tables:
        header_text = (" ".join(tbl.headers) + " " + (tbl.title or "")).lower()
        has_period = bool(PERIOD_REGEX.search(header_text))
        has_header_accounting = any(
            re.search(pat, header_text)
            for cat_patterns in ACCOUNTING_LINE_ITEMS.values()
            for pat in cat_patterns
        )

        # Inspect rows for accounting terms and numbers
        row_accounting_terms = 0
        numeric_cells = 0
        for row in tbl.rows:
            row_str = " ".join(row).lower()
            if any(re.search(pat, row_str) for cat_patterns in ACCOUNTING_LINE_ITEMS.values() for pat in cat_patterns):
                row_accounting_terms += 1
            for cell in row:
                if re.search(r"\d{2,}", cell) or CURRENCY_VALUE_REGEX.search(cell):
                    numeric_cells += 1

        if (
            (has_period and numeric_cells >= 2)
            or (row_accounting_terms >= 1 and numeric_cells >= 2)
            or (has_header_accounting and numeric_cells >= 2)
        ):
            financial_tables_count += 1
            t_name = tbl.title or f"Table on Page {tbl.page_number}"
            table_details.append(f"{t_name} (rows: {len(tbl.rows)})")

    if financial_tables_count > 0:
        signals.append(f"Found {financial_tables_count} structured financial table(s) with numeric accounting data: {', '.join(table_details[:3])}")

    # 4. Currency and monetary disclosures count
    currency_hits = len(CURRENCY_VALUE_REGEX.findall(parsed_doc.full_text))
    if currency_hits >= 2:
        signals.append(f"Found {currency_hits} formatted currency value disclosures.")

    # Rule-based synthesis
    strong_header_count = len(detected_headers)
    cat_count = len(detected_categories)

    # Heuristic scoring (strictly uncalibrated score 0.0 - 1.0, not a probability)
    raw_points = 0.0
    if strong_header_count >= 1:
        raw_points += 0.35
    if strong_header_count >= 2:
        raw_points += 0.15
    raw_points += min(0.35, cat_count * 0.08)
    if financial_tables_count >= 1:
        raw_points += 0.25
    if financial_tables_count >= 3:
        raw_points += 0.10
    if currency_hits >= 2:
        raw_points += 0.05
    heuristic_score = min(1.0, round(raw_points, 2))

    # Balanced classification decision
    is_financial = (
        (strong_header_count >= 1 and (cat_count >= 1 or financial_tables_count >= 1))
        or (financial_tables_count >= 1 and (cat_count >= 1 or currency_hits >= 2))
        or (cat_count >= 2 and (currency_hits >= 2 or strong_header_count >= 1))
        or (cat_count >= 3)
    )

    is_non_financial = (
        strong_header_count == 0
        and cat_count == 0
        and financial_tables_count == 0
        and currency_hits == 0
    )

    if is_financial:
        classification = "FINANCIAL"
    elif is_non_financial:
        classification = "NON_FINANCIAL"
        warnings.append("Document lacks verifiable accounting statements, structured financial tables, or regulatory disclosure line items.")
    else:
        classification = "UNCERTAIN"
        warnings.append(
            "Document contains sparse or isolated financial mentions without full regulatory statement structure or accounting tables. Automatic financial analysis is blocked without verification."
        )

    return DocumentAssessment(
        classification=classification,
        signals=signals if signals else ["No distinct financial statements or accounting disclosures detected."],
        warnings=warnings,
        heuristic_score=heuristic_score,
    )


def generate_page_summaries(parsed_doc: ParsedDocument) -> List[PageSummaryRecord]:
    """Generate ordered, extractive, source-grounded summaries for every page."""
    page_records: List[PageSummaryRecord] = []

    for page in parsed_doc.pages:
        page_num = page.page_number
        raw_text = page.text.strip()
        char_count = len(raw_text)
        table_count = len(page.tables)
        p_warnings = list(page.warnings)

        # 1. No extractable text case (blank or scanned page)
        if char_count == 0 and table_count == 0:
            p_warnings.append("No extractable digital text found; page may be blank or scanned. OCR was not run.")
            page_records.append(
                PageSummaryRecord(
                    page_number=page_num,
                    summary="No extractable digital text found; page may be blank or scanned. OCR was not run.",
                    content_kind="no_extractable_text",
                    table_count=0,
                    extracted_characters=0,
                    warnings=p_warnings,
                    summary_method="extractive_heuristic",
                )
            )
            continue

        # 2. Determine content_kind
        if table_count > 0 and char_count < 80:
            content_kind = "table"
        elif table_count > 0 and char_count >= 80:
            content_kind = "mixed"
        else:
            content_kind = "text"

        summary_parts = []

        # 3. Extract grounded sentence snippets from narrative text
        if raw_text:
            # Normalize whitespace
            clean_text = re.sub(r"[ \t]+", " ", raw_text)
            lines = [ln.strip() for ln in clean_text.split("\n") if ln.strip()]

            # Candidate sentence units
            sentences: List[str] = []
            for ln in lines:
                # Split by sentence periods
                parts = re.split(r"(?<=[.!?])\s+", ln)
                for p in parts:
                    p_strip = p.strip()
                    if len(p_strip) >= 20:
                        sentences.append(p_strip)

            if not sentences and lines:
                sentences = lines[:2]

            # Prioritize sentences with substantive content
            scored_sentences = []
            for s in sentences:
                score = 0
                s_lower = s.lower()
                if any(re.search(pat, s_lower) for pat in STRONG_STATEMENT_HEADERS):
                    score += 5
                if any(re.search(pat, s_lower) for cat in ACCOUNTING_LINE_ITEMS.values() for pat in cat):
                    score += 3
                if re.search(r"\b\d{4}\b", s):
                    score += 1
                if re.search(r"\$\d+", s):
                    score += 2
                scored_sentences.append((score, s))

            scored_sentences.sort(key=lambda x: x[0], reverse=True)
            chosen_snippets = [s for _, s in scored_sentences[:2]]
            if chosen_snippets:
                summary_parts.append(" ".join(chosen_snippets))

        # 4. Extract table header and row samples
        if table_count > 0:
            tbl_summaries = []
            for tbl in page.tables[:2]:
                t_label = tbl.title or "Financial Table"
                headers_str = ", ".join([h.strip() for h in tbl.headers if h.strip()][:4])
                row_samples = []
                for row in tbl.rows[:2]:
                    row_cells = [c.strip() for c in row if c.strip()]
                    if row_cells:
                        row_samples.append(" | ".join(row_cells[:3]))

                tbl_desc = f"[{t_label}"
                if headers_str:
                    tbl_desc += f": {headers_str}"
                if row_samples:
                    tbl_desc += f" (sample: {'; '.join(row_samples)})"
                tbl_desc += "]"
                tbl_summaries.append(tbl_desc)

            if tbl_summaries:
                summary_parts.append(" ".join(tbl_summaries))

        final_summary = " ".join(summary_parts).strip()
        if not final_summary:
            final_summary = f"Page {page_num} contains unstructured visual content with {char_count} characters and {table_count} table(s)."

        # Truncate summary cleanly to avoid excessive payload
        if len(final_summary) > 400:
            final_summary = final_summary[:397] + "..."

        page_records.append(
            PageSummaryRecord(
                page_number=page_num,
                summary=final_summary,
                content_kind=content_kind,
                table_count=table_count,
                extracted_characters=char_count,
                warnings=p_warnings,
                summary_method="extractive_heuristic",
            )
        )

    return page_records


# --- Sidecar Storage Utilities ---


def get_summary_sidecar_path(stored_doc_path: Path) -> Path:
    """Safely derive sidecar JSON path strictly within configured upload directory."""
    doc_path = Path(stored_doc_path).resolve()
    upload_root = settings.upload_dir.resolve()

    # Security check: Ensure document path is inside configured upload directory
    if not doc_path.is_relative_to(upload_root):
        # Anchor inside upload root using basename to prevent traversal
        doc_path = upload_root / doc_path.name

    sidecar_path = doc_path.with_suffix(".page_summary.json")
    return sidecar_path


def save_document_summary_sidecar(
    stored_doc_path: Path,
    assessment: DocumentAssessment,
    pages: List[PageSummaryRecord],
) -> Path:
    """Atomically write page summary and assessment sidecar JSON."""
    sidecar_path = get_summary_sidecar_path(stored_doc_path)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "assessment": assessment.to_dict(),
        "total_pages": len(pages),
        "pages": [p.to_dict() for p in pages],
    }

    # Atomic write pattern via temporary file replacement
    dir_name = sidecar_path.parent
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, encoding="utf-8") as tf:
        json.dump(payload, tf, indent=2)
        temp_name = tf.name

    os.replace(temp_name, sidecar_path)
    return sidecar_path


def load_document_summary_sidecar(stored_doc_path: Path) -> Optional[Dict[str, Any]]:
    """Safely load page summary sidecar if present."""
    sidecar_path = get_summary_sidecar_path(stored_doc_path)
    if not sidecar_path.exists():
        return None
    try:
        with open(sidecar_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
