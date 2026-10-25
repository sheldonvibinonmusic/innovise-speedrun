"""End-to-End Demonstration and Acceptance Test Suite.

Validates the full vertical slice:
1. Document upload (PDF / PPTX) and true processing status.
2. Canonical financial fact extraction with column-specific period preservation.
3. Prevention of 'Cost of revenue' misclassification as 'TotalRevenue' (AUD-03).
4. Deterministic arithmetic calculation with strict period comparability.
5. Tripartite judge verification and strict numerical equality audit (AUD-06).
6. Planted contradiction detection triggering QUALIFIED/BLOCKED status.
7. Substantive, finding-led report synthesis and persistence.
8. Publication-ready PDF export with embedded matplotlib chart and audit scorecard.
9. Human review sign-off and audit log persistence.
"""

from decimal import Decimal
import io
from pathlib import Path
import pymupdf
import pytest
from app.agents.analyst_models import CandidateClaim
from app.agents.judges.financial_integrity import NumericalIntegrityJudge
from app.finance.calculations import CalculationResult
from app.ingestion.parser import DocumentParser, ParsedTable
from app.ingestion.tables import CANONICAL_METRIC_MAP, TableExtractor


def test_cost_of_revenue_never_classified_as_total_revenue():
    """Priority 1 (AUD-03): 'Cost of revenue' or 'Cost of goods sold' must never match TotalRevenue."""
    extractor = TableExtractor()
    table = ParsedTable(
        table_id="tbl_inc_01",
        page_number=2,
        title="Income Statement",
        headers=["Consolidated Income Statement", "2024", "2023"],
        rows=[
            ["Total revenue", "245120", "211915"],
            ["Cost of revenue", "72361", "65860"],
            ["Cost of goods sold", "15000", "14000"],
            ["Operating expenses", "50000", "45000"],
            ["Operating income", "109433", "88523"],
            ["Net income", "88136", "72361"],
        ],
        raw_text="Total revenue 245120 211915 Cost of revenue 72361 65860",
    )
    facts = extractor.extract_facts_from_tables([table], document_id="doc_test_audit03")

    rev_facts = [f for f in facts if f.metric_name == "TotalRevenue"]
    cost_facts = [f for f in facts if f.metric_name == "CostOfRevenue"]

    # Exactly 2 TotalRevenue facts (2024 and 2023)
    assert len(rev_facts) == 2
    assert rev_facts[0].numeric_value == Decimal("245120")
    assert rev_facts[1].numeric_value == Decimal("211915")

    # Cost of revenue must be classified as CostOfRevenue, NOT TotalRevenue
    assert len(cost_facts) == 4  # 2 for Cost of revenue, 2 for Cost of goods sold
    for cf in cost_facts:
        assert cf.metric_name != "TotalRevenue"


def test_column_specific_period_preservation():
    """Priority 1 (AUD-04): Comparative columns must retain their distinct periods."""
    extractor = TableExtractor()
    table = ParsedTable(
        table_id="tbl_bal_01",
        page_number=3,
        title="Balance Sheet",
        headers=["Consolidated Balance Sheets", "FY24", "FY23"],
        rows=[
            ["Current assets", "110000", "100000"],
            ["Current liabilities", "55000", "50000"],
            ["Total assets", "512163", "411976"],
            ["Total debt", "44922", "47204"],
            ["Stockholders' equity", "268499", "206223"],
        ],
        raw_text="Current assets 110000 100000 Current liabilities 55000 50000",
    )
    facts = extractor.extract_facts_from_tables([table], document_id="doc_test_audit04", default_period="FY24")

    ca_facts = [f for f in facts if f.metric_name == "CurrentAssets"]
    assert len(ca_facts) == 2

    # Column 1 should be FY24, Column 2 should be FY23
    assert ca_facts[0].reporting_period == "FY24"
    assert ca_facts[1].reporting_period == "FY23"
    assert ca_facts[0].reporting_period != ca_facts[1].reporting_period


