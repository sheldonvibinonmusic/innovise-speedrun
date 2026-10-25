"""Local Qdrant Vector Store Client.

Manages persistent on-disk or in-memory vector collections using qdrant-client:
- Collection: financial_chunks (384-dim, Cosine distance)
- Idempotent upserts with stable chunk IDs
- Filtered retrieval by company, document, and reporting period
- Full index rebuilding from persistent SQLite chunks
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "financial_chunks"
VECTOR_DIM = 384


class QdrantVectorStore:
    """Manages dense vector storage and nearest-neighbor search."""

    def __init__(self, path: Optional[Path] = None, in_memory: bool = False):
        if in_memory:
            self.client = QdrantClient(location=":memory:")
        else:
            storage_path = path or settings.qdrant_path
            storage_path.mkdir(parents=True, exist_ok=True)
            try:
                self.client = QdrantClient(path=str(storage_path))
            except RuntimeError as err:
                if "already accessed by another instance" in str(err).lower():
                    logger.warning(
                        "Qdrant storage folder %s locked by another process. Falling back to in-memory store: %s",
                        storage_path,
                        err,
                    )
                    self.client = QdrantClient(location=":memory:")
                else:
                    raise

        self.collection_name = COLLECTION_NAME
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create the target vector collection if it does not already exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=VECTOR_DIM,
                    distance=qmodels.Distance.COSINE,
                ),
            )

    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        vectors: List[List[float]],
    ) -> List[str]:
        """Idempotently insert or update chunk vectors in Qdrant."""
        if not chunks:
            return []

        points = []
        point_ids = []

        for chunk, vec in zip(chunks, vectors):
            chunk_id = chunk["chunk_id"]
            # Generate deterministic UUID5 from chunk_id for Qdrant compatibility
            point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))
            point_ids.append(point_uuid)

            payload = {
                "chunk_id": chunk_id,
                "document_id": chunk.get("document_id", ""),
                "company_ticker": chunk.get("company_ticker") or "",
                "page_number": chunk.get("page_number", 1),
                "chunk_type": chunk.get("chunk_type", "narrative"),
                "reporting_period": chunk.get("reporting_period") or "",
                "section_title": chunk.get("section_title") or "",
                "content": chunk.get("content", ""),
            }

            points.append(
                qmodels.PointStruct(
                    id=point_uuid,
                    vector=vec,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        return point_ids

    def search(
        self,
        query_vector: List[float],
        top_k: int = 15,
        company_ticker: Optional[str] = None,
        document_id: Optional[str] = None,
        reporting_period: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search dense vector index with optional metadata filters."""
        filter_conditions = []

        if company_ticker:
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="company_ticker",
                    match=qmodels.MatchValue(value=company_ticker.upper()),
                )
            )

        if document_id:
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="document_id",
                    match=qmodels.MatchValue(value=document_id),
                )
            )

        if reporting_period:
            filter_conditions.append(
                qmodels.FieldCondition(
                    key="reporting_period",
                    match=qmodels.MatchValue(value=reporting_period),
                )
            )

        query_filter = (
            qmodels.Filter(must=filter_conditions) if filter_conditions else None
        )

        # qdrant-client search / query_points
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
            ).points
        except AttributeError:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
            )

        hits = []
        for r in results:
            payload = r.payload or {}
            hits.append(
                {
                    "chunk_id": payload.get("chunk_id"),
                    "document_id": payload.get("document_id"),
                    "page_number": payload.get("page_number"),
                    "chunk_type": payload.get("chunk_type"),
                    "section_title": payload.get("section_title"),
                    "content": payload.get("content"),
                    "company_ticker": payload.get("company_ticker"),
                    "reporting_period": payload.get("reporting_period"),
                    "dense_score": float(r.score),
                }
            )
        return hits

    def delete_document_vectors(self, document_id: str) -> None:
        """Clear vectors associated with a document (for idempotent re-indexing)."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )
