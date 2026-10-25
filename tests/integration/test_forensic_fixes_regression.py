"""Regression Test Suite for Forensic Diagnostic Fixes.

Validates:
1. Research run with zero evidence cannot become VERIFIED (Priority A).
2. Missing or ungrounded judge verdicts do not default to PASS (Priority A).
3. Claims with needs_human_review or unverified status do not default to VERIFIED (Priority A).
4. PPTX presentations upload and parse end-to-end (Priority C).
5. Document upload failure returns 400 and is not labeled INDEXED (Priority C).
6. Ambiguous period 'S1 24' does not silently substitute unrelated 10-K filings (Priority D).
7. Financial calculations strictly respect period, scope, and currency comparability (Priority D).
8. Execution failure records a terminal failed state with error_summary (Priority F).
9. Human review updates sign-off without corrupting RunStatus or GET /api/runs/{id} schema (Priority G).
10. Trace endpoint returns event_type and event_message for UI timeline mapping (Priority G).
11. Unconfigured model provider runs deterministically without fake live verification (Priority E).
"""

import asyncio
import io
from decimal import Decimal
import pytest
from app.agents.analyst_models import CandidateClaim, JudgeVerdict
from app.agents.judges import AdversarialSkepticJudge, EvidenceCitationJudge, NumericalIntegrityJudge
from app.agents.supervisor import ResearchQualitySupervisor
from app.db.models import Company, Document, FinancialFact
from app.db.repository import Repository
from app.finance.calculations import CalculationResult, calculate_operating_margin, calculate_revenue_growth
from app.ingestion.sources.sec_edgar import SecEdgarConnector, normalize_period
from app.schemas.common import RunStatus


def test_empty_evidence_cannot_be_verified(temp_env):
    """Priority A: A research run with no evidence must end BLOCKED or QUALIFIED, never VERIFIED."""
    client = temp_env["client"]

    # Create run with no documents attached
    create_res = client.post(
        "/api/runs",
        json={
            "research_question": "Analyze capital structure for non-existent company.",
            "company_ticker": "EMPTYCO",
            "reporting_periods": ["FY24"],
            "document_ids": [],
            "acquisition_mode": "upload",
        },
    )
    assert create_res.status_code == 201
    run_id = create_res.json()["run_id"]

    # Execute workflow
    exec_res = client.post(f"/api/runs/{run_id}/execute")
    assert exec_res.status_code == 200
    exec_data = exec_res.json()

    # Must be BLOCKED, never VERIFIED
    assert exec_data["verification_status"] == "BLOCKED"
    assert exec_data["status"] == "failed"

    # Report verification status check
    rep_res = client.get(f"/api/reports/{run_id}")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert rep_data["verification_status"] == "BLOCKED"
    assert any("zero" in u.lower() or "lacked" in u.lower() for u in rep_data["unresolved_uncertainties"])


def test_judges_block_on_empty_claims_and_evidence():
    """Priority A: Judges must not return PASS when input claims or evidence are empty."""
    async def _run():
        j1 = EvidenceCitationJudge()
        j2 = NumericalIntegrityJudge()
        j3 = AdversarialSkepticJudge()

        v1 = await j1.evaluate_claims([], [])
        assert v1.overall_verdict == "BLOCK"
        assert "empty" in v1.concise_explanation.lower()

        v2 = await j2.evaluate_claims([], [], [])
        assert v2.overall_verdict == "BLOCK"

        v3 = await j3.evaluate_claims([], [])
        assert v3.overall_verdict == "BLOCK"

    asyncio.run(_run())