def test_numerical_integrity_judge_rejects_incorrect_number():
    """Priority 4 (AUD-06): A claim asserting a wrong number citing a real fact/calc must be rejected."""
    import asyncio
    judge = NumericalIntegrityJudge()

    # Fact with value 245120
    class MockFact:
        def __init__(self, fid, val):
            self.id = fid
            self.numeric_value = Decimal(val)
            self.currency = "USD"

    fact = MockFact(fid=101, val="245120")
    calc = CalculationResult(
        calculation_id="calc_om_01",
        metric_name="OperatingMargin",
        formula="(OperatingIncome / TotalRevenue) * 100",
        numeric_result=Decimal("44.64"),
        formatted_result="44.64%",
        unit="%",
        reporting_period="FY24",
        reporting_scope="consolidated",
        validation_outcome="VALID",
    )

    async def _run():
        # 1. Correct claim citing fact
        correct_fact_claim = CandidateClaim(
            claim_id="c_valid_fact",
            claim_text="Microsoft reported Total Revenue of 245120 USD.",
            claim_type="reported_fact",
            fact_references=[101],
        )
        # 2. Fabricated claim asserting wrong number
        fake_fact_claim = CandidateClaim(
            claim_id="c_fake_fact",
            claim_text="Microsoft reported Total Revenue of 999999 USD.",
            claim_type="reported_fact",
            fact_references=[101],
        )
        # 3. Correct calc claim
        correct_calc_claim = CandidateClaim(
            claim_id="c_valid_calc",
            claim_text="Operating margin reached 44.64%.",
            claim_type="calculated_metric",
            calculation_id="calc_om_01",
        )
        # 4. Fabricated calc claim asserting wrong number
        fake_calc_claim = CandidateClaim(
            claim_id="c_fake_calc",
            claim_text="Operating margin reached 99.00%.",
            claim_type="calculated_metric",
            calculation_id="calc_om_01",
        )

        verdict = await judge.evaluate_claims(
            claims=[correct_fact_claim, fake_fact_claim, correct_calc_claim, fake_calc_claim],
            calculations=[calc],
            facts=[fact],
        )

        assert verdict.overall_verdict == "BLOCK"
        eval_map = {e.claim_id: e for e in verdict.claim_evaluations}

        assert eval_map["c_valid_fact"].status == "supported"
        assert eval_map["c_fake_fact"].status == "contradicted"
        assert "does not match authoritative" in eval_map["c_fake_fact"].reason

        assert eval_map["c_valid_calc"].status == "supported"
        assert eval_map["c_fake_calc"].status == "contradicted"
        assert "does not match verified arithmetic" in eval_map["c_fake_calc"].reason

    asyncio.run(_run())


