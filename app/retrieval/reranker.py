"""Second-Stage Cross-Encoder Reranker.

Reranks a bounded shortlist of fused candidate passages using cross-attention scoring.
Default model: cross-encoder/ms-marco-MiniLM-L-6-v2.
Provides graceful degradation if the model is disabled or unavailable.
"""

from typing import Any, Dict, List, Optional, Tuple


class CrossEncoderReranker:
    """Evaluates query-passage pairs and sorts candidates by relevance score."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        enabled: bool = False,
    ):
        self.model_name = model_name
        self.enabled = enabled
        self._model = None

    def _load_model(self) -> bool:
        if not self.enabled:
            return False
        if self._model is not None:
            return True

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            return True
        except Exception:
            self._model = None
            return False

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Rerank candidates using cross-encoder.

        Returns (reranked_candidates, warning_message).
        """
        if not candidates:
            return [], None

        if not self.enabled or not self._load_model():
            warning = "Reranking skipped: cross-encoder is disabled or unavailable. Returning RRF fused order."
            for idx, c in enumerate(candidates):
                c["rerank_score"] = None
                c["final_rank"] = idx + 1
            return candidates[:top_k], warning

        pairs = [[query, c.get("content", "")] for c in candidates]
        try:
            scores = self._model.predict(pairs)
            for c, score in zip(candidates, scores):
                c["rerank_score"] = float(score)

            reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
            for idx, c in enumerate(reranked):
                c["final_rank"] = idx + 1

            return reranked[:top_k], None
        except Exception as e:
            warning = f"Reranker failed ({str(e)}). Falling back to RRF rankings."
            for idx, c in enumerate(candidates):
                c["rerank_score"] = None
                c["final_rank"] = idx + 1
            return candidates[:top_k], warning
