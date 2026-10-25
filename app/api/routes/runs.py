"""Research Run Management Routes.

Endpoints:
- POST /api/runs (Create a new persistent research run)
- GET /api/runs/{run_id} (Retrieve run status and metadata)
- GET /api/runs/{run_id}/trace (Retrieve execution audit trail)
- POST /api/runs/{run_id}/review (Human review endpoint placeholder)
"""

from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_repository
from app.db.repository import Repository
from app.schemas.common import RunStatus
from app.schemas.requests import CreateRunRequest, SubmitReviewRequest
from app.schemas.runs import AuditEventResponse, RunResponse, RunTraceResponse

router = APIRouter(prefix="/runs", tags=["Research Runs"])


@router.post(
    "",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new financial research run",
    description="Registers and persists a new research run in the database with status 'pending'.",
)
def create_run(
    payload: CreateRunRequest,
    repo: Repository = Depends(get_repository),
):
    """Validate request, resolve company reference, persist run, and log audit event."""
    company_id = payload.company_id

    # Resolve company if ticker or name provided
    if not company_id and payload.company_ticker:
        existing_company = repo.get_company_by_ticker(payload.company_ticker)
        if existing_company:
            company_id = existing_company.id
        else:
            new_company = repo.create_company(
                name=payload.company_name or payload.company_ticker,
                ticker=payload.company_ticker,
                jurisdiction=payload.jurisdiction,
            )
            company_id = new_company.id

    # Generate unique run ID
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    # Persist ResearchRun record
    run = repo.create_run(
        run_id=run_id,
        research_question=payload.research_question,
        company_id=company_id,
        jurisdiction=payload.jurisdiction,
        requested_periods=payload.reporting_periods,
        input_document_ids=payload.document_ids,
        status=RunStatus.PENDING.value,
    )

    # Record initial audit event
    repo.create_event(
        run_id=run_id,
        node_or_stage="initialization",
        status_or_code="INFO",
        details={
            "action": "run_created",
            "research_question": payload.research_question,
            "analytical_areas": payload.analytical_areas,
            "document_count": len(payload.document_ids),
        },
    )

    company_ticker = payload.company_ticker
    if not company_ticker and run.company:
        company_ticker = run.company.ticker

    return RunResponse(
        run_id=run.id,
        status=RunStatus(run.status),
        research_question=run.research_question,
        company_id=run.company_id,
        company_ticker=company_ticker,
        jurisdiction=run.jurisdiction,
        current_stage="initialization",
        progress_percent=0,
        created_at=run.created_at,
        updated_at=run.updated_at,
        error_summary=run.error_summary,
        requested_periods=run.requested_periods,
        input_document_ids=run.input_document_ids,
        message="Research run registered successfully in 'pending' state. Multi-agent execution will commence in Phase 3.",
    )


@router.get(
    "/{run_id}",
    response_model=RunResponse,
    summary="Get status and details of a research run",
    description="Fetches the persistent run status, active stage, and parameters from SQLite.",
)
def get_run(
    run_id: str,
    repo: Repository = Depends(get_repository),
):
    """Retrieve persistent research run by ID."""
    run = repo.get_run_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run '{run_id}' not found.",
        )

    company_ticker = run.company.ticker if run.company else None

    return RunResponse(
        run_id=run.id,
        status=RunStatus(run.status),
        research_question=run.research_question,
        company_id=run.company_id,
        company_ticker=company_ticker,
        jurisdiction=run.jurisdiction,
        current_stage="initialization" if run.status == "pending" else run.status,
        progress_percent=0 if run.status == "pending" else (100 if run.status == "completed" else 50),
        created_at=run.created_at,
        updated_at=run.updated_at,
        error_summary=run.error_summary,
        requested_periods=run.requested_periods,
        input_document_ids=run.input_document_ids,
        message=f"Current run status: {run.status}",
    )


@router.get(
    "/{run_id}/trace",
    response_model=RunTraceResponse,
    summary="Retrieve execution audit trace",
    description="Returns chronological audit events logged for this research run.",
)
def get_run_trace(
    run_id: str,
    repo: Repository = Depends(get_repository),
):
    """Retrieve all execution events for the given run."""
    run = repo.get_run_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run '{run_id}' not found.",
        )

    events = repo.get_events_by_run_id(run_id)
    event_responses = [
        AuditEventResponse(
            event_id=e.id,
            run_id=e.run_id,
            node_or_stage=e.node_or_stage,
            event_timestamp=e.event_timestamp,
            status_or_code=e.status_or_code,
            duration_ms=e.duration_ms,
            details=e.details,
            model_or_parser_version=e.model_or_parser_version,
        )
        for e in events
    ]

    return RunTraceResponse(
        run_id=run_id,
        total_events=len(event_responses),
        events=event_responses,
    )


