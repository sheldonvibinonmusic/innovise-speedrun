"""Report Retrieval and Export Routes.

Endpoints:
- GET /api/reports/{run_id} (Retrieve structured report and verification ledger)
"""

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_repository
from app.db.repository import Repository

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

    return {
        "report_id": report.id,
        "run_id": run.id,
        "company_ticker": run.company.ticker if run.company else None,
        "title": f"Financial Research Report: {run.company.name if run.company else run.id}",
        "executive_summary": report.executive_summary,
        "verification_status": report.verification_status,
        "quality_score": float(report.quality_score) if report.quality_score else 1.0,
        "markdown_content": report.report_markdown,
        "structured_data": report.structured_data,
        "claims": [
            {
                "claim_id": c.id,
                "claim_text": c.claim_text,
                "claim_type": c.claim_type,
                "materiality": c.materiality,
                "verification_status": c.verification_status,
                "verification_notes": c.verification_notes,
                "evidence_references": c.evidence_references,
                "fact_ids": c.fact_ids,
                "calculation_id": c.calculation_id,
            }
            for c in claims
        ],
        "created_at": report.created_at.isoformat(),
    }
