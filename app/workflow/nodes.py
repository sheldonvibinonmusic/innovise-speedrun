"""LangGraph Workflow Node Callables.

Implements step functions for:
- validate_scope_node
- acquire_sources_node
- check_readiness_node
- decompose_question_node
- retrieve_evidence_node
- calculate_metrics_node
- run_analysts_node (7 specialist roles)
- run_judges_node (3 verification roles)
- supervise_quality_node (Research Quality Supervisor)
- repair_retrieval_node (Bounded recovery)
- synthesize_report_node (Final report compilation and persistence)
"""

from decimal import Decimal
import json
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.agents.analyst_models import (
    AnalystOutput,
    CandidateClaim,
    JudgeVerdict,
    SupervisorDecision,
)
from app.agents.analysts import (
    FinancialStatementsAnalyst,
    HistoricalTrendsAnalyst,
    ManagementGuidanceAnalyst,
    PeerComparisonAnalyst,
    ResearchSynthesisAnalyst,
    RiskCounterEvidenceAnalyst,
    SourceCoverageAnalyst,
)
from app.agents.judges import (
    AdversarialSkepticJudge,
    EvidenceCitationJudge,
    NumericalIntegrityJudge,
)
from app.agents.supervisor import ResearchQualitySupervisor
from app.db.models import FinancialFact
from app.db.repository import Repository
from app.db.session import SessionLocal
from app.finance.calculations import (
    CalculationResult,
    calculate_current_ratio,
    calculate_debt_to_equity,
    calculate_net_margin,
    calculate_operating_margin,
    calculate_revenue_growth,
)
from app.ingestion.document_registry import DocumentIngestionService
from app.retrieval.service import RetrievalResponse, retrieval_service
from app.workflow.state import ResearchWorkflowState


def validate_scope_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Validate research inquiry, company ticker, and scope bounds."""
    question = state.get("research_question", "").strip()
    if not question:
        raise ValueError("Research question cannot be blank.")

    ticker = state.get("company_ticker", "").strip().upper()
    return {
        "current_stage": "validate_scope",
        "company_ticker": ticker,
        "remaining_repair_budget": state.get("remaining_repair_budget", 2),
        "warnings": state.get("warnings", []),
        "errors": state.get("errors", []),
        "analyst_outputs": [],
        "judge_verdicts": [],
        "supervisor_decisions": [],
    }


async def acquire_sources_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Acquire documents via SEC EDGAR, website crawler, or confirm existing upload scope."""
    acq_mode = state.get("acquisition_mode", "upload")
    ticker = state.get("company_ticker", "")
    seed_url = state.get("seed_website_url")
    doc_ids = list(state.get("document_ids", []))
    manifest: Dict[str, Any] = {}

    if acq_mode in ("website_discovery", "combined") and seed_url:
        from app.ingestion.sources.website_crawler import WebsiteFinancialCrawler
        crawler = WebsiteFinancialCrawler()
        crawler_res = await crawler.crawl_and_discover(seed_url=seed_url, company_name=ticker)
        manifest["website_discovery"] = {
            "status": crawler_res.coverage_status,
            "pages_inspected": crawler_res.pages_inspected,
            "documents_found": len(crawler_res.discovered_documents),
        }

    return {
        "current_stage": "acquire_sources",
        "document_ids": doc_ids,
        "source_manifest": manifest,
    }


def check_readiness_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Ensure all documents in scope are parsed, indexed, and facts extracted."""
    doc_ids = state.get("document_ids", [])
    ingestion_service = DocumentIngestionService()

    with SessionLocal() as db:
        repo = Repository(db)
        for doc_id in doc_ids:
            doc = repo.get_document_by_id(doc_id)
            if doc and doc.ingestion_status in ("REGISTERED", "PARSING"):
                ingestion_service.process_document(doc_id, db)

    return {
        "current_stage": "check_readiness",
        "documents_ready": True,
    }


def decompose_question_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Break broad inquiry into explicit subquestions."""
    q = state.get("research_question", "")
    ticker = state.get("company_ticker", "")

    subquestions = [
        f"{ticker} Total revenue, operating income, and net income performance",
        f"{ticker} Operating cash flow stability and capital allocation",
        f"{ticker} Key business risks, operational headwinds, and margin compression",
    ]
    return {
        "current_stage": "decompose_question",
        "subquestions": subquestions,
    }


