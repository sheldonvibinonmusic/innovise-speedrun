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
import re
import time
from typing import Any, Dict, List, Optional
import httpx

from app.config import settings
from app.ingestion.sources.base import BaseSourceConnector

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_BASE = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FACTS_BASE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filename}"


def normalize_period(period_str: Optional[str]) -> Dict[str, Any]:
    """Deterministically parse and normalize financial period and filing expressions.

    Supports:
    - 'FY24', 'FY2024', '2024', '24' -> normalized_year='2024', period_type='annual'
    - 'Q1 2024', 'Q1 24', 'Q1-2024', 'Q1' -> normalized_year='2024', quarter='Q1'
    - 'S1 24', 'S-1 2024', 'Form S-1', 'S1' -> detected Form S-1 / Semester 1
    - 'H1 24', 'H2 2024' -> half-year
    """
    if not period_str:
        return {
            "normalized_year": None,
            "period_label": None,
            "quarter": None,
            "is_s1_form": False,
            "is_semester": False,
            "additional_forms": [],
        }

    raw = period_str.strip().upper()
    normalized_year = None
    quarter = None
    is_s1_form = False
    is_semester = False
    additional_forms = []

    # 1. Detect 4-digit or 2-digit fiscal year
    four_digit = re.search(r"(?:19\d\d|20\d\d)", raw)
    if four_digit:
        normalized_year = four_digit.group(0)
    else:
        two_digit = re.search(r"(?:FY|CY|Q[1-4]|S[1-2]|H[1-2]|\s|^)['`]?([0-9]{2})\b", raw)
        if two_digit:
            normalized_year = f"20{two_digit.group(1)}"

    # 2. Detect Form S-1 or Semester 1 / Half 1
    if re.search(r"\bS[- ]?1\b", raw) or "FORM S-1" in raw or "FORM S1" in raw:
        is_s1_form = True
        is_semester = True
        additional_forms.extend(["S-1", "S-1/A"])
    elif re.search(r"\bH[1-2]\b", raw) or re.search(r"\bS[2]\b", raw):
        is_semester = True

    # 3. Detect Quarters
    q_match = re.search(r"\b(Q[1-4])\b", raw)
    if q_match:
        quarter = q_match.group(1)
        if quarter in ("Q1", "Q2", "Q3") and "10-Q" not in additional_forms:
            additional_forms.append("10-Q")
        elif quarter == "Q4" and "10-K" not in additional_forms:
            additional_forms.append("10-K")

    return {
        "raw_period": period_str,
        "normalized_year": normalized_year,
        "quarter": quarter,
        "is_s1_form": is_s1_form,
        "is_semester": is_semester,
        "additional_forms": additional_forms,
    }


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
        """Resolve company identifier (ticker, name, or CIK) to standardized SEC metadata."""
        ident = identifier.strip().upper()
        # Clean common company suffixes for flexible lookup
        clean_name = re.sub(r"\b(CORP|CORPORATION|INC|INCORPORATED|CO|COMPANY|LTD|HOLDINGS?|PLC)\b\.?", "", ident).strip()

        with httpx.Client() as client:
            resp = self._get_with_retry(client, SEC_TICKERS_URL, self.sec_headers)
            tickers_data = resp.json()

        # tickers_data format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        candidates = []
        for entry in tickers_data.values():
            entry_ticker = str(entry.get("ticker", "")).upper()
            entry_cik = str(entry.get("cik_str", "")).zfill(10)
            entry_title = str(entry.get("title", ""))
            entry_title_upper = entry_title.upper()

            # Rank 1: Exact ticker match
            if entry_ticker == ident:
                candidates.append((1, entry_cik, entry_ticker, entry_title))
            # Rank 2: Exact CIK match
            elif entry_cik == ident.zfill(10):
                candidates.append((2, entry_cik, entry_ticker, entry_title))
            # Rank 3: Exact title match
            elif entry_title_upper == ident:
                candidates.append((3, entry_cik, entry_ticker, entry_title))
            # Rank 4: Title starts with identifier (e.g. "MICROSOFT CORP" starts with "MICROSOFT")
            elif entry_title_upper.startswith(ident + " ") or (clean_name and entry_title_upper.startswith(clean_name)):
                candidates.append((4, entry_cik, entry_ticker, entry_title))
            # Rank 5: Word boundary match
            elif (clean_name and re.search(r"\b" + re.escape(clean_name) + r"\b", entry_title_upper)) or re.search(r"\b" + re.escape(ident) + r"\b", entry_title_upper):
                candidates.append((5, entry_cik, entry_ticker, entry_title))
            # Rank 6: Substring match
            elif (clean_name and clean_name in entry_title_upper) or ident in entry_title_upper:
                candidates.append((6, entry_cik, entry_ticker, entry_title))

        if candidates:
            candidates.sort(key=lambda x: x[0])
            best = candidates[0]
            return {
                "cik": best[1],
                "ticker": best[2],
                "company_name": best[3],
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

        # 2. Normalize requested period and expand target forms if needed
        norm_period = normalize_period(period_filter)
        if norm_period.get("additional_forms"):
            for f in norm_period["additional_forms"]:
                if f.upper() not in target_forms:
                    target_forms.append(f.upper())

        # 3. Query SEC Submissions API
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

                if len(discovered) >= max_periods * 3:
                    break

        # Filter by requested period if supplied (e.g. "2024", "FY24", "S1 24")
        if period_filter:
            norm_year = norm_period.get("normalized_year")
            norm_quarter = norm_period.get("quarter")
            is_s1 = norm_period.get("is_s1_form")

            filtered: List[DiscoveredFiling] = []
            for d in discovered:
                f_date = str(d.filing_date or "")
                r_date = str(d.report_date or "")

                # Direct match with raw filter string
                match = period_filter.lower() in f_date.lower() or period_filter.lower() in r_date.lower()

                # Match by normalized 4-digit fiscal year
                if not match and norm_year:
                    match = norm_year in f_date or norm_year in r_date

                # Match by quarter (e.g. Q1 filings usually filed in April/May)
                if not match and norm_quarter:
                    if norm_quarter == "Q1" and any(m in f_date for m in ("-03-", "-04-", "-05-")):
                        match = True
                    elif norm_quarter == "Q2" and any(m in f_date for m in ("-06-", "-07-", "-08-")):
                        match = True
                    elif norm_quarter == "Q3" and any(m in f_date for m in ("-09-", "-10-", "-11-")):
                        match = True

                # If Form S-1 was requested, prioritize S-1 form match
                if not match and is_s1:
                    match = "S-1" in d.form.upper()

                if match:
                    filtered.append(d)

            # UNCONDITIONAL ASSIGNMENT: Never fall back to all filings on zero matches!
            discovered = filtered

        warnings: List[str] = []
        if period_filter and not discovered:
            status = "NO_MATCHING_PERIOD"
            periods_preview = ", ".join(sorted(list(set(available_periods)), reverse=True)[:6])
            warnings.append(
                f"No {', '.join(target_forms)} filings found matching requested period '{period_filter}'. "
                f"Available periods: {periods_preview or 'None discovered'}."
            )
        elif not discovered:
            status = "NO_FILINGS"
            warnings.append(f"No {', '.join(target_forms)} filings found matching criteria.")
        else:
            status = "COVERAGE_AVAILABLE"

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
