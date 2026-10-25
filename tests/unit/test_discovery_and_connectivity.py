"""Tests for Connectivity, Period Normalization, Discovery, and Report Schema Integrity.

Verifies:
1. Deterministic period normalization (FY24, FY2024, S1 24, Q1 2024, etc.)
2. SEC EDGAR period filtering without silent empty-filter fallback
3. Ranked company name resolution ("Microsoft" -> MSFT)
4. Health endpoint contract and readiness flags
5. Report endpoint exposing top-level calculations, verdicts, and caveats
"""

from typing import Dict, Any
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.ingestion.sources.sec_edgar import SecEdgarConnector, normalize_period
from app.schemas.requests import CompanyDiscoverRequest, CreateRunRequest


# --- 1. Deterministic Period Normalization ---

def test_normalize_period_annual():
    norm_fy24 = normalize_period("FY24")
    assert norm_fy24["normalized_year"] == "2024"
    assert not norm_fy24["is_s1_form"]

    norm_fy2024 = normalize_period("FY2024")
    assert norm_fy2024["normalized_year"] == "2024"

    norm_plain24 = normalize_period("24")
    assert norm_plain24["normalized_year"] == "2024"

    norm_2023 = normalize_period("2023")
    assert norm_2023["normalized_year"] == "2023"


def test_normalize_period_quarters():
    norm_q1 = normalize_period("Q1 2024")
    assert norm_q1["normalized_year"] == "2024"
    assert norm_q1["quarter"] == "Q1"
    assert "10-Q" in norm_q1["additional_forms"]

    norm_q4 = normalize_period("Q4 24")
    assert norm_q4["normalized_year"] == "2024"
    assert norm_q4["quarter"] == "Q4"
    assert "10-K" in norm_q4["additional_forms"]


def test_normalize_period_s1_and_semesters():
    norm_s1 = normalize_period("S1 24")
    assert norm_s1["normalized_year"] == "2024"
    assert norm_s1["is_s1_form"] is True
    assert norm_s1["is_semester"] is True
    assert "S-1" in norm_s1["additional_forms"]

    norm_form_s1 = normalize_period("Form S-1")
    assert norm_form_s1["is_s1_form"] is True
    assert "S-1" in norm_form_s1["additional_forms"]


# --- 2. Request Schema Backward & Forward Compatibility ---

def test_company_discover_request_schema():
    # Frontend payload with company_name_or_ticker
    req1 = CompanyDiscoverRequest(company_name_or_ticker="Microsoft", period="FY24")
    assert req1.ticker_or_cik == "Microsoft"
    assert req1.period == "FY24"

    # Direct ticker payload
    req2 = CompanyDiscoverRequest(ticker_or_cik="MSFT", website_url="https://microsoft.com/investor")
    assert req2.ticker_or_cik == "MSFT"
    assert req2.website_url == "https://microsoft.com/investor"


def test_create_run_request_schema_with_mode_a():
    req = CreateRunRequest(
        research_question="Analyze operating margins.",
        company_ticker="MSFT",
        reporting_periods=["FY24"],
        website_url="https://www.microsoft.com/investor",
        acquisition_mode="combined",
    )
    assert req.company_ticker == "MSFT"
    assert req.website_url == "https://www.microsoft.com/investor"
    assert req.acquisition_mode == "combined"


# --- 3. SEC Empty-Filter & Ranked Resolution Verification ---

@pytest.mark.anyio
async def test_sec_edgar_empty_filter_does_not_fall_back_silently():
    connector = SecEdgarConnector()

    mock_tickers = {
        "0": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
    }

    # Synthetic submissions containing only 2023 filings
    mock_submissions = {
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q"],
                "accessionNumber": ["0000789019-23-000001", "0000789019-23-000002"],
                "filingDate": ["2023-07-27", "2023-10-24"],
                "reportDate": ["2023-06-30", "2023-09-30"],
                "primaryDocument": ["msft-20230630.htm", "msft-20230930.htm"],
            }
        }
    }

    with patch.object(connector, "_get_with_retry") as mock_get:
        mock_resp_tickers = MagicMock()
        mock_resp_tickers.json.return_value = mock_tickers

        mock_resp_sub = MagicMock()
        mock_resp_sub.json.return_value = mock_submissions

        mock_get.side_effect = [mock_resp_tickers, mock_resp_sub]

        # Query for FY24 (which is not in the mock submissions)
        manifest = await connector.fetch_filings(
            company_id="MSFT",
            period_filter="2024",
        )

        # Must report NO_MATCHING_PERIOD and return 0 filings, NOT fall back to 2023 filings!
        assert manifest.coverage_status == "NO_MATCHING_PERIOD"
        assert len(manifest.discovered_filings) == 0
        assert any("No" in w and "matching" in w for w in manifest.warnings)


@pytest.mark.anyio
async def test_sec_edgar_company_name_resolution():
    connector = SecEdgarConnector()

    mock_tickers = {
        "0": {"cik_str": 12345, "ticker": "OTHER", "title": "SOME OTHER MICROSOFT VENDOR"},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
    }

    with patch.object(connector, "_get_with_retry") as mock_get:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_tickers
        mock_get.return_value = mock_resp

        # Should rank "MICROSOFT CORP" above "SOME OTHER MICROSOFT VENDOR"
        resolved = await connector.discover_company("Microsoft")
        assert resolved["resolved"] is True
        assert resolved["ticker"] == "MSFT"
        assert resolved["cik"] == "0000789019"
        assert resolved["company_name"] == "MICROSOFT CORP"


# --- 4. System Health & Report Contract Integration ---

def test_health_endpoint_contract(temp_env):
    client: TestClient = temp_env["client"]
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True
    assert "llm_api_key_configured" in data["optional_components"]


def test_report_endpoint_exposes_convenience_fields(temp_env):
    client: TestClient = temp_env["client"]
    session_factory = temp_env["session_factory"]

    # Seed a completed run and report in isolated db
    from app.db.repository import Repository
    with session_factory() as db:
        repo = Repository(db)
        comp = repo.create_company("Microsoft Corp", "MSFT", "US")
        run = repo.create_run(
            run_id="run_test_rep_schema",
            research_question="Verify schema exposure.",
            company_id=comp.id,
            requested_periods=["FY24"],
        )
        repo.update_run_status("run_test_rep_schema", "completed")
        repo.create_or_update_report(
            report_id="rep_test_rep_schema",
            run_id="run_test_rep_schema",
            executive_summary="Summary for MSFT.",
            report_markdown="# Test Report",
            structured_data={
                "calculations": [{"metric_name": "OperatingMargin", "formatted_result": "44.6%"}],
                "verdicts": [{"judge_name": "evidence_citation_judge", "verdict": "PASS"}],
                "unresolved": ["Minor currency fluctuation risk."],
            },
            verification_status="VERIFIED",
        )

    resp = client.get("/api/reports/run_test_rep_schema")
    assert resp.status_code == 200
    data = resp.json()

    # Verify top-level convenience fields
    assert "calculations" in data
    assert len(data["calculations"]) == 1
    assert data["calculations"][0]["metric_name"] == "OperatingMargin"

    assert "verdicts" in data
    assert len(data["verdicts"]) == 1
    assert data["verdicts"][0]["judge_name"] == "evidence_citation_judge"

    assert "unresolved_uncertainties" in data
    assert len(data["unresolved_uncertainties"]) == 1
    assert data["unresolved_uncertainties"][0] == "Minor currency fluctuation risk."
