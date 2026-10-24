"""BM25 Lexical Keyword Retrieval Engine.

Maintains in-memory inverted indices using rank_bm25 with specialized financial tokenization.
Preserves symbols ($ , %), negative parenthesized numbers, tickers, and accounting line items.
"""

import math
import re
from typing import Any, Dict, List, Optional
from rank_bm25 import BM25Okapi


def financial_tokenize(text: str) -> List[str]:
    """Tokenize financial text preserving numbers, currency, percentages, and tickers."""
    # Matches currency numbers ($245,120), percentages (15.4%),
    # parenthesized negative figures ((45,000)), and standard words/tickers
    tokens = re.findall(
        r"\$?\d+(?:,\d+)*(?:\.\d+)?%?|\(\$?\d+(?:,\d+)*(?:\.\d+)?\)|\b[a-zA-Z0-9]+(?:[-/][a-zA-Z0-9]+)*\b",
        text.lower(),
    )
    return [t for t in tokens if len(t) > 1 or t.isdigit()]


class FinancialBM25(BM25Okapi):
    """Lucene-style BM25 using non-negative IDF: ln(1 + (N - n + 0.5)/(n + 0.5)).

    Standard Okapi formula produces 0.0 or negative IDF on small document collections
    or high-frequency terms, which drops relevant matches in micro-benchmarks and focused searches.
    """

    def _calc_idf(self, nd):
        for word, freq in nd.items():
            self.idf[word] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))


class BM25Index:
    """Manages lexical retrieval across document chunks with metadata filtering."""

    def __init__(self):
        self.chunk_ids: List[str] = []
        self.corpus_metadata: List[Dict[str, Any]] = []
        self.bm25: Optional[FinancialBM25] = None

    def build_index(self, chunks: List[Dict[str, Any]]) -> None:
        """Construct BM25 index from a collection of chunk dictionaries."""
        self.chunk_ids = []
        self.corpus_metadata = []
        tokenized_corpus = []

        for chunk in chunks:
            content = chunk.get("content", "")
            tokens = financial_tokenize(content)
            if not tokens:
                tokens = ["empty_passage"]

            self.chunk_ids.append(chunk["chunk_id"])
            self.corpus_metadata.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk.get("document_id", ""),
                    "page_number": chunk.get("page_number", 1),
                    "chunk_type": chunk.get("chunk_type", "narrative"),
                    "section_title": chunk.get("section_title", ""),
                    "content": content,
                    "company_ticker": chunk.get("company_ticker", ""),
                    "reporting_period": chunk.get("reporting_period", ""),
                }
            )
            tokenized_corpus.append(tokens)

        if tokenized_corpus:
            self.bm25 = FinancialBM25(tokenized_corpus)
        else:
            self.bm25 = None

    def search(
        self,
        query: str,
        top_k: int = 15,
        company_ticker: Optional[str] = None,
        document_id: Optional[str] = None,
        reporting_period: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query lexical BM25 index with optional metadata filtering."""
        if not self.bm25 or not self.chunk_ids:
            return []

        tokens = financial_tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)

        # Pair scores with metadata and apply filters
        scored_candidates = []
        for idx, score in enumerate(scores):
            if score <= 0.0:
                continue

            meta = self.corpus_metadata[idx]

            if company_ticker and meta.get("company_ticker", "").upper() != company_ticker.upper():
                continue
            if document_id and meta.get("document_id") != document_id:
                continue
            if reporting_period and meta.get("reporting_period") != reporting_period:
                continue

            candidate = dict(meta)
            candidate["bm25_score"] = float(score)
            scored_candidates.append(candidate)

        # Sort descending by BM25 score
        scored_candidates.sort(key=lambda x: x["bm25_score"], reverse=True)
        return scored_candidates[:top_k]
