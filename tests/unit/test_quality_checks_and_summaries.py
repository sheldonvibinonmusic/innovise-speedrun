"""Tests for Ingestion Quality Checks, Content Classifier, and Page Summaries."""

from pathlib import Path
import pytest
import pymupdf

from app.ingestion.parser import DocumentParser, ParsedDocument, ParsedPage, ParsedTable
from app.ingestion.quality_checks import (
    DocumentAssessment,
    PageSummaryRecord,
    assess_document_content,
    generate_page_summaries,
    get_summary_sidecar_path,
    load_document_summary_sidecar,
    save_document_summary_sidecar,
)


@pytest.fixture
def non_financial_pdf_bytes() -> bytes:
    """Generate a synthetic non-financial policy document (e.g. AI Ethics & Risk Management Framework)."""
    doc = pymupdf.open()

    # Page 1: Policy overview
    p1 = doc.new_page()
    p1.insert_text(
        (50, 70),
        "National AI Risk Management Framework & Ethics Standards\n\n"
        "This guidance document establishes core governance protocols for autonomous systems.\n"
        "Organizations should map societal risks, identify algorithmic bias, and maintain data hygiene.\n"
        "Regular architectural audits and vulnerability scanning must be conducted across all deployment teams.",
        fontsize=11,
    )

    # Page 2: Operational guidelines (non-financial table)
    p2 = doc.new_page()
    p2.insert_text(
        (50, 70),
        "Risk Assessment Matrix & Classification Levels\n"
        "Security incident response timelines and severity categorizations:",
        fontsize=11,
    )
    # Non-financial matrix
    p2.draw_rect(pymupdf.Rect(50, 120, 500, 250), color=(0.4, 0.4, 0.4))
    p2.insert_text((60, 140), "Severity Level | Response Time | Escalation Path", fontsize=10)
    p2.insert_text((60, 165), "High Severity  | 1 Hour        | Executive Committee", fontsize=10)
    p2.insert_text((60, 190), "Medium Severity| 4 Hours       | Security Operations", fontsize=10)

    # Page 3: Blank/Scanned page
    doc.new_page()

    buf = doc.tobytes()
    doc.close()
    return buf


@pytest.fixture
def mixed_uncertain_pdf_bytes() -> bytes:
    """Generate a synthetic ambiguous document with sparse financial words but no full statements."""
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text(
        (50, 70),
        "Corporate Social Responsibility & Sustainability Memorandum\n\n"
        "Our enterprise continues to invest in community engagement and global decarbonization.\n"
        "During the recent fiscal year, the company allocated volunteer resources to educational foundations.\n"
        "Total revenue and operational cost metrics are detailed separately in regulatory statutory filings.",
        fontsize=11,
    )
    buf = doc.tobytes()
    doc.close()
    return buf


def test_financial_document_classification(tmp_path: Path, financial_10k_pdf_bytes: bytes):
    """Verify genuine financial disclosures are classified as FINANCIAL."""
    pdf_path = tmp_path / "financial_10k.pdf"
    pdf_path.write_bytes(financial_10k_pdf_bytes)

    parser = DocumentParser()
    parsed_doc = parser.parse_pdf(pdf_path)

    assessment = assess_document_content(parsed_doc)
    assert assessment.classification == "FINANCIAL"
    assert len(assessment.signals) >= 2
    assert any("accounting" in s.lower() or "table" in s.lower() for s in assessment.signals)
    assert assessment.heuristic_score >= 0.5


def test_non_financial_document_classification(tmp_path: Path, non_financial_pdf_bytes: bytes):
    """Verify non-financial documents (AI risk policies) are classified as NON_FINANCIAL."""
    pdf_path = tmp_path / "ai_risk_policy.pdf"
    pdf_path.write_bytes(non_financial_pdf_bytes)

    parser = DocumentParser()
    parsed_doc = parser.parse_pdf(pdf_path)

    assessment = assess_document_content(parsed_doc)
    assert assessment.classification == "NON_FINANCIAL"
    assert "No distinct financial statements" in assessment.signals[0] or "zero" in assessment.signals[0]
    assert any("lacks verifiable accounting statements" in w.lower() for w in assessment.warnings)
    assert assessment.heuristic_score < 0.3


