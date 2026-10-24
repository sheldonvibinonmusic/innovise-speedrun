"""Abstract Base Source Connector Interface.

All jurisdiction and regulatory source connectors (SEC EDGAR, India MCA/BSE, etc.)
implement this interface to ensure uniform document acquisition.

PHASE 0 STATUS: Scaffold only.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseSourceConnector(ABC):
    """Abstract interface for regulatory filing sources."""

    @abstractmethod
    async def discover_company(self, identifier: str) -> Dict[str, Any]:
        """Search company by ticker or regulatory identifier."""
        raise NotImplementedError

    @abstractmethod
    async def fetch_filings(
        self, company_id: str, filing_types: List[str], max_periods: int = 3
    ) -> List[Dict[str, Any]]:
        """Fetch regulatory filing metadata and file references."""
        raise NotImplementedError
