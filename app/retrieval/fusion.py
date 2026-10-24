"""Reciprocal Rank Fusion (RRF) for Hybrid Retrieval.

Merges ranked candidate lists from Dense Vector Search and Lexical BM25 Search.
RRF_Score(d) = sum(1.0 / (k + rank_m(d))) where k=60 by default.
"""

from typing import Any, Dict, List, Optional


def reciprocal_rank_fusion(
    dense_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = 60,
    top_k: int = 15,
) -> List[Dict[str, Any]]:
    """Fuse dense vector rankings and lexical BM25 rankings using Reciprocal Rank Fusion.

    Returns unified candidate records with combined RRF scores and route provenance.
    """
    fused_candidates: Dict[str, Dict[str, Any]] = {}

    # 1. Process Dense Rankings
    for rank_idx, hit in enumerate(dense_results):
        chunk_id = hit["chunk_id"]
        rank = rank_idx + 1  # 1-based rank
        score_contribution = 1.0 / (k + rank)

        if chunk_id not in fused_candidates:
            fused_candidates[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": hit.get("document_id"),
                "page_number": hit.get("page_number"),
                "chunk_type": hit.get("chunk_type"),
                "section_title": hit.get("section_title"),
                "content": hit.get("content"),
                "company_ticker": hit.get("company_ticker"),
                "reporting_period": hit.get("reporting_period"),
                "rrf_score": score_contribution,
                "dense_rank": rank,
                "dense_score": hit.get("dense_score"),
                "bm25_rank": None,
                "bm25_score": None,
                "routes": ["dense"],
            }
        else:
            fused_candidates[chunk_id]["rrf_score"] += score_contribution
            fused_candidates[chunk_id]["dense_rank"] = rank
            fused_candidates[chunk_id]["dense_score"] = hit.get("dense_score")
            if "dense" not in fused_candidates[chunk_id]["routes"]:
                fused_candidates[chunk_id]["routes"].append("dense")

    # 2. Process BM25 Rankings
    for rank_idx, hit in enumerate(bm25_results):
        chunk_id = hit["chunk_id"]
        rank = rank_idx + 1
        score_contribution = 1.0 / (k + rank)

        if chunk_id not in fused_candidates:
            fused_candidates[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": hit.get("document_id"),
                "page_number": hit.get("page_number"),
                "chunk_type": hit.get("chunk_type"),
                "section_title": hit.get("section_title"),
                "content": hit.get("content"),
                "company_ticker": hit.get("company_ticker"),
                "reporting_period": hit.get("reporting_period"),
                "rrf_score": score_contribution,
                "dense_rank": None,
                "dense_score": None,
                "bm25_rank": rank,
                "bm25_score": hit.get("bm25_score"),
                "routes": ["bm25"],
            }
        else:
            fused_candidates[chunk_id]["rrf_score"] += score_contribution
            fused_candidates[chunk_id]["bm25_rank"] = rank
            fused_candidates[chunk_id]["bm25_score"] = hit.get("bm25_score")
            if "bm25" not in fused_candidates[chunk_id]["routes"]:
                fused_candidates[chunk_id]["routes"].append("bm25")

    # 3. Sort by total RRF score descending
    sorted_candidates = sorted(
        fused_candidates.values(),
        key=lambda x: x["rrf_score"],
        reverse=True,
    )

    return sorted_candidates[:top_k]