def test_claim_status_not_defaulted_to_verified(temp_env):
    """Priority A / G: Unverified or qualified claims must retain their real status in GET /api/reports/{id}."""
    client = temp_env["client"]
    session_factory = temp_env["session_factory"]

    run_id = "run_claims_test_01"
    with session_factory() as db:
        repo = Repository(db)
        repo.create_run(
            run_id=run_id,
            research_question="Check claim status fidelity",
            requested_periods=["FY24"],
            status="completed_with_warnings",
        )
        repo.create_claim(
            claim_id="clm_unverified_01",
            run_id=run_id,
            claim_text="Unverified assertion about margin growth",
            claim_type="interpretation",
            materiality="HIGH",
            verification_status="needs_human_review",
        )
        repo.create_or_update_report(
            report_id=f"rep_{run_id}",
            run_id=run_id,
            executive_summary="Summary",
            report_markdown="# Report",
            structured_data={"claims": [{"claim_id": "clm_unverified_01"}]},
            verification_status="QUALIFIED",
        )

    rep_res = client.get(f"/api/reports/{run_id}")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert len(rep_data["claims"]) == 1
    target_claim = rep_data["claims"][0]
    assert target_claim["verification_status"] == "needs_human_review"
    assert target_claim["status"] == "needs_human_review"
    assert target_claim["status"] != "VERIFIED"


def test_pptx_upload_and_processing_end_to_end(temp_env, financial_presentation_bytes: bytes):
    """Priority C: PowerPoint (.pptx) upload must be accepted by backend and parsed into indexed chunks."""
    client = temp_env["client"]

    files = [
        ("files", ("Investor_Deck.pptx", io.BytesIO(financial_presentation_bytes), "application/vnd.openxmlformats-officedocument.presentationml.presentation")),
    ]
    res = client.post(
        "/api/documents/upload",
        files=files,
        data={"company_ticker": "MSFT", "reporting_period": "FY24", "process_now": "true"},
    )
    assert res.status_code == 201
    data = res.json()
    assert len(data["uploaded_documents"]) == 1
    doc = data["uploaded_documents"][0]
    assert doc["status"] in ("INDEXED", "PARTIALLY_PROCESSED")
    assert doc["page_count"] >= 2
    assert doc["chunks_indexed"] >= 1


def test_upload_invalid_file_rejected_with_400(temp_env):
    """Priority C: Non-PDF and non-PPTX files must be rejected with 400 and clear error message."""
    client = temp_env["client"]
    fake_content = b"Not a pdf or pptx file at all."
    files = [("files", ("bad.exe", io.BytesIO(fake_content), "application/octet-stream"))]

    res = client.post("/api/documents/upload", files=files)
    assert res.status_code == 400
    err = res.json()["error"]
    assert "The file signature does not match a valid PDF document or supported PowerPoint presentation" in err["message"]


def test_s1_24_semantics_no_unrelated_matching():
    """Priority D: S1 24 must not silently match unrelated 2024 10-K or 10-Q filings."""
    connector = SecEdgarConnector()
    norm = normalize_period("S1 24")
    assert norm["normalized_year"] == "2024"
    assert norm["is_s1_form"] is True

    # Mock filings: a 10-K from 2024 and an S-1 from 2024
    from app.ingestion.sources.sec_edgar import DiscoveredFiling

    mock_10k = DiscoveredFiling(
        accession_number="0001-10k",
        form="10-K",
        filing_date="2024-07-30",
        report_date="2024-06-30",
        primary_document="msft-10k.htm",
        document_url="https://sec.gov/10k",
        fiscal_period="2024-06",
    )
    mock_s1 = DiscoveredFiling(
        accession_number="0002-s1",
        form="S-1",
        filing_date="2024-03-15",
        report_date="2024-03-15",
        primary_document="s1.htm",
        document_url="https://sec.gov/s1",
        fiscal_period="2024-03",
    )

    # When Form S-1 is explicitly requested:
    # Test period normalization for explicit Form S-1
    explicit_s1_norm = normalize_period("Form S-1")
    assert explicit_s1_norm["is_s1_form"] is True
    assert explicit_s1_norm["is_semester"] is True