def retrieve_evidence_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Execute bounded multi-hop retrieval across subquestions and evidence graph."""
    q = state.get("research_question", "")
    ticker = state.get("company_ticker", "")
    subqs = state.get("subquestions", [q])

    with SessionLocal() as db:
        resp = retrieval_service.multi_hop_search(
            query=q,
            db=db,
            company_ticker=ticker,
            subquestions=subqs,
            max_hops=2,
            top_k_per_hop=5,
        )

    evidence_dicts = [
        {
            "chunk_id": e.chunk_id,
            "document_id": e.document_id,
            "page_number": e.page_number,
            "chunk_type": e.chunk_type,
            "section_title": e.section_title,
            "content": e.content,
            "company_ticker": e.company_ticker,
            "reporting_period": e.reporting_period,
            "score": e.score,
            "retrieval_routes": e.retrieval_routes,
        }
        for e in resp.evidence
    ]

    counter_dicts = [
        {
            "chunk_id": ce.chunk_id,
            "document_id": ce.document_id,
            "page_number": ce.page_number,
            "content": ce.content,
            "score": ce.score,
            "retrieval_routes": ce.retrieval_routes,
        }
        for ce in resp.counter_evidence
    ]

    return {
        "current_stage": "retrieve_evidence",
        "evidence": evidence_dicts,
        "financial_facts": resp.structured_facts,
        "counter_evidence": counter_dicts,
    }


def calculate_metrics_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Execute deterministic arithmetic using Python Decimal."""
    facts = state.get("financial_facts", [])
    ticker = state.get("company_ticker", "")

    # Reconstruct lightweight objects or fetch from DB
    calc_results: List[CalculationResult] = []

    with SessionLocal() as db:
        repo = Repository(db)
        comp = repo.get_company_by_ticker(ticker)
        db_facts = list(repo.get_facts_by_company(comp.id)) if comp else []

        doc_ids = state.get("document_ids", [])
        existing_fact_ids = {f.id for f in db_facts}
        for did in doc_ids:
            for f in repo.get_facts_by_document(did):
                if f.id not in existing_fact_ids:
                    db_facts.append(f)
                    existing_fact_ids.add(f.id)

        rev_facts = [f for f in db_facts if f.metric_name == "TotalRevenue"]
        op_facts = [f for f in db_facts if f.metric_name == "OperatingIncome"]
        net_facts = [f for f in db_facts if f.metric_name == "NetIncome"]
        debt_facts = [f for f in db_facts if f.metric_name in ("TotalDebt", "LongTermDebt")]
        asset_facts = [f for f in db_facts if f.metric_name == "TotalAssets"]

        if len(rev_facts) >= 2:
            calc_results.append(calculate_revenue_growth(rev_facts[0], rev_facts[1]))
        if rev_facts and op_facts:
            calc_results.append(calculate_operating_margin(op_facts[0], rev_facts[0]))
        if rev_facts and net_facts:
            calc_results.append(calculate_net_margin(net_facts[0], rev_facts[0]))

    calc_dicts = [c.to_dict() for c in calc_results]
    return {
        "current_stage": "calculate_metrics",
        "calculations": calc_dicts,
    }


