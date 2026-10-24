"""India Regulatory Source Connector Interface.

Connector scaffold for Indian corporate filings (BSE, NSE, and MCA).

PHASE 2 STATUS: Explicitly unsupported coverage.
Official exchange APIs for automated XBRL/PDF ingestion are not automated
in this prototype version. Returns explicit unsupported status without fabricating data.
"""

from typing import Any, Dict, List
from app.ingestion.sources.base import BaseSourceConnector


class IndiaSourcesConnector(BaseSourceConnector):
    """Connector interface for Indian regulatory equity filings."""

    async def discover_company(self, identifier: str) -> Dict[str, Any]:
        """Return explicit unsupported jurisdiction status for India."""
        return {
            "identifier": identifier,
            "resolved": False,
            "jurisdiction": "IN",
            "status": "UNSUPPORTED_JURISDICTION",
            "message": "Automated discovery for Indian filings (BSE/NSE/MCA) is not implemented in this prototype. Please upload filings via /api/documents/upload.",
        }

    async def fetch_filings(
        self, company_id: str, filing_types: List[str], max_periods: int = 3
    ) -> List[Dict[str, Any]]:
        """Return empty filings manifest with unsupported jurisdiction error."""
        return []