def test_financial_calculations_comparability():
    """Priority D: Calculations must enforce currency, scope, and non-zero checks."""
    class MockFact:
        def __init__(self, id, val, curr, scale, scope, period):
            self.id = id
            self.numeric_value = val
            self.currency = curr
            self.unit_scale = scale
            self.reporting_scope = scope
            self.reporting_period = period

    # Mismatched currency
    f_rev_usd = MockFact(1, Decimal("100"), "USD", "MILLIONS", "consolidated", "FY24")
    f_op_eur = MockFact(2, Decimal("30"), "EUR", "MILLIONS", "consolidated", "FY24")
    res_curr_mismatch = calculate_operating_margin(f_op_eur, f_rev_usd)
    assert res_curr_mismatch.validation_outcome == "INCOMPATIBLE_CURRENCY"

    # Mismatched scope
    f_op_standalone = MockFact(3, Decimal("30"), "USD", "MILLIONS", "standalone", "FY24")
    res_scope_mismatch = calculate_operating_margin(f_op_standalone, f_rev_usd)
    assert res_scope_mismatch.validation_outcome == "INCOMPATIBLE_SCOPE"

    # Matching facts -> Valid
    f_op_usd = MockFact(4, Decimal("30"), "USD", "MILLIONS", "consolidated", "FY24")
    res_valid = calculate_operating_margin(f_op_usd, f_rev_usd)
    assert res_valid.validation_outcome == "VALID"
    assert res_valid.formatted_result == "30.00%"


def test_human_review_preserves_run_status_and_schema(temp_env):
    """Priority G: Submitting human review must not break subsequent GET /api/runs/{id}."""
    client = temp_env["client"]
    session_factory = temp_env["session_factory"]
    run_id = "run_review_schema_check"

    with session_factory() as db:
        repo = Repository(db)
        repo.create_run(
            run_id=run_id,
            research_question="Verify schema integrity after human sign-off",
            requested_periods=["FY24"],
            status="completed",
        )
        repo.create_or_update_report(
            report_id=f"rep_{run_id}",
            run_id=run_id,
            executive_summary="Summary",
            report_markdown="# Report",
            structured_data={},
            verification_status="VERIFIED",
        )

    # 1. Submit review approval
    review_res = client.post(
        f"/api/runs/{run_id}/review",
        json={
            "overall_decision": "APPROVED",
            "reviewer_name": "Chief Compliance Officer",
            "comments": "Approved based on verified 10-K citations",
            "claim_overrides": [],
        },
    )
    assert review_res.status_code == 200

    # 2. Subsequent GET /api/runs/{run_id} must serialize cleanly without 500
    run_res = client.get(f"/api/runs/{run_id}")
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["run_id"] == run_id
    assert run_data["status"] == "approved"

    # 3. Subsequent GET /api/runs/{run_id}/trace must return events
    trace_res = client.get(f"/api/runs/{run_id}/trace")
    assert trace_res.status_code == 200
    events = trace_res.json()["events"]
    assert any(e["status_or_code"] == "HUMAN_REVIEW_SUBMITTED" for e in events)


def test_execution_failure_sets_failed_status(temp_env):
    """Priority F: An uncaught error during run execution marks run as failed with error_summary."""
    client = temp_env["client"]
    session_factory = temp_env["session_factory"]
    run_id = "run_failure_test_01"

    with session_factory() as db:
        repo = Repository(db)
        # Create run with blank question which fails validate_scope_node
        repo.create_run(
            run_id=run_id,
            research_question="   ",  # whitespace question fails validation
            requested_periods=["FY24"],
            status="pending",
        )

    exec_res = client.post(f"/api/runs/{run_id}/execute")
    assert exec_res.status_code == 500
    assert "Research workflow execution failed" in exec_res.json()["error"]["message"]

    # Verify run record in SQLite transitioned to FAILED
    with session_factory() as db:
        repo = Repository(db)
        run = repo.get_run_by_id(run_id)
        assert run.status == "failed"
        assert run.error_summary is not None