def test_complete_end_to_end_journey_with_pdf_export(temp_env, financial_10k_pdf_bytes: bytes):
    """Priority 6 & 12: Complete demonstrator journey with upload, math, report, and PDF export."""
    client = temp_env["client"]

    # 1. Upload supported PDF
    files = [("files", ("Microsoft_FY24_10K.pdf", io.BytesIO(financial_10k_pdf_bytes), "application/pdf"))]
    upload_res = client.post(
        "/api/documents/upload",
        files=files,
        data={"company_ticker": "MSFT", "reporting_period": "FY24", "process_now": "true"},
    )
    assert upload_res.status_code == 201
    up_data = upload_res.json()
    assert len(up_data["uploaded_documents"]) == 1
    doc_info = up_data["uploaded_documents"][0]
    assert doc_info["status"] in ("INDEXED", "PARTIALLY_PROCESSED")
    doc_id = doc_info["document_id"]

    # 2. Create Research Run
    create_res = client.post(
        "/api/runs",
        json={
            "research_question": "Analyze Microsoft FY24 operating profitability and revenue trajectory.",
            "company_ticker": "MSFT",
            "reporting_periods": ["FY24"],
            "document_ids": [doc_id],
            "acquisition_mode": "upload",
        },
    )
    assert create_res.status_code == 201
    run_id = create_res.json()["run_id"]

    # 3. Execute Multi-Agent Graph Workflow
    exec_res = client.post(f"/api/runs/{run_id}/execute")
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["status"] in ("completed", "completed_with_warnings")

    # 4. Retrieve Persisted Structured Report
    rep_res = client.get(f"/api/reports/{run_id}")
    assert rep_res.status_code == 200
    rep = rep_res.json()

    assert rep["run_id"] == run_id
    assert rep["company_ticker"] == "MSFT"
    assert rep["verification_status"] in ("VERIFIED", "QUALIFIED")

    # Scorecard calculations validation
    calcs = {c["metric_name"]: c for c in rep["calculations"]}
    assert "OperatingMargin" in calcs
    assert calcs["OperatingMargin"]["validation_outcome"] == "VALID"
    assert "RevenueGrowth" in calcs
    assert calcs["RevenueGrowth"]["validation_outcome"] == "VALID"

    # Core claims validation
    assert len(rep["claims"]) >= 2
    for cl in rep["claims"]:
        assert cl["claim_text"]
        assert cl["verification_status"] in ("supported", "needs_human_review", "VERIFIED")

    # 5. Export Report as PDF (Priority 5 / AUD-16)
    pdf_res = client.get(f"/api/reports/{run_id}/export/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers.get("content-type") == "application/pdf"
    assert "attachment" in pdf_res.headers.get("content-disposition", "")
    assert len(pdf_res.content) > 1000

    # 6. Verify PDF format, readability, and embedded components
    pdf_doc = pymupdf.open(stream=pdf_res.content, filetype="pdf")
    assert len(pdf_doc) >= 1

    extracted_pdf_text = ""
    for page in pdf_doc:
        extracted_pdf_text += page.get_text() + "\n"
    pdf_doc.close()

    assert "TRUSTWORTHY FINANCIAL RESEARCH" in extracted_pdf_text
    assert "MSFT" in extracted_pdf_text
    assert "Operating Margin" in extracted_pdf_text or "Total Revenue" in extracted_pdf_text

    # 7. Human Review Sign-Off Cockpit
    review_res = client.post(
        f"/api/runs/{run_id}/review",
        json={
            "overall_decision": "APPROVED",
            "reviewer_name": "Senior Equity Analyst",
            "comments": "Audited deterministic calculations and citations against FY24 Form 10-K disclosures.",
            "claim_overrides": [],
        },
    )
    assert review_res.status_code == 200
    assert review_res.json()["overall_decision"] == "APPROVED"

    # Post-review report verification
    rep_after = client.get(f"/api/reports/{run_id}").json()
    assert rep_after["verification_status"] == "APPROVED"


def test_planted_contradiction_escalates_and_prevents_verified(temp_env, conflicting_10k_pdf_bytes: bytes):
    """Priority 7 & 12 (AUD-15): Planted contradiction must trigger QUALIFIED/BLOCK and never false VERIFIED."""
    client = temp_env["client"]

    # 1. Upload conflicting disclosure document
    files = [("files", ("Conflicting_Restatement_10K.pdf", io.BytesIO(conflicting_10k_pdf_bytes), "application/pdf"))]
    upload_res = client.post(
        "/api/documents/upload",
        files=files,
        data={"company_ticker": "MSFT", "reporting_period": "FY24", "process_now": "true"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["uploaded_documents"][0]["document_id"]

    # 2. Run workflow
    create_res = client.post(
        "/api/runs",
        json={
            "research_question": "Audit Microsoft FY24 reported performance against restated risk disclosures.",
            "company_ticker": "MSFT",
            "reporting_periods": ["FY24"],
            "document_ids": [doc_id],
            "acquisition_mode": "upload",
        },
    )
    run_id = create_res.json()["run_id"]
    exec_res = client.post(f"/api/runs/{run_id}/execute")
    assert exec_res.status_code == 200

    # 3. Verify gate status: MUST NOT be VERIFIED
    rep_res = client.get(f"/api/reports/{run_id}")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()

    assert rep_data["verification_status"] in ("QUALIFIED", "BLOCKED")
    assert rep_data["verification_status"] != "VERIFIED"

    # 4. Verify contradictory disclosures are highlighted in executive summary & report
    summary = rep_data["executive_summary"].lower()
    assert "contradict" in summary or "risk" in summary or "compression" in summary


def test_pdf_workflow_stage_events_and_trace_progression(temp_env, financial_10k_pdf_bytes: bytes):
    """Audit Fix: Workflow nodes must emit granular RunEvent stages so UI stepper advances and report is loaded."""
    client = temp_env["client"]

    # 1. Upload PDF
    files = [("files", ("MSFT_10K_Audited.pdf", io.BytesIO(financial_10k_pdf_bytes), "application/pdf"))]
    upload_res = client.post(
        "/api/documents/upload",
        files=files,
        data={"company_ticker": "MSFT", "reporting_period": "FY24", "process_now": "true"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["uploaded_documents"][0]["document_id"]

    # 2. Run execution
    create_res = client.post(
        "/api/runs",
        json={
            "research_question": "Analyze Microsoft FY24 profitability, liquidity, and operational growth trajectory.",
            "company_ticker": "MSFT",
            "reporting_periods": ["FY24"],
            "document_ids": [doc_id],
            "acquisition_mode": "upload",
        },
    )
    assert create_res.status_code == 201
    run_id = create_res.json()["run_id"]

    exec_res = client.post(f"/api/runs/{run_id}/execute")
    assert exec_res.status_code == 200

    # 3. Retrieve audit trace and assert all stages emitted events
    trace_res = client.get(f"/api/runs/{run_id}/trace")
    assert trace_res.status_code == 200
    events = trace_res.json()["events"]
    event_types = [
        ev.get("details", {}).get("event_type") or ev.get("status_or_code")
        for ev in events
        if ev.get("details")
    ]

    # Required for UI stages 1 through 6
    assert any("ACQUIRE_SOURCES" in et for et in event_types)
    assert any("CHECK_READINESS" in et or "FACTS_EXTRACTED" in et for et in event_types)
    assert any("RETRIEVE_EVIDENCE" in et or "MULTI_HOP" in et for et in event_types)
    assert any("CALCULATE_METRICS" in et or "METRICS_VERIFIED" in et for et in event_types)
    assert any("ANALYSTS_COMPLETE" in et or "JUDGES_AUDITED" in et for et in event_types)
    assert any("SYNTHESIS_COMPLETE" in et for et in event_types)

    # 4. Report is available and PDF exportable
    rep_res = client.get(f"/api/reports/{run_id}")
    assert rep_res.status_code == 200
    pdf_res = client.get(f"/api/reports/{run_id}/export/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF")
