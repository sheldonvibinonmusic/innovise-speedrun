"""Mode A: Bounded Investor Relations & Financial Website Crawler.

Implements safe, bounded discovery of financial filings, annual reports, and investor decks:
- Strict SSRF protection and same-domain scope enforcement via app.security.url_safety
- Configurable limits: max_depth (2), max_pages (10), max_documents (5), timeout (10s)
- Discovers PDF and PPTX links with financial keywords (annual report, 10-K, 10-Q, earnings, results)
- Returns structured discovery manifest with explicit states:
  COVERAGE_AVAILABLE, NO_FINANCIAL_DOCUMENTS_FOUND, ACCESS_BLOCKED, or CRAWL_LIMIT_REACHED
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import httpx

from app.security.url_safety import validate_url_safety


FINANCIAL_KEYWORD_PATTERNS = [
    r"annual[-_ ]?report",
    r"10[-_ ]?k",
    r"10[-_ ]?q",
    r"quarterly[-_ ]?report",
    r"earnings[-_ ]?(?:release|presentation|transcript)",
    r"investor[-_ ]?presentation",
    r"financial[-_ ]?statements?",
    r"results?",
    r"filings?",
    r"shareholder",
    r"form[-_ ]?8[-_ ]?k",
]

FINANCIAL_REGEX = re.compile("|".join(FINANCIAL_KEYWORD_PATTERNS), re.IGNORECASE)


@dataclass
class DiscoveredDocumentRecord:
    """Metadata for an acquired financial document."""
    url: str
    document_type: str  # PDF, PPTX
    title: str
    discovered_at: str
    file_bytes: Optional[bytes] = None
    file_size_bytes: int = 0
    warning: Optional[str] = None


@dataclass
class WebsiteDiscoveryManifest:
    """Outcome and coverage record of the website discovery operation."""
    company_name: str
    seed_url: str
    coverage_status: str  # COVERAGE_AVAILABLE, NO_FINANCIAL_DOCUMENTS_FOUND, ACCESS_BLOCKED, CRAWL_LIMIT_REACHED
    pages_inspected: int
    links_evaluated: int
    visited_urls: List[str] = field(default_factory=list)
    discovered_documents: List[DiscoveredDocumentRecord] = field(default_factory=list)
    skipped_reasons: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class WebsiteFinancialCrawler:
    """Safely discovers and retrieves financial documents from permitted company websites."""

    def __init__(
        self,
        max_depth: int = 2,
        max_pages: int = 10,
        max_documents: int = 5,
        timeout_sec: float = 10.0,
        allow_private_for_tests: bool = False,
    ):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.max_documents = max_documents
        self.timeout_sec = timeout_sec
        self.allow_private_for_tests = allow_private_for_tests

    def is_financial_link(self, href: str, text: str) -> bool:
        """Evaluate if link or anchor text points to a financial disclosure."""
        combined = f"{href} {text}"
        return bool(FINANCIAL_REGEX.search(combined))

    async def crawl_and_discover(
        self,
        seed_url: str,
        company_name: str = "",
        client: Optional[httpx.AsyncClient] = None,
    ) -> WebsiteDiscoveryManifest:
        """Execute bounded crawl starting from seed_url within same domain."""
        if not validate_url_safety(seed_url, allow_private_for_tests=self.allow_private_for_tests):
            return WebsiteDiscoveryManifest(
                company_name=company_name,
                seed_url=seed_url,
                coverage_status="ACCESS_BLOCKED",
                pages_inspected=0,
                links_evaluated=0,
                warnings=[f"Rejected seed URL {seed_url} due to safety or SSRF policy."],
            )

        parsed_seed = urlparse(seed_url)
        allowed_domain = parsed_seed.hostname or ""

        visited_urls: Set[str] = set()
        queue: List[tuple[str, int]] = [(seed_url, 0)]
        discovered_docs: List[DiscoveredDocumentRecord] = []
        skipped_reasons: List[Dict[str, str]] = []
        warnings: List[str] = []
        links_evaluated_count = 0
        status = "NO_FINANCIAL_DOCUMENTS_FOUND"

        headers = {
            "User-Agent": "TrustworthyFinancialResearchAgent/1.0 (Compliance; research-inquiry@example.com)",
            "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
        }

        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(headers=headers, timeout=self.timeout_sec, follow_redirects=True)
            should_close_client = True

        try:
            while queue and len(visited_urls) < self.max_pages:
                current_url, depth = queue.pop(0)
                if current_url in visited_urls:
                    continue

                if not validate_url_safety(
                    current_url,
                    allowed_domains={allowed_domain},
                    allow_private_for_tests=self.allow_private_for_tests,
                ):
                    skipped_reasons.append({"url": current_url, "reason": "Cross-domain or unsafe destination"})
                    continue

                visited_urls.add(current_url)

                try:
                    resp = await client.get(current_url)
                except httpx.HTTPError as e:
                    warnings.append(f"HTTP error fetching {current_url}: {str(e)}")
                    continue

                if resp.status_code in (401, 403):
                    status = "ACCESS_BLOCKED"
                    warnings.append(f"Access blocked (HTTP {resp.status_code}) on {current_url}")
                    break

                if resp.status_code != 200:
                    skipped_reasons.append({"url": current_url, "reason": f"HTTP status {resp.status_code}"})
                    continue

                content_type = resp.headers.get("content-type", "").lower()

                # If the URL itself directly returns a PDF/PPTX
                if "application/pdf" in content_type or current_url.lower().endswith(".pdf"):
                    discovered_docs.append(
                        DiscoveredDocumentRecord(
                            url=current_url,
                            document_type="PDF",
                            title=current_url.split("/")[-1] or "Document",
                            discovered_at=datetime.now(timezone.utc).isoformat(),
                            file_bytes=resp.content,
                            file_size_bytes=len(resp.content),
                        )
                    )
                    if len(discovered_docs) >= self.max_documents:
                        break
                    continue

                # Parse HTML for links
                if "text/html" not in content_type:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    links_evaluated_count += 1
                    raw_href = a_tag["href"].strip()
                    if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                        continue

                    full_url = urljoin(current_url, raw_href)
                    link_text = a_tag.get_text(strip=True)

                    # Check for document endpoints
                    lower_url = full_url.lower()
                    if lower_url.endswith(".pdf") or lower_url.endswith(".pptx"):
                        if self.is_financial_link(full_url, link_text):
                            doc_type = "PPTX" if lower_url.endswith(".pptx") else "PDF"
                            discovered_docs.append(
                                DiscoveredDocumentRecord(
                                    url=full_url,
                                    document_type=doc_type,
                                    title=link_text or full_url.split("/")[-1],
                                    discovered_at=datetime.now(timezone.utc).isoformat(),
                                )
                            )
                            if len(discovered_docs) >= self.max_documents:
                                break
                        else:
                            skipped_reasons.append({"url": full_url, "reason": "Not recognized as a financial disclosure"})
                    elif depth + 1 <= self.max_depth and full_url not in visited_urls:
                        # Enqueue promising sub-pages (e.g. investor relations, financial tabs)
                        if self.is_financial_link(full_url, link_text):
                            queue.append((full_url, depth + 1))

                if len(discovered_docs) >= self.max_documents:
                    break

            if len(visited_urls) >= self.max_pages and not discovered_docs:
                status = "CRAWL_LIMIT_REACHED"
            elif discovered_docs:
                status = "COVERAGE_AVAILABLE"

            return WebsiteDiscoveryManifest(
                company_name=company_name,
                seed_url=seed_url,
                coverage_status=status,
                pages_inspected=len(visited_urls),
                links_evaluated=links_evaluated_count,
                visited_urls=sorted(list(visited_urls)),
                discovered_documents=discovered_docs,
                skipped_reasons=skipped_reasons[:50],
                warnings=warnings,
            )
        finally:
            if should_close_client:
                await client.aclose()