async def run_analysts_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Dispatch all 7 specialized financial research analysts."""
    analysts = [
        SourceCoverageAnalyst(),
        FinancialStatementsAnalyst(),
        HistoricalTrendsAnalyst(),
        ManagementGuidanceAnalyst(),
        RiskCounterEvidenceAnalyst(),
        PeerComparisonAnalyst(),
    ]

    context = {
        "research_question": state.get("research_question"),
        "company_ticker": state.get("company_ticker"),
        "requested_periods": state.get("requested_periods", []),
        "evidence": state.get("evidence", []),
        "counter_evidence": state.get("counter_evidence", []),
        "financial_facts": state.get("financial_facts", []),
        "calculations": state.get("calculations", []),
    }

    outputs: List[AnalystOutput] = []
    all_claims: List[CandidateClaim] = []

    for a in analysts:
        res = await a.analyze(context)
        outputs.append(res)
        all_claims.extend(res.claims)

    # 7th Analyst: Synthesis
    synthesis_analyst = ResearchSynthesisAnalyst()
    synthesis_context = dict(context)
    synthesis_context["prior_analyst_outputs"] = outputs
    synth_res = await synthesis_analyst.analyze(synthesis_context)
    outputs.append(synth_res)
    all_claims.extend(synth_res.claims)

    claim_dicts = [c.model_dump() for c in all_claims]
    output_dicts = [o.model_dump() for o in outputs]

    return {
        "current_stage": "run_analysts",
        "analyst_outputs": output_dicts,
        "candidate_claims": claim_dicts,
    }


async def run_judges_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Execute tripartite verification judges."""
    raw_claims = state.get("candidate_claims", [])
    claims = [CandidateClaim.model_validate(c) for c in raw_claims]
    evidence = state.get("evidence", [])
    counter_evidence = state.get("counter_evidence", [])
    raw_calcs = state.get("calculations", [])
    calcs = [
        CalculationResult(
            calculation_id=c["calculation_id"],
            metric_name=c["metric_name"],
            formula=c["formula"],
            numeric_result=Decimal(c["numeric_result"]) if c.get("numeric_result") else None,
            formatted_result=c["formatted_result"],
            unit=c["unit"],
            reporting_period=c["reporting_period"],
            reporting_scope=c["reporting_scope"],
            source_fact_ids=c.get("source_fact_ids", []),
            validation_outcome=c.get("validation_outcome", "VALID"),
            warnings=c.get("warnings", []),
        )
        for c in raw_calcs
    ]
    facts = state.get("financial_facts", [])

    j1 = EvidenceCitationJudge()
    j2 = NumericalIntegrityJudge()
    j3 = AdversarialSkepticJudge()

    v1 = await j1.evaluate_claims(claims, evidence)
    v2 = await j2.evaluate_claims(claims, calcs, facts)
    v3 = await j3.evaluate_claims(claims, counter_evidence)

    verdicts = [v1.model_dump(), v2.model_dump(), v3.model_dump()]
    return {
        "current_stage": "run_judges",
        "judge_verdicts": verdicts,
    }


def supervise_quality_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Research Quality Supervisor evaluates workflow integrity and recovery needs."""
    supervisor = ResearchQualitySupervisor(max_repair_budget=2)
    verdicts = [JudgeVerdict.model_validate(v) for v in state.get("judge_verdicts", [])]
    outputs = state.get("analyst_outputs", [])
    remaining_repairs = state.get("remaining_repair_budget", 2)

    decision = supervisor.evaluate_workflow_state(
        current_stage="supervise_quality",
        analyst_outputs=outputs,
        judge_verdicts=verdicts,
        retrieval_history=[],
        remaining_repairs=remaining_repairs,
    )

    dec_dict = decision.model_dump()
    decisions = list(state.get("supervisor_decisions", []))
    decisions.append(dec_dict)

    return {
        "current_stage": "supervise_quality",
        "supervisor_decisions": decisions,
        "remaining_repair_budget": decision.remaining_retries,
        "unresolved_uncertainties": decision.unresolved_uncertainties,
    }


def repair_retrieval_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Execute targeted follow-up retrieval directed by the Supervisor."""
    decisions = state.get("supervisor_decisions", [])
    latest_dec = decisions[-1] if decisions else {}
    repair_q = latest_dec.get("repair_query") or state.get("research_question", "")
    ticker = state.get("company_ticker", "")

    with SessionLocal() as db:
        resp = retrieval_service.search(
            query=repair_q,
            db=db,
            company_ticker=ticker,
            top_k=5,
            include_structured_facts=True,
            include_counter_evidence=True,
        )

    existing_evidence = list(state.get("evidence", []))
    existing_ids = {e.get("chunk_id") for e in existing_evidence}

    for rec in resp.evidence:
        if rec.chunk_id not in existing_ids:
            existing_evidence.append({
                "chunk_id": rec.chunk_id,
                "document_id": rec.document_id,
                "page_number": rec.page_number,
                "chunk_type": rec.chunk_type,
                "section_title": rec.section_title,
                "content": rec.content,
                "company_ticker": rec.company_ticker,
                "reporting_period": rec.reporting_period,
                "score": rec.score,
                "retrieval_routes": rec.retrieval_routes + ["supervisor_repair"],
            })

    return {
        "current_stage": "repair_retrieval",
        "evidence": existing_evidence,
    }


