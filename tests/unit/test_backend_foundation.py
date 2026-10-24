"""Unit and Integration Tests for Phase 1 Backend Foundation.

Verifies:
1. Application initialization and /api/health endpoint.
2. SQLite table creation and database models.
3. Research run creation, validation, and retrieval (including 404 handling).
4. PDF upload verification: valid signature, invalid signature rejection,
   empty file rejection, size limit enforcement, deduplication, and metadata persistence.
"""

import io
from pathlib import Path
from unittest.mock import patch
import pytest
from sqlalchemy import inspect, select

from app.config import settings
from app.db.models import Company, Document, FinancialFact, ResearchRun, RunEvent


def test_app_initialization_and_health(temp_env):
    """Test that FastAPI starts up and /api/health returns a healthy status."""
    client = temp_env["client"]
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True
    assert data["version"] == settings.app_version


def test_sqlite_table_initialization(temp_env):
    """Test that all required tables are deterministically initialized in SQLite."""
    engine = temp_env["engine"]
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = ["companies", "documents", "research_runs", "run_events", "financial_facts"]
    for table in expected_tables:
        assert table in tables, f"Expected table '{table}' was not created in SQLite."


def test_research_request_validation(temp_env):
    """Test rejection of malformed or missing research request fields."""
    client = temp_env["client"]

    # Missing research_question
    res_missing = client.post("/api/runs", json={})
    assert res_missing.status_code == 422

    # Blank whitespace research_question
    res_blank = client.post("/api/runs", json={"research_question": "   "})
    assert res_blank.status_code == 422


def test_create_and_retrieve_research_run(temp_env):
    """Test creating a persistent research run and retrieving it by ID."""
    client = temp_env["client"]

    payload = {
        "research_question": "Analyze operating margins and cash flow conversion for FY24.",
        "company_name": "Microsoft Corporation",
        "company_ticker": "MSFT",
        "jurisdiction": "US",
        "reporting_periods": ["FY2023", "FY2024"],
        "analytical_areas": ["profitability", "cash_flow"],
    }

    create_res = client.post("/api/runs", json=payload)
    assert create_res.status_code == 201
    created_data = create_res.json()

    run_id = created_data["run_id"]
    assert run_id.startswith("run_")
    assert created_data["status"] == "pending"
    assert created_data["company_ticker"] == "MSFT"
    assert created_data["requested_periods"] == ["FY2023", "FY2024"]

    # Retrieve known run
    get_res = client.get(f"/api/runs/{run_id}")
    assert get_res.status_code == 200
    retrieved_data = get_res.json()
    assert retrieved_data["run_id"] == run_id
    assert retrieved_data["status"] == "pending"
    assert retrieved_data["research_question"] == payload["research_question"]

    # Retrieve audit trace
    trace_res = client.get(f"/api/runs/{run_id}/trace")
    assert trace_res.status_code == 200
    trace_data = trace_res.json()
    assert trace_data["total_events"] >= 1
    assert trace_data["events"][0]["node_or_stage"] == "initialization"


def test_retrieve_unknown_run_404(temp_env):
    """Test that requesting an unknown run ID returns 404 Not Found."""
    client = temp_env["client"]
    res = client.get("/api/runs/run_nonexistent_9999")
    assert res.status_code == 404
    data = res.json()
    assert data["error"]["code"] == "NOT_FOUND"


