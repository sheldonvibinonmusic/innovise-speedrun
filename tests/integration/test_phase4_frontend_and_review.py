"""Integration Tests for Phase 4: Frontend Assets, Integration Contracts, and Human Review Cockpit.

Verifies:
1. FastAPI static mount serves frontend application at /ui and /ui/index.html.
2. Architectural hero image asset (hero-arch.png) is accessible.
3. Core CSS and ES module JS assets load correctly with valid MIME types.
4. Human review sign-off endpoint (POST /api/runs/{run_id}/review) persists decisions (APPROVED, QUALIFIED, REJECTED).
5. Claim overrides update claim verification status in SQLite.
6. Audit trace logs HUMAN_REVIEW_SUBMITTED event.
7. Error handling for non-existent runs (404) and invalid decision keywords (422).
"""

from decimal import Decimal
import io
import pytest
from app.db.models import FinancialFact, ResearchClaim, ResearchReport, ResearchRun
from app.db.repository import Repository


def test_frontend_static_serving(temp_env):
    """Verify FastAPI serves the frontend application and assets."""
    client = temp_env["client"]

    # 1. UI Root Index
    ui_res = client.get("/ui/")
    assert ui_res.status_code == 200
    assert "text/html" in ui_res.headers.get("content-type", "")
    assert "Research That Shows Its Work" in ui_res.text
    assert "FINANCIAL RESEARCH" in ui_res.text

    # 2. Hero Architectural Image Asset
    img_res = client.get("/ui/assets/images/hero-arch.png")
    assert img_res.status_code == 200
    assert "image/png" in img_res.headers.get("content-type", "")

    # 3. Core Architectural Stylesheet
    css_res = client.get("/ui/assets/css/styles.css")
    assert css_res.status_code == 200
    assert "text/css" in css_res.headers.get("content-type", "")
    assert "--bg-deep" in css_res.text

    # 4. Main JavaScript ES Module
    js_res = client.get("/ui/assets/js/app.js")
    assert js_res.status_code == 200
    assert "javascript" in js_res.headers.get("content-type", "")


def test_human_review_cockpit_lifecycle(temp_env):
    """Verify human review cockpit sign-off and claim override persistence."""
    client = temp_env["client"]
    session_factory = temp_env["session_factory"]

    run_id = "run_review_test_01"

    with session_factory() as db:
        repo = Repository(db)
        # Create completed run
        run = repo.create_run(
            run_id=run_id,
            research_question="Verify Q4 margin expansion",
            company_id=None,
            jurisdiction="US",
            requested_periods=["FY24"],
            input_document_ids=["doc_rev_01"],
        )
        repo.update_run_status(run_id, "completed")

        # Create candidate claim
        claim = repo.create_claim(
            claim_id="clm_rev_01",
            run_id=run_id,
            evidence_references=["doc_rev_01"],
            claim_text="Operating margin expanded by 240 bps to 44.6%.",
            claim_type="reported_fact",
            materiality="HIGH",
            verification_status="UNVERIFIED",
        )

        # Create report
        report = repo.create_or_update_report(
            report_id="rep_rev_01",
            run_id=run_id,
            executive_summary="Summary of margin findings",
            report_markdown="# Report",
            structured_data={"claims": [{"claim_id": "clm_rev_01"}]},
            verification_status="VERIFIED",
        )

    # 1. Submit Human Sign-Off (APPROVED with claim override)
    review_payload = {
        "overall_decision": "APPROVED",
        "reviewer_name": "Chief Risk Officer",
        "comments": "Audited against primary 10-K filing; numbers reconcile.",
        "claim_overrides": [
            {
                "claim_id": "clm_rev_01",
                "new_status": "VERIFIED",
                "notes": "Verified against 10-K Income Statement table.",
            }
        ],
    }

    res = client.post(f"/api/runs/{run_id}/review", json=review_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["run_id"] == run_id
    assert data["overall_decision"] == "APPROVED"
    assert data["status"] == "approved"
    assert data["reviewer_name"] == "Chief Risk Officer"
    assert data["claim_overrides_applied"] == 1

    # 2. Verify Database State
    with session_factory() as db:
        repo = Repository(db)
        updated_run = repo.get_run_by_id(run_id)
        assert updated_run.status == "approved"

        updated_report = repo.get_report_by_run_id(run_id)
        assert updated_report.verification_status == "APPROVED"
        assert updated_report.structured_data["human_review"]["decision"] == "APPROVED"

        # Verify claim override
        claims = repo.get_claims_by_run_id(run_id)
        target_claim = next(c for c in claims if c.id == "clm_rev_01")
        assert target_claim.verification_status == "VERIFIED"
        assert target_claim.verification_notes == "Verified against 10-K Income Statement table."

        # Verify audit trail event
        events = repo.get_events_by_run_id(run_id)
        event_codes = [e.status_or_code for e in events]
        assert "HUMAN_REVIEW_SUBMITTED" in event_codes


def test_human_review_validation_errors(temp_env):
    """Test 404 for missing run and 422 for invalid decision keywords."""
    client = temp_env["client"]

    # 1. Non-existent run
    missing_res = client.post(
        "/api/runs/run_non_existent/review",
        json={"overall_decision": "APPROVED", "reviewer_name": "Analyst"},
    )
    assert missing_res.status_code == 404

    # 2. Invalid overall_decision
    session_factory = temp_env["session_factory"]
    with session_factory() as db:
        repo = Repository(db)
        repo.create_run(
            run_id="run_invalid_dec",
            research_question="Question",
            company_id=None,
            jurisdiction="US",
            requested_periods=["FY24"],
            input_document_ids=[],
        )

    invalid_res = client.post(
        "/api/runs/run_invalid_dec/review",
        json={"overall_decision": "MAYBE_VALID", "reviewer_name": "Analyst"},
    )
    assert invalid_res.status_code == 422


def test_evidence_provenance_inspector_claim_enrichment(temp_env):
    """Verify GET /api/reports/{run_id} enriches claims with document coordinates and evidence excerpts."""
    client = temp_env["client"]
    session_factory = temp_env["session_factory"]

    run_id = "run_inspect_test_01"
    doc_id = "doc_source_10k_01"
    chunk_id = "chk_page_42_para_03"

    with session_factory() as db:
        repo = Repository(db)
        repo.create_document(
            document_id=doc_id,
            company_id=None,
            source_type="user_upload",
            original_filename="Microsoft_10K_Audited.pdf",
            stored_path=f"data/uploads/{doc_id}.pdf",
            sha256_hash="d" * 64,
        )
        repo.create_chunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            chunk_index=0,
            content="Gross margin increased by 3.2% driven by cloud infrastructure scaling and efficiency.",
            page_number=42,
            section_title="Management's Discussion & Analysis",
        )
        repo.create_run(
            run_id=run_id,
            research_question="Analyze cloud margin expansion",
            company_id=None,
            jurisdiction="US",
            requested_periods=["FY24"],
            input_document_ids=[doc_id],
        )
        repo.create_claim(
            claim_id="clm_insp_01",
            run_id=run_id,
            claim_text="Gross margin increased by 3.2% driven by cloud infrastructure.",
            claim_type="reported_fact",
            materiality="HIGH",
            evidence_references=[chunk_id],
            verification_status="VERIFIED",
        )
        repo.create_or_update_report(
            report_id=f"rep_{run_id}",
            run_id=run_id,
            executive_summary="Executive summary with verified cloud margins.",
            report_markdown="# Report",
            structured_data={"calculations": [], "verdicts": [], "unresolved": []},
            verification_status="VERIFIED",
        )

    res = client.get(f"/api/reports/{run_id}")
    assert res.status_code == 200
    data = res.json()
    assert len(data["claims"]) == 1
    enriched_claim = data["claims"][0]
    assert enriched_claim["claim_id"] == "clm_insp_01"
    assert enriched_claim["document_id"] == doc_id
    assert enriched_claim["page_number"] == 42
    assert "Gross margin increased by 3.2%" in enriched_claim["evidence_excerpt"]
    assert enriched_claim["section_title"] == "Management's Discussion & Analysis"


