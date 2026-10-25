"""Integration tests for Non-Financial PDF Guard and Page-by-Page Summaries.

Validates:
1. Non-financial PDF upload is detected, labeled NON_FINANCIAL, and barred from
   canonical fact extraction and dense/lexical RAG indexing.
2. GET /api/documents/{document_id}/pages returns typed, grounded extractive summaries,
   table statistics, and content assessment without leaking internal server paths.
3. Financial 10-K disclosures are correctly classified as FINANCIAL and indexed.
4. Workflow check_readiness_node blocks research execution if only non-financial documents are scoped.
"""

import io
from pathlib import Path
import pymupdf
import pytest

from app.db.repository import Repository
from app.workflow.nodes import check_readiness_node


def _create_synthetic_employee_handbook_pdf() -> bytes:
    """Generate a multi-page non-financial employee policy handbook."""
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_textbox(
        pymupdf.Rect(50, 50, 550, 750),
        "Engineering Team Handbook — Workspace Conduct and Information Security Guidelines\n\n"
        "Section 1: General Code of Workplace Conduct\n"
        "All team members are expected to conduct themselves with integrity, professionalism, and mutual respect. "
        "Collaborative problem solving and transparent peer reviews form the cornerstone of our engineering culture. "
        "Flexible working hours must be aligned with your sprint commitments and core pairing windows.\n\n"
        "Section 2: Workstation and Device Hygiene\n"
        "All development laptops must enforce full-disk encryption and automated security patch updates. "
        "Never leave unlocked workstations unattended in public spaces or shared coworking areas.\n",
    )

    p2 = doc.new_page()
    p2.insert_textbox(
        pymupdf.Rect(50, 50, 550, 750),
        "Section 3: Incident Reporting and Escalation Matrix\n\n"
        "In the event of a suspected credential leakage or unverified package dependency, immediately report the event "
        "to the security response channel on Slack. Preserve terminal logs and timestamps to assist triage.\n\n"
        "Team Emergency Contact List:\n"
        "Role | Contact Channel\n"
        "Security Lead | #sec-ops\n"
        "Infrastructure Lead | #infra-triage\n",
    )
    content = doc.tobytes()
    doc.close()
    return content