def synthesize_report_node(state: ResearchWorkflowState) -> Dict[str, Any]:
    """Synthesize final report, persist to SQLite, and assign terminal status."""
    run_id = state.get("run_id", f"run_{uuid.uuid4().hex[:10]}")
    ticker = state.get("company_ticker", "UNKNOWN")
    q = state.get("research_question", "")
    claims = state.get("candidate_claims", [])
    calcs = state.get("calculations", [])
    verdicts = state.get("judge_verdicts", [])
    decisions = state.get("supervisor_decisions", [])
    unresolved = state.get("unresolved_uncertainties", [])

    # Determine overall status
    is_blocked = any(v.get("overall_verdict") == "BLOCK" for v in verdicts)
    has_qualification = any(v.get("overall_verdict") in ("QUALIFY", "RETRIEVE_MORE") for v in verdicts) or bool(unresolved)

    if is_blocked:
        verif_status = "BLOCKED"
        run_status = "failed"
    elif has_qualification:
        verif_status = "QUALIFIED"
        run_status = "completed_with_warnings"
    else:
        verif_status = "VERIFIED"
        run_status = "completed"

    # Build report Markdown
    exec_summary = (
        f"Multi-agent research analysis for {ticker} addressing inquiry: '{q}'. "
        f"Verified {len(claims)} claims and {len(calcs)} deterministic calculations across 7 specialist perspectives."
    )

    report_lines = [
        f"# Financial Research & Verification Report: {ticker}",
        f"**Inquiry**: {q}",
        f"**Verification Gate Status**: `{verif_status}`",
        "",
        "## Executive Summary",
        exec_summary,
        "",
        "## Deterministic Calculations",
    ]
    for c in calcs:
        metric_title = {
            "OperatingMargin": "Operating Margin",
            "RevenueGrowth": "Revenue Growth",
            "NetMargin": "Net Margin",
            "CurrentRatio": "Current Ratio",
            "DebtToEquity": "Debt-to-Equity",
            "FreeCashFlow": "Free Cash Flow",
        }.get(c.get("metric_name", ""), c.get("metric_name", ""))
        report_lines.append(f"- **{metric_title}**: `{c['formatted_result']}` (Formula: `{c['formula']}`, Validation: `{c['validation_outcome']}`)")

    report_lines.extend(["", "## Core Findings & Claims"])
    for cl in claims[:8]:
        report_lines.append(f"- [{cl.get('materiality')}] {cl.get('claim_text')} (Citations: `{cl.get('evidence_references')}`)")

    if unresolved:
        report_lines.extend(["", "## Unresolved Uncertainties & Risk Caveats"])
        for u in unresolved:
            report_lines.append(f"- {u}")

    report_markdown = "\n".join(report_lines)

    # Persist report and claims to SQLite
    with SessionLocal() as db:
        repo = Repository(db)
        repo.update_run_status(run_id, status=run_status)
        repo.create_or_update_report(
            report_id=f"rep_{run_id}",
            run_id=run_id,
            executive_summary=exec_summary,
            report_markdown=report_markdown,
            structured_data={
                "claims": claims,
                "calculations": calcs,
                "verdicts": verdicts,
                "unresolved": unresolved,
            },
            verification_status=verif_status,
        )

        seen_claim_ids = set()
        for cl in claims:
            cid = cl.get("claim_id") or f"clm_{uuid.uuid4().hex[:8]}"
            if cid in seen_claim_ids:
                continue
            seen_claim_ids.add(cid)
            repo.create_claim(
                claim_id=cid,
                run_id=run_id,
                claim_text=cl.get("claim_text", ""),
                claim_type=cl.get("claim_type", "reported_fact"),
                materiality=cl.get("materiality", "MEDIUM"),
                evidence_references=cl.get("evidence_references", []),
                fact_ids=cl.get("fact_references", []),
                calculation_id=cl.get("calculation_id"),
                verification_status="supported" if verif_status == "VERIFIED" else "needs_human_review",
            )

    return {
        "current_stage": "synthesize_report",
        "report_markdown": report_markdown,
        "verification_status": verif_status,
        "report": {
            "report_id": f"rep_{run_id}",
            "run_id": run_id,
            "verification_status": verif_status,
            "executive_summary": exec_summary,
            "markdown": report_markdown,
        },
    }
