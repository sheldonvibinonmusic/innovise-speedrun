"""Company Discovery and Regulatory Source Connector Routes.

Endpoints:
- POST /api/company/discover (Official SEC EDGAR and International source discovery)
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_repository
from app.db.repository import Repository
from app.ingestion.sources.india_sources import IndiaSourcesConnector
from app.ingestion.sources.sec_edgar import SecEdgarConnector
from app.schemas.requests import CompanyDiscoverRequest, CompanyDiscoverResponse, DiscoveredFilingSchema

router = APIRouter(prefix="/company", tags=["Company"])


@router.post(
    "/discover",
    response_model=CompanyDiscoverResponse,
    status_code=status.HTTP_200_OK,
    summary="Discover company filings via regulatory sources",
    description="Discovers regulatory filings and reports source coverage using official SEC EDGAR APIs.",
)
async def discover_company(
    payload: CompanyDiscoverRequest,
    repo: Repository = Depends(get_repository),
):
    """Discover company regulatory filings and return coverage manifest."""
    jurisdiction = (payload.jurisdiction or "US").upper()

    # 1. Indian Jurisdiction Connector Handling
    if jurisdiction == "IN":
        india_connector = IndiaSourcesConnector()
        india_res = await india_connector.discover_company(payload.ticker_or_cik)
        return CompanyDiscoverResponse(
            company_name=payload.ticker_or_cik,
            cik="",
            ticker=payload.ticker_or_cik.upper(),
            jurisdiction="IN",
            coverage_status="UNSUPPORTED_JURISDICTION",
            requested_period=payload.period,
            available_periods=[],
            discovered_filings=[],
            warnings=[india_res.get("message", "Unsupported jurisdiction.")],
        )

    # 2. US SEC EDGAR Connector Handling
    sec_connector = SecEdgarConnector()
    try:
        manifest = await sec_connector.fetch_filings(
            company_id=payload.ticker_or_cik,
            filing_types=payload.filing_types,
            max_periods=payload.max_periods,
            period_filter=payload.period,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SEC EDGAR gateway error during discovery: {str(exc)}",
        )

    # Automatically register company in database if resolved successfully
    if manifest.coverage_status in ("COVERAGE_AVAILABLE", "NO_FILINGS") and manifest.cik:
        existing = repo.get_company_by_ticker(manifest.ticker)
        if not existing:
            repo.create_company(
                name=manifest.company_name,
                ticker=manifest.ticker,
                jurisdiction="US",
                external_source_id=manifest.cik,
            )

    filings_schemas = [
        DiscoveredFilingSchema(
            accession_number=f.accession_number,
            form=f.form,
            filing_date=f.filing_date,
            report_date=f.report_date,
            primary_document=f.primary_document,
            document_url=f.document_url,
            fiscal_period=f.fiscal_period,
        )
        for f in manifest.discovered_filings
    ]

    return CompanyDiscoverResponse(
        company_name=manifest.company_name,
        cik=manifest.cik,
        ticker=manifest.ticker,
        jurisdiction="US",
        coverage_status=manifest.coverage_status,
        requested_period=manifest.requested_period,
        available_periods=manifest.available_periods,
        discovered_filings=filings_schemas,
        warnings=manifest.warnings,
    )