def test_non_financial_pdf_upload_blocked_from_facts_and_rag(temp_env):
    """Uploading a non-financial PDF must yield NON_FINANCIAL status and 0 indexed chunks/facts."""
    client = temp_env["client"]
    pdf_bytes = _create_synthetic_employee_handbook_pdf()

    files = [("files", ("Engineering_Handbook_2024.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    res = client.post(
        "/api/documents/upload",
        files=files,
        data={"company_ticker": "MSFT", "reporting_period": "FY24", "process_now": "true"},
    )
    assert res.status_code == 201
    data = res.json()
    assert len(data["uploaded_documents"]) == 1

    doc = data["uploaded_documents"][0]
    doc_id = doc["document_id"]
    assert doc["status"] == "NON_FINANCIAL"
    assert doc["classification"] == "NON_FINANCIAL"
    assert doc["chunks_indexed"] == 0
    assert doc["facts_extracted"] == 0

    # Verify database isolation: zero chunks and facts stored in SQLite
    session_factory = temp_env["session_factory"]
    with session_factory() as db:
        repo = Repository(db)
        db_doc = repo.get_document_by_id(doc_id)
        assert db_doc is not None
        assert db_doc.ingestion_status == "NON_FINANCIAL"
        assert len(repo.get_chunks_by_document(doc_id)) == 0
        assert len(repo.get_facts_by_document(doc_id)) == 0


def test_get_document_pages_endpoint_structure_and_security(temp_env):
    """GET /api/documents/{doc_id}/pages returns grounded page summaries without path leakage."""
    client = temp_env["client"]
    pdf_bytes = _create_synthetic_employee_handbook_pdf()

    files = [("files", ("Engineering_Handbook_2024.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    upload_res = client.post(
        "/api/documents/upload",
        files=files,
        data={"company_ticker": "MSFT", "process_now": "true"},
    )
    doc_id = upload_res.json()["uploaded_documents"][0]["document_id"]

    # Query page extraction summaries endpoint
    pages_res = client.get(f"/api/documents/{doc_id}/pages")
    assert pages_res.status_code == 200
    page_data = pages_res.json()

    assert page_data["document_id"] == doc_id
    assert page_data["summary_method"] == "extractive_heuristic"
    assert page_data["page_count"] == 2

    # Verify no filesystem paths leaked in original_filename
    assert "/" not in page_data["original_filename"]
    assert "\\" not in page_data["original_filename"]
    assert page_data["original_filename"].endswith(".pdf")

    # Verify assessment contract
    assessment = page_data["assessment"]
    assert assessment["classification"] == "NON_FINANCIAL"
    assert len(assessment["warnings"]) >= 1

    # Verify ordered page summaries
    pages = page_data["pages"]
    assert len(pages) == 2
    assert pages[0]["page_number"] == 1
    assert pages[0]["extracted_characters"] > 100
    assert "Engineering Team Handbook" in pages[0]["summary"]
    assert pages[0]["summary_method"] == "extractive_heuristic"

    assert pages[1]["page_number"] == 2
    assert pages[1]["summary_method"] == "extractive_heuristic"

    # Verify 404 for nonexistent document
    notFoundRes = client.get("/api/documents/doc_nonexistent_9999/pages")
    assert notFoundRes.status_code == 404


def test_financial_10k_upload_and_page_summaries(temp_env, financial_10k_pdf_bytes: bytes):
    """Financial 10-K must classify as FINANCIAL, index chunks, and yield page summaries."""
    client = temp_env["client"]

    files = [("files", ("MSFT_FY24_10K.pdf", io.BytesIO(financial_10k_pdf_bytes), "application/pdf"))]
    upload_res = client.post(
        "/api/documents/upload",
        files=files,
        data={"company_ticker": "MSFT", "reporting_period": "FY24", "process_now": "true"},
    )
    assert upload_res.status_code == 201
    doc = upload_res.json()["uploaded_documents"][0]
    doc_id = doc["document_id"]

    assert doc["status"] in ("INDEXED", "PARTIALLY_PROCESSED")
    assert doc["classification"] == "FINANCIAL"
    assert doc["chunks_indexed"] > 0
    assert doc["facts_extracted"] > 0

    # Query page summaries
    pages_res = client.get(f"/api/documents/{doc_id}/pages")
    assert pages_res.status_code == 200
    page_data = pages_res.json()

    assert page_data["assessment"]["classification"] == "FINANCIAL"
    assert page_data["assessment"]["heuristic_score"] >= 0.5
    assert len(page_data["pages"]) == 2

    # Page 2 has the financial table
    p2 = page_data["pages"][1]
    assert p2["page_number"] == 2
    assert p2["content_kind"] in ("table", "mixed")
    assert p2["table_count"] >= 1
    assert "revenue" in p2["summary"].lower() or "table" in p2["summary"].lower()


def test_research_run_readiness_blocks_non_financial_doc(temp_env):
    """check_readiness_node must set documents_ready=False when non-financial doc is scoped."""
    client = temp_env["client"]
    pdf_bytes = _create_synthetic_employee_handbook_pdf()

    files = [("files", ("Internal_Policy.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    upload_res = client.post(
        "/api/documents/upload",
        files=files,
        data={"company_ticker": "MSFT", "process_now": "true"},
    )
    doc_id = upload_res.json()["uploaded_documents"][0]["document_id"]

    # Directly invoke workflow readiness node with the non-financial doc ID
    readiness_state = {
        "document_ids": [doc_id],
        "company_ticker": "MSFT",
        "errors": [],
        "warnings": [],
    }
    result = check_readiness_node(readiness_state)

    assert result["documents_ready"] is False
    assert len(result["document_ids"]) == 0
    assert any("readiness failure" in err.lower() or "non_financial" in err.lower() for err in result["errors"])
