"""Retrieval and Hybrid RAG Search Routes.

Endpoints:
- POST /api/retrieval/search (Execute hybrid search: Dense + BM25 + RRF + Reranker + Facts)
- POST /api/retrieval/rebuild (Reconstruct search indices from SQLite)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.retrieval.service import retrieval_service
from app.schemas.requests import EvidenceItemSchema, RetrievalQueryRequest, RetrievalQueryResponse

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


@router.post(
    "/search",
    response_model=RetrievalQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute multi-stage hybrid retrieval",
    description="Combines dense vector search, lexical BM25, Reciprocal Rank Fusion, cross-encoder reranking, and structured facts.",
)
def search_evidence(
    payload: RetrievalQueryRequest,
    db: Session = Depends(get_db),
):
    """Execute hybrid search over processed financial disclosures."""
    res = retrieval_service.search(
        query=payload.query,
        db=db,
        company_ticker=payload.company_ticker,
        document_id=payload.document_id,
        reporting_period=payload.reporting_period,
        top_k=payload.top_k,
        include_structured_facts=payload.include_structured_facts,
        include_counter_evidence=payload.include_counter_evidence,
    )

    evidence_items = [
        EvidenceItemSchema(
            chunk_id=e.chunk_id,
            document_id=e.document_id,
            page_number=e.page_number,
            chunk_type=e.chunk_type,
            section_title=e.section_title,
            content=e.content,
            company_ticker=e.company_ticker,
            reporting_period=e.reporting_period,
            score=e.score,
            retrieval_routes=e.retrieval_routes,
            dense_score=e.dense_score,
            bm25_score=e.bm25_score,
            rerank_score=e.rerank_score,
        )
        for e in res.evidence
    ]

    counter_items = [
        EvidenceItemSchema(
            chunk_id=ce.chunk_id,
            document_id=ce.document_id,
            page_number=ce.page_number,
            chunk_type=ce.chunk_type,
            section_title=ce.section_title,
            content=ce.content,
            company_ticker=ce.company_ticker,
            reporting_period=ce.reporting_period,
            score=ce.score,
            retrieval_routes=ce.retrieval_routes,
            dense_score=ce.dense_score,
            bm25_score=ce.bm25_score,
        )
        for ce in res.counter_evidence
    ]

    return RetrievalQueryResponse(
        query=res.query,
        evidence=evidence_items,
        structured_facts=res.structured_facts,
        counter_evidence=counter_items,
        total_candidates=res.total_candidates,
        warning=res.warning,
    )


@router.post(
    "/rebuild",
    status_code=status.HTTP_200_OK,
    summary="Rebuild retrieval indices from SQLite",
    description="Reconstructs both Qdrant dense vector index and in-memory BM25 index from persistent database chunks.",
)
def rebuild_search_indices(
    db: Session = Depends(get_db),
):
    """Rebuild all vector and lexical indices from SQLite chunk table."""
    indexed_count = retrieval_service.rebuild_indices_from_db(db)
    return {
        "status": "SUCCESS",
        "message": f"Successfully reconstructed search indices from {indexed_count} persistent chunks.",
        "chunks_indexed": indexed_count,
    }
