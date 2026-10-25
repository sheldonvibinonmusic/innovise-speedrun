"""Unit test for PDF export rendering and layout completeness.

Validates:
1. Claims, terms, and explanations are fully rendered into the PDF text stream without being truncated or dropped by layout bounds.
2. Executive summary headers and paragraphs render cleanly.
3. PDF can be opened and parsed by standard PDF viewers without corruption.
"""

import pymupdf
import pytest
from app.services.pdf_export import generate_report_pdf


def test_pdf_export_renders_all_text_and_terms():
    mock_report = {
        "company_ticker": "MSFT",
        "title": "Financial Research Report: MSFT",
        "verification_status": "VERIFIED",
        "run_id": "run_test_pdf_render_456",
        "executive_summary": (
            "Multi-agent financial assessment for MSFT evaluated reported disclosures.\n\n"
            "### Profit & Loss (P&L) Trajectory\n\n"
            "Gross margin stands at 69.8%, demonstrating strong pricing power and cost absorption.\n\n"
            "### Cash Flow & Working Capital\n\n"
            "Discretionary Free Cash Flow reached $74,071M, confirming durable operational cash conversion.\n\n"
            "### Balance Sheet & Solvency Structure\n\n"
            "Capital structure leverage reflects a debt-to-equity ratio of 0.17x.\n\n"
            "### Controller Assessment & Governance\n\n"
            "Tripartite verification gates concluded with an overall status of VERIFIED."
        ),
        "calculations": [
            {
                "metric_name": "OperatingMargin",
                "formatted_result": "44.6%",
                "formula": "OperatingIncome / Revenue",
                "reporting_period": "FY24",
                "validation_outcome": "VALID",
                "numeric_result": 44.6,
            },
            {
                "metric_name": "RevenueGrowth",
                "formatted_result": "+15.7%",
                "formula": "(Rev24 - Rev23) / Rev23",
                "reporting_period": "FY24",
                "validation_outcome": "VALID",
                "numeric_result": 15.7,
            },
        ],
        "verdicts": [
            {
                "judge_name": "Numerical Integrity Judge",
                "verdict": "PASS",
                "rationale": "All arithmetic calculations reconcile strictly with primary disclosures.",
            },
            {
                "judge_name": "Evidence Citation Judge",
                "verdict": "PASS",
                "rationale": "Every quantitative claim carries valid document coordinates and page references.",
            },
        ],
        "claims": [
            {
                "claim_text": "Total revenue reached $245,120M in FY24 driven by cloud growth.",
                "materiality": "HIGH",
                "verification_status": "supported",
                "claim_type": "reported_fact",
                "evidence_references": ["doc_1:p2"],
            },
            {
                "claim_text": "Operating expenses expanded modestly due to AI infrastructure investments.",
                "materiality": "MEDIUM",
                "verification_status": "supported",
                "claim_type": "reported_fact",
                "evidence_references": ["doc_1:p1"],
            },
            {
                "claim_text": "Foreign currency headwinds may compress international cloud segment margins.",
                "materiality": "HIGH",
                "verification_status": "supported",
                "claim_type": "risk_factor",
                "evidence_references": ["doc_1:p4"],
            },
        ],
        "unresolved_uncertainties": [
            "Hardware supply chain constraints could impact future server delivery timelines."
        ],
    }

    pdf_bytes = generate_report_pdf(mock_report)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    assert len(doc) >= 1

    all_text = " ".join([page.get_text() for page in doc])

    # Verify that the actual claim sentences and explained terms are present in the PDF text
    assert "Total revenue reached $245,120M in FY24 driven by cloud growth" in all_text
    assert "Operating expenses expanded modestly due to AI infrastructure investments" in all_text
    assert "Foreign currency headwinds may compress international cloud segment margins" in all_text

    # Verify executive summary paragraphs and section headings
    assert "PROFIT & LOSS (P&L) TRAJECTORY" in all_text
    assert "Gross margin stands at 69.8%" in all_text
    assert "CASH FLOW & WORKING CAPITAL" in all_text
    assert "Discretionary Free Cash Flow reached $74,071M" in all_text

    # Verify scorecard and judge ledger text
    assert "OperatingMargin" in all_text
    assert "Numerical Integrity Judge" in all_text
    assert "All arithmetic calculations reconcile strictly with primary disclosures" in all_text

    doc.close()