def test_valid_pdf_upload_and_registration(temp_env, valid_pdf_bytes):
    """Test successful upload, hashing, storage, and database registration of a valid PDF."""
    client = temp_env["client"]

    files = [
        ("files", ("AAPL_10K.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")),
    ]
    data = {
        "company_ticker": "AAPL",
        "reporting_period": "FY24",
        "document_type": "10-K",
        "process_now": "false",
    }

    response = client.post("/api/documents/upload", files=files, data=data)
    assert response.status_code == 201
    res_json = response.json()

    assert len(res_json["uploaded_documents"]) == 1
    doc_meta = res_json["uploaded_documents"][0]
    assert doc_meta["document_id"].startswith("doc_")
    assert doc_meta["filename"] == "AAPL_10K.pdf"
    assert doc_meta["file_size_bytes"] == len(valid_pdf_bytes)
    assert doc_meta["status"] == "REGISTERED"
    assert doc_meta["is_duplicate"] is False

    # Verify document exists in database
    session_factory = temp_env["session_factory"]
    with session_factory() as session:
        doc = session.get(Document, doc_meta["document_id"])
        assert doc is not None
        assert doc.sha256_hash == doc_meta["sha256_hash"]
        assert Path(doc.stored_path).exists()


def test_reject_non_pdf_upload(temp_env):
    """Test rejection of non-PDF file upload (invalid magic byte header)."""
    client = temp_env["client"]

    invalid_content = b"This is plain text and definitely not a PDF file header."
    files = [
        ("files", ("fake_report.pdf", io.BytesIO(invalid_content), "application/pdf")),
    ]

    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    res_json = response.json()
    assert "The file signature does not match a valid PDF document" in res_json["error"]["message"]


def test_reject_empty_upload(temp_env):
    """Test rejection of empty 0-byte file upload."""
    client = temp_env["client"]

    files = [
        ("files", ("empty.pdf", io.BytesIO(b""), "application/pdf")),
    ]

    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    res_json = response.json()
    assert "is empty" in res_json["error"]["message"]


def test_upload_size_limit_enforcement(temp_env, valid_pdf_bytes):
    """Test rejection of file exceeding the configured max_upload_mb limit."""
    client = temp_env["client"]

    # Temporarily set max_upload_mb to a very small size (e.g., 0 MB or 1 MB threshold)
    with patch.object(settings, "max_upload_mb", 1):
        # Create bytes larger than 1 MB (1.5 MB)
        oversized_bytes = valid_pdf_bytes + (b"A" * (1024 * 1024 + 100))
        files = [
            ("files", ("huge_filing.pdf", io.BytesIO(oversized_bytes), "application/pdf")),
        ]

        response = client.post("/api/documents/upload", files=files)
        assert response.status_code == 413
        res_json = response.json()
        assert "exceeds maximum permitted upload limit" in res_json["error"]["message"]


def test_sha256_content_deduplication(temp_env, valid_pdf_bytes):
    """Test that uploading the exact same document twice reuses the registered record."""
    client = temp_env["client"]

    files1 = [
        ("files", ("annual_report_v1.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")),
    ]
    res1 = client.post("/api/documents/upload", files=files1)
    assert res1.status_code == 201
    doc1 = res1.json()["uploaded_documents"][0]
    assert doc1["is_duplicate"] is False

    # Upload same content with different filename
    files2 = [
        ("files", ("annual_report_copy.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")),
    ]
    res2 = client.post("/api/documents/upload", files=files2)
    assert res2.status_code == 201
    doc2 = res2.json()["uploaded_documents"][0]
    assert doc2["is_duplicate"] is True
    assert doc2["document_id"] == doc1["document_id"]
    assert doc2["sha256_hash"] == doc1["sha256_hash"]


def test_database_registration_failure_cleans_up_file(temp_env, valid_pdf_bytes):
    """Test that a database error during registration cleans up the newly saved file."""
    client = temp_env["client"]

    files = [
        ("files", ("fail_doc.pdf", io.BytesIO(valid_pdf_bytes), "application/pdf")),
    ]

    # Mock repository.create_document to raise an unexpected database exception
    with patch("app.db.repository.Repository.create_document", side_effect=RuntimeError("Simulated DB Disk Failure")):
        response = client.post("/api/documents/upload", files=files)
        assert response.status_code == 500
        assert "Simulated DB Disk Failure" in response.json()["error"]["message"]

        # Ensure no lingering files left in uploads dir
        upload_files = list(temp_env["upload_dir"].glob("*fail_doc*"))
        assert len(upload_files) == 0
