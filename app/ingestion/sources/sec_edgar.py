"""Official US SEC EDGAR Source Connector.

Connects to official SEC EDGAR public APIs:
- Company Ticker / CIK Resolution: https://www.sec.gov/files/company_tickers.json
- Company Submissions: https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json
- Company Facts (XBRL): https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json

Complies with SEC fair-access policies:
- User-Agent: Custom contact string (declared in settings.sec_user_agent)
- Rate-limiting: Conservative delays and bounded retries
- No indiscriminate web scraping; official REST endpoints only
"""

from dataclasses import dataclass, field
from datetime import datetime
import time
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings
from app.ingestion.sources.base import BaseSourceConnector

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_BASE = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FACTS_BASE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}"


@dataclass
class DiscoveredFiling:
    """Metadata representing an official SEC regulatory filing."""
    accession_number: str
    form: str
    filing_date: str
    report_date: Optional[str]
    primary_document: str
    document_url: str
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None


@dataclass
class DiscoveryManifest:
    """Coverage summary of SEC filings discovered for a company."""
    company_name: str
    cik: str
    ticker: str
    requested_period: Optional[str]
    discovered_filings: List[DiscoveredFiling] = field(default_factory=list)
    available_periods: List[str] = field(default_factory=list)
    coverage_status: str = "COVERAGE_AVAILABLE"  # COVERAGE_AVAILABLE, NO_FILINGS, AMBIGUOUS_COMPANY
    warnings: List[str] = field(default_factory=list)


class SecEdgarConnector(BaseSourceConnector):
    """Production connector for SEC EDGAR regulatory submissions and XBRL facts."""

    def __init__(self, user_agent: Optional[str] = None, timeout_sec: float = 12.0):
        self.user_agent = user_agent or settings.sec_user_agent
        self.timeout_sec = timeout_sec
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }
        self.sec_headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    def _get_with_retry(
        self, client: httpx.Client, url: str, headers: Dict[str, str], max_retries: int = 3
    ) -> httpx.Response:
        """Execute HTTP GET with exponential backoff and rate limit handling."""
        backoff = 1.0
        for attempt in range(max_retries):
            try:
                resp = client.get(url, headers=headers, timeout=self.timeout_sec)
                if resp.status_code == 429:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
                resp.raise_for_status()
                return resp
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                if attempt == max_retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2.0
        raise httpx.RequestError(f"Failed to fetch {url} after {max_retries} attempts.")

    async def discover_company(self, identifier: str) -> Dict[str, Any]:
        """Resolve company identifier (ticker or CIK) to standardized SEC metadata."""
        ident = identifier.strip().upper()
        # Synchronous implementation inside async wrapper for straightforward execution
        with httpx.Client() as client:
            resp = self._get_with_retry(client, SEC_TICKERS_URL, self.sec_headers)
            tickers_data = resp.json()

        # tickers_data format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        for entry in tickers_data.values():
            entry_ticker = str(entry.get("ticker", "")).upper()
            entry_cik = str(entry.get("cik_str", "")).zfill(10)
            entry_title = str(entry.get("title", ""))

            if entry_ticker == ident or entry_cik == ident.zfill(10) or ident in entry_title.upper():
                return {
                    "cik": entry_cik,
                    "ticker": entry_ticker,
                    "company_name": entry_title,
                    "resolved": True,
                }

        return {
            "identifier": identifier,
            "resolved": False,
            "error": f"No unambiguous SEC registration found for '{identifier}'.",
        }

    async def fetch_filings(
        self,
        company_id: str,  # CIK or ticker
        filing_types: Optional[List[str]] = None,
        max_periods: int = 3,
        period_filter: Optional[str] = None,
    ) -> DiscoveryManifest:
        """Discover eligible regulatory filings for an SEC registered company."""
        # 1. Resolve company CIK
        comp_info = await self.discover_company(company_id)
        if not comp_info.get("resolved"):
            return DiscoveryManifest(
                company_name=company_id,
                cik="",
                ticker=company_id,
                requested_period=period_filter,
                coverage_status="AMBIGUOUS_COMPANY",
                warnings=[f"Company identifier '{company_id}' could not be resolved in SEC records."],
            )

        cik_str = comp_info["cik"]
        target_forms = [f.upper() for f in (filing_types or ["10-K", "10-Q"])]

        # 2. Query SEC Submissions API
        submissions_url = SEC_SUBMISSIONS_BASE.format(cik=cik_str)
        try:
            with httpx.Client() as client:
                resp = self._get_with_retry(client, submissions_url, self.headers)
                sub_data = resp.json()
        except Exception as e:
            return DiscoveryManifest(
                company_name=comp_info["company_name"],
                cik=cik_str,
                ticker=comp_info["ticker"],
                requested_period=period_filter,
                coverage_status="NO_FILINGS",
                warnings=[f"Failed to query SEC submissions API: {str(e)}"],
            )

        recent = sub_data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accessions = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_docs = recent.get("primaryDocument", [])

        discovered: List[DiscoveredFiling] = []
        available_periods: List[str] = []

        cik_num = str(int(cik_str))  # URL path format uses unpadded CIK

        for i, form in enumerate(forms):
            if form.upper() in target_forms:
                accession = accessions[i]
                accession_no_hyphen = accession.replace("-", "")
                primary_doc = primary_docs[i] if i < len(primary_docs) else "document.htm"
                f_date = filing_dates[i] if i < len(filing_dates) else ""
                r_date = report_dates[i] if i < len(report_dates) else f_date

                doc_url = SEC_ARCHIVES_BASE.format(
                    cik=cik_num,
                    accession=accession_no_hyphen,
                    filename=primary_doc,
                )

                filing = DiscoveredFiling(
                    accession_number=accession,
                    form=form,
                    filing_date=f_date,
                    report_date=r_date,
                    primary_document=primary_doc,
                    document_url=doc_url,
                    fiscal_period=f_date[:7] if f_date else None,
                )
                discovered.append(filing)
                if r_date:
                    available_periods.append(r_date[:7])

                if len(discovered) >= max_periods * 2:
                    break

        # Filter by requested period if supplied (e.g. "2024")
        if period_filter:
            filtered = [
                d for d in discovered
                if period_filter in str(d.filing_date) or period_filter in str(d.report_date)
            ]
            if filtered:
                discovered = filtered

        status = "COVERAGE_AVAILABLE" if discovered else "NO_FILINGS"
        warnings = []
        if not discovered:
            warnings.append(f"No {', '.join(target_forms)} filings found matching criteria.")

        return DiscoveryManifest(
            company_name=comp_info["company_name"],
            cik=cik_str,
            ticker=comp_info["ticker"],
            requested_period=period_filter,
            discovered_filings=discovered[:max_periods],
            available_periods=sorted(list(set(available_periods)), reverse=True),
            coverage_status=status,
            warnings=warnings,
        )