def test_mixed_uncertain_document_classification(tmp_path: Path, mixed_uncertain_pdf_bytes: bytes):
    """Verify mixed documents with isolated words are classified as UNCERTAIN."""
    pdf_path = tmp_path / "sustainability_memo.pdf"
    pdf_path.write_bytes(mixed_uncertain_pdf_bytes)

    parser = DocumentParser()
    parsed_doc = parser.parse_pdf(pdf_path)

    assessment = assess_document_content(parsed_doc)
    assert assessment.classification == "UNCERTAIN"
    assert any("automatic financial analysis is blocked" in w.lower() for w in assessment.warnings)


def test_page_summaries_generation_and_order(tmp_path: Path, non_financial_pdf_bytes: bytes):
    """Verify each page gets exactly one ordered summary with correct content_kind and OCR warnings."""
    pdf_path = tmp_path / "policy_doc.pdf"
    pdf_path.write_bytes(non_financial_pdf_bytes)

    parser = DocumentParser()
    parsed_doc = parser.parse_pdf(pdf_path)
    assert parsed_doc.page_count == 3

    page_summaries = generate_page_summaries(parsed_doc)
    assert len(page_summaries) == 3

    # Check page 1 (text)
    p1 = page_summaries[0]
    assert p1.page_number == 1
    assert p1.content_kind in ("text", "mixed")
    assert "National AI Risk Management Framework" in p1.summary
    assert p1.summary_method == "extractive_heuristic"

    # Check page 3 (blank/scanned)
    p3 = page_summaries[2]
    assert p3.page_number == 3
    assert p3.content_kind == "no_extractable_text"
    assert "No extractable digital text found" in p3.summary
    assert "OCR was not run" in p3.summary
    assert any("OCR" in w for w in p3.warnings)


def test_table_page_summary_includes_headers(tmp_path: Path, financial_10k_pdf_bytes: bytes):
    """Verify table page summaries contain real headers or row samples."""
    pdf_path = tmp_path / "financial_10k.pdf"
    pdf_path.write_bytes(financial_10k_pdf_bytes)

    parser = DocumentParser()
    parsed_doc = parser.parse_pdf(pdf_path)

    page_summaries = generate_page_summaries(parsed_doc)
    # Find a page with tables
    table_pages = [p for p in page_summaries if p.table_count > 0]
    assert len(table_pages) >= 1
    tp = table_pages[0]
    assert "[" in tp.summary and "]" in tp.summary
    assert tp.content_kind in ("table", "mixed")


def test_sidecar_atomic_save_and_load(tmp_path: Path):
    """Verify summary sidecar saves atomically and loads cleanly."""
    doc_path = tmp_path / "doc_test_123.pdf"
    doc_path.write_text("dummy")

    assessment = DocumentAssessment(
        classification="FINANCIAL",
        signals=["Strong statement headers"],
        warnings=[],
        heuristic_score=0.85,
    )
    pages = [
        PageSummaryRecord(
            page_number=1,
            summary="Extracted summary for page 1.",
            content_kind="text",
            table_count=0,
            extracted_characters=200,
            warnings=[],
        )
    ]

    sidecar_path = save_document_summary_sidecar(doc_path, assessment, pages)
    assert sidecar_path.exists()
    assert sidecar_path.name.endswith(".page_summary.json")

    loaded = load_document_summary_sidecar(doc_path)
    assert loaded is not None
    assert loaded["assessment"]["classification"] == "FINANCIAL"
    assert loaded["total_pages"] == 1
    assert loaded["pages"][0]["summary"] == "Extracted summary for page 1."
