"""Report Retrieval and Export Routes.

Endpoints:
- GET /api/reports/{run_id} (Retrieve structured report and verification ledger)
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_repository
from app.db.repository import Repository
from app.services.pdf_export import generate_report_pdf

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get(
    "/{run_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve final research report",
    description="Fetches synthesized multi-agent report, deterministic calculation ledger, and claim verification status.",
)
def get_report(
    run_id: str,
    repo: Repository = Depends(get_repository),
) -> Dict[str, Any]:
    """Retrieve synthesized report and verification ledger for a research run."""
    run = repo.get_run_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run '{run_id}' not found.",
        )

    report = repo.get_report_by_run_id(run_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report for run '{run_id}' has not been generated yet. Current status: '{run.status}'.",
        )

    claims = repo.get_claims_by_run_id(run_id)
    structured = report.structured_data or {}

    # Pre-fetch all referenced chunks to enrich claims with real document coordinates and excerpts
    all_ref_ids = set()
    for c in claims:
        if c.evidence_references:
            all_ref_ids.update(c.evidence_references)
    chunk_map = {chk.id: chk for chk in repo.get_chunks_by_ids(list(all_ref_ids))}

    enriched_claims = []
    for c in claims:
        first_chk = None
        if c.evidence_references:
            for ref in c.evidence_references:
                if ref in chunk_map:
                    first_chk = chunk_map[ref]
                    break
        doc_id = first_chk.document_id if first_chk else None
        page_num = first_chk.page_number if first_chk else None
        excerpt = first_chk.content if first_chk else c.claim_text
        sec_title = first_chk.section_title if first_chk else None

        enriched_claims.append({
            "claim_id": c.id,
            "claim_text": c.claim_text,
            "claim_type": c.claim_type,
            "materiality": c.materiality,
            "verification_status": c.verification_status,
            "status": c.verification_status,
            "verification_notes": c.verification_notes,
            "evidence_references": c.evidence_references or [],
            "fact_ids": c.fact_ids or [],
            "calculation_id": c.calculation_id,
            "document_id": doc_id or "Primary Source Filing",
            "page_number": page_num or 1,
            "evidence_excerpt": excerpt,
            "section_title": sec_title or "",
        })

    return {
        "report_id": report.id,
        "run_id": run.id,
        "company_ticker": run.company.ticker if run.company else None,
        "title": f"Financial Research Report: {run.company.name if run.company else run.id}",
        "executive_summary": report.executive_summary,
        "verification_status": report.verification_status,
        "quality_score": float(report.quality_score) if report.quality_score else 1.0,
        "markdown_content": report.report_markdown,
        "structured_data": structured,
        # Direct top-level access for frontend convenience & schema reliability
        "calculations": structured.get("calculations", []),
        "verdicts": structured.get("verdicts", []),
        "unresolved_uncertainties": structured.get("unresolved", []),
        "claims": enriched_claims,
        "created_at": report.created_at.isoformat(),
    }


@router.get(
    "/{run_id}/export/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Export financial research report as PDF",
    description="Generates an audit-grade PDF dossier containing executive summary, scorecard table, chart, verified claims, risks, and judge findings.",
)
@router.get(
    "/{run_id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    include_in_schema=False,
)
@router.get(
    "/{run_id}/export.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    include_in_schema=False,
)
def export_report_pdf(
    run_id: str,
    repo: Repository = Depends(get_repository),
) -> Response:
    """Generate and download publication-ready institutional research report PDF."""
    report_data = get_report(run_id=run_id, repo=repo)
    pdf_bytes = generate_report_pdf(report_data)
    ticker = report_data.get("company_ticker") or "REPORT"
    filename = f"financial_research_{ticker}_{run_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        },
    )