def test_gross_margin_and_free_cash_flow_math():
    """Verify deterministic precision for gross margin and free cash flow."""
    from datetime import datetime
    from app.finance.calculations import calculate_gross_margin, calculate_free_cash_flow

    fact_rev = FinancialFact(
        id=101,
        company_id=None,
        metric_name="TotalRevenue",
        numeric_value=Decimal("245122000000.00"),
        currency="USD",
        unit_scale="ONES",
        period_type="annual",
        period_end_date=datetime(2024, 12, 31),
        reporting_scope="consolidated",
    )
    fact_gp = FinancialFact(
        id=102,
        company_id=None,
        metric_name="GrossProfit",
        numeric_value=Decimal("170720000000.00"),
        currency="USD",
        unit_scale="ONES",
        period_type="annual",
        period_end_date=datetime(2024, 12, 31),
        reporting_scope="consolidated",
    )
    gm_res = calculate_gross_margin(fact_gp, fact_rev, is_cogs=False)
    assert gm_res.validation_outcome == "VALID"
    assert gm_res.formatted_result == "69.65%"
    assert gm_res.numeric_result == Decimal("69.65")

    fact_ocf = FinancialFact(
        id=103,
        company_id=None,
        metric_name="OperatingCashFlow",
        numeric_value=Decimal("118548000000.00"),
        currency="USD",
        unit_scale="ONES",
        period_type="annual",
        period_end_date=datetime(2024, 12, 31),
        reporting_scope="consolidated",
    )
    fact_capex = FinancialFact(
        id=104,
        company_id=None,
        metric_name="CapitalExpenditures",
        numeric_value=Decimal("44477000000.00"),
        currency="USD",
        unit_scale="ONES",
        period_type="annual",
        period_end_date=datetime(2024, 12, 31),
        reporting_scope="consolidated",
    )
    fcf_res = calculate_free_cash_flow(fact_ocf, fact_capex)
    assert fcf_res.validation_outcome == "VALID"
    assert fcf_res.numeric_result == Decimal("74071000000.00")
    assert "74071000000" in fcf_res.formatted_result