@router.post(
    "/{run_id}/execute",
    summary="Execute multi-agent research workflow",
    description="Invokes the compiled LangGraph workflow orchestrating 7 analysts, 3 judges, and the Research Quality Supervisor.",
)
async def execute_run(
    run_id: str,
    repo: Repository = Depends(get_repository),
):
    """Trigger execution of the multi-agent LangGraph workflow for an initialized run."""
    run = repo.get_run_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run '{run_id}' not found.",
        )

    from app.workflow.graph import research_graph_app

    initial_state = {
        "run_id": run.id,
        "research_question": run.research_question,
        "company_ticker": run.company.ticker if run.company else "UNKNOWN",
        "company_name": run.company.name if run.company else None,
        "jurisdiction": run.jurisdiction,
        "requested_periods": run.requested_periods,
        "document_ids": run.input_document_ids,
        "acquisition_mode": "combined" if run.input_document_ids else "sec_edgar",
        "remaining_repair_budget": 2,
    }

    final_state = await research_graph_app.ainvoke(initial_state)

    repo.db.expire_all()
    updated_run = repo.get_run_by_id(run_id)
    return {
        "run_id": run_id,
        "status": updated_run.status if updated_run else "completed",
        "verification_status": final_state.get("verification_status", "INDETERMINATE"),
        "report": final_state.get("report"),
    }


@router.post(
    "/{run_id}/review",
    summary="Submit human review sign-off",
    description="Endpoint for human analyst approval, qualification, or overrides.",
    status_code=status.HTTP_200_OK,
)
def submit_review(
    run_id: str,
    payload: SubmitReviewRequest,
    repo: Repository = Depends(get_repository),
):
    """Human review cockpit endpoint persisting reviewer sign-off and claim overrides."""
    run = repo.get_run_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research run '{run_id}' not found.",
        )

    decision_upper = payload.overall_decision.upper()
    valid_decisions = {"APPROVED", "QUALIFIED", "REJECTED"}
    if decision_upper not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid overall_decision '{payload.overall_decision}'. Must be one of: {sorted(list(valid_decisions))}",
        )

    run_status_map = {
        "APPROVED": "approved",
        "QUALIFIED": "completed_with_warnings",
        "REJECTED": "rejected",
    }
    repo.update_run_status(run_id, status=run_status_map[decision_upper])

    report = repo.get_report_by_run_id(run_id)
    if report:
        report.verification_status = decision_upper
        s_data = dict(report.structured_data or {})
        review_history = list(s_data.get("review_history", []))
        review_entry = {
            "decision": decision_upper,
            "reviewer_name": payload.reviewer_name,
            "comments": payload.comments,
            "claim_overrides": payload.claim_overrides,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        review_history.append(review_entry)
        s_data["review_history"] = review_history
        s_data["human_review"] = review_entry
        report.structured_data = s_data
        repo.db.commit()

    applied_overrides = []
    for override in payload.claim_overrides:
        claim_id = override.get("claim_id")
        new_status = override.get("new_status") or override.get("action")
        notes = override.get("notes") or override.get("rationale")
        if claim_id and new_status:
            updated_claim = repo.update_claim_verification(claim_id, str(new_status).upper(), notes)
            if updated_claim:
                applied_overrides.append({
                    "claim_id": claim_id,
                    "status": str(new_status).upper(),
                    "notes": notes,
                })

    repo.create_event(
        run_id=run_id,
        node_or_stage="human_review",
        status_or_code="HUMAN_REVIEW_SUBMITTED",
        details={
            "overall_decision": decision_upper,
            "reviewer_name": payload.reviewer_name,
            "comments": payload.comments,
            "claim_overrides": applied_overrides,
        },
    )

    return {
        "run_id": run_id,
        "overall_decision": decision_upper,
        "reviewer_name": payload.reviewer_name,
        "status": run_status_map[decision_upper],
        "verification_status": report.verification_status if report else decision_upper,
        "claim_overrides_applied": len(applied_overrides),
        "comments": payload.comments,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "message": f"Human review decision '{decision_upper}' recorded successfully.",
    }
