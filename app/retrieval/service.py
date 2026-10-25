"""Unified Retrieval Coordination Service.

Orchestrates multi-stage hybrid retrieval:
1. Dense Qdrant Vector Retrieval
2. Lexical BM25 Retrieval
3. Reciprocal Rank Fusion (RRF)
4. Optional Second-Stage Cross-Encoder Reranking
5. Authoritative Structured Fact Retrieval (SQLite)
6. Counter-Evidence Search
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk
from app.retrieval.bm25 import BM25Index
from app.retrieval.counter_evidence import generate_adversarial_queries
from app.retrieval.embeddings import BaseEmbeddingService, EmbeddingService
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.structured_facts import StructuredFactRetriever
from app.retrieval.vector_store import QdrantVectorStore


@dataclass
class EvidenceRecord:
    """Standardized evidence unit returned by the retrieval engine."""
    chunk_id: str
    document_id: str
    page_number: int
    chunk_type: str
    section_title: Optional[str]
    content: str
    company_ticker: Optional[str]
    reporting_period: Optional[str]
    score: float
    retrieval_routes: List[str]
    dense_score: Optional[float] = None
    bm25_score: Optional[float] = None
    rerank_score: Optional[float] = None


@dataclass
class RetrievalResponse:
    """Comprehensive response envelope for research and verification queries."""
    query: str
    evidence: List[EvidenceRecord] = field(default_factory=list)
    structured_facts: List[Dict[str, Any]] = field(default_factory=list)
    counter_evidence: List[EvidenceRecord] = field(default_factory=list)
    total_candidates: int = 0
    warning: Optional[str] = None


class RetrievalService:
    """Unified facade coordinating dense, sparse, structured, and counter-evidence retrieval."""

    def __init__(
        self,
        vector_store: Optional[QdrantVectorStore] = None,
        embedding_service: Optional[BaseEmbeddingService] = None,
        reranker: Optional[CrossEncoderReranker] = None,
    ):
        self.vector_store = vector_store or QdrantVectorStore()
        self.embedding_service = embedding_service or EmbeddingService()
        self.bm25_index = BM25Index()
        self.reranker = reranker or CrossEncoderReranker(enabled=False)

    def index_document_chunks(
        self,
        chunks: List[DocumentChunk],
        company_ticker: Optional[str] = None,
        reporting_period: Optional[str] = None,
    ) -> None:
        """Add new document chunks to both dense Qdrant and lexical BM25 indices."""
        if not chunks:
            return

        chunk_dicts = []
        texts = []
        for c in chunks:
            meta = c.metadata_dict
            ticker = company_ticker or meta.get("company_ticker", "")
            period = reporting_period or meta.get("reporting_period", "")
            cdict = {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "page_number": c.page_number,
                "chunk_type": c.chunk_type,
                "section_title": c.section_title or "",
                "content": c.content,
                "company_ticker": ticker,
                "reporting_period": period,
            }
            chunk_dicts.append(cdict)
            texts.append(c.content)

        # 1. Dense embeddings & Qdrant upsert
        vectors = self.embedding_service.embed_documents(texts)
        self.vector_store.upsert_chunks(chunk_dicts, vectors)

        # 2. Append to BM25 in-memory index
        all_chunks = self.bm25_index.corpus_metadata + chunk_dicts
        self.bm25_index.build_index(all_chunks)

    def rebuild_indices_from_db(self, db: Session) -> int:
        """Rebuild both Qdrant and BM25 indices from persistent SQLite chunks."""
        stmt = (
            select(DocumentChunk, Document.company_id, Document.reporting_period)
            .join(Document, DocumentChunk.document_id == Document.id, isouter=True)
        )
        rows = db.execute(stmt).all()
        if not rows:
            return 0

        chunk_dicts = []
        texts = []
        for chunk, company_id, period in rows:
            meta = chunk.metadata_dict
            ticker = meta.get("company_ticker", "")
            cdict = {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "page_number": chunk.page_number,
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title or "",
                "content": chunk.content,
                "company_ticker": ticker,
                "reporting_period": period or meta.get("reporting_period", ""),
            }
            chunk_dicts.append(cdict)
            texts.append(chunk.content)

        # Populate BM25
        self.bm25_index.build_index(chunk_dicts)

        # Populate Qdrant
        vectors = self.embedding_service.embed_documents(texts)
        self.vector_store.upsert_chunks(chunk_dicts, vectors)

        return len(chunk_dicts)

    def search(
        self,
        query: str,
        db: Optional[Session] = None,
        company_ticker: Optional[str] = None,
        document_id: Optional[str] = None,
        reporting_period: Optional[str] = None,
        top_k: int = 10,
        include_structured_facts: bool = True,
        include_counter_evidence: bool = False,
    ) -> RetrievalResponse:
        """Execute full hybrid retrieval pipeline."""
        warning = None

        # Ensure indices are built if chunks exist in database
        if db and (self.bm25_index.bm25 is None or len(self.bm25_index.chunk_ids) == 0):
            try:
                self.rebuild_indices_from_db(db)
            except Exception:
                pass

        # 1. Dense vector search
        query_vec = self.embedding_service.embed_query(query)
        dense_hits = self.vector_store.search(
            query_vector=query_vec,
            top_k=top_k * 2,
            company_ticker=company_ticker,
            document_id=document_id,
            reporting_period=reporting_period,
        )

        # 2. Lexical BM25 search
        bm25_hits = self.bm25_index.search(
            query=query,
            top_k=top_k * 2,
            company_ticker=company_ticker,
            document_id=document_id,
            reporting_period=reporting_period,
        )

        # 3. Reciprocal Rank Fusion
        fused = reciprocal_rank_fusion(dense_hits, bm25_hits, k=60, top_k=top_k * 2)

        # 4. Optional Cross-Encoder reranking
        reranked, rerank_warn = self.reranker.rerank(query, fused, top_k=top_k)
        if rerank_warn:
            warning = rerank_warn

        evidence_records = [
            EvidenceRecord(
                chunk_id=c["chunk_id"],
                document_id=c["document_id"],
                page_number=c["page_number"],
                chunk_type=c["chunk_type"],
                section_title=c.get("section_title"),
                content=c["content"],
                company_ticker=c.get("company_ticker"),
                reporting_period=c.get("reporting_period"),
                score=c.get("rerank_score") if c.get("rerank_score") is not None else c["rrf_score"],
                retrieval_routes=c["routes"],
                dense_score=c.get("dense_score"),
                bm25_score=c.get("bm25_score"),
                rerank_score=c.get("rerank_score"),
            )
            for c in reranked
        ]

        # 4B. Direct SQLite fallback if dense and sparse returned no candidates
        if len(evidence_records) == 0 and db:
            from app.db.models import DocumentChunk
            query_obj = db.query(DocumentChunk)
            if document_id:
                query_obj = query_obj.filter(DocumentChunk.document_id == document_id)
            elif company_ticker:
                from app.db.models import Company, Document
                comp = db.query(Company).filter(Company.ticker == company_ticker.upper()).first()
                if comp:
                    doc_ids_comp = [d.id for d in db.query(Document).filter(Document.company_id == comp.id).all()]
                    if doc_ids_comp:
                        query_obj = query_obj.filter(DocumentChunk.document_id.in_(doc_ids_comp))
            fallback_chunks = query_obj.limit(top_k).all()
            for chk in fallback_chunks:
                evidence_records.append(
                    EvidenceRecord(
                        chunk_id=chk.id,
                        document_id=chk.document_id,
                        page_number=chk.page_number,
                        chunk_type=chk.chunk_type,
                        section_title=chk.section_title,
                        content=chk.content,
                        company_ticker=company_ticker,
                        reporting_period=reporting_period,
                        score=0.5,
                        retrieval_routes=["sqlite_direct_fallback"],
                    )
                )

        # 5. Authoritative Structured Facts Lookup
        facts: List[Dict[str, Any]] = []
        if include_structured_facts and db:
            fact_retriever = StructuredFactRetriever(db)
            facts = fact_retriever.search_facts(
                query=query,
                company_ticker=company_ticker,
                period=reporting_period,
                limit=5,
            )

        # 6. Counter-Evidence Retrieval
        counter_evidence_records: List[EvidenceRecord] = []
        if include_counter_evidence:
            adv_queries = generate_adversarial_queries(query)
            for adv_q in adv_queries:
                adv_vec = self.embedding_service.embed_query(adv_q)
                adv_dense = self.vector_store.search(
                    query_vector=adv_vec,
                    top_k=3,
                    company_ticker=company_ticker,
                    document_id=document_id,
                    reporting_period=reporting_period,
                )
                adv_bm25 = self.bm25_index.search(
                    query=adv_q,
                    top_k=3,
                    company_ticker=company_ticker,
                    document_id=document_id,
                    reporting_period=reporting_period,
                )
                adv_fused = reciprocal_rank_fusion(adv_dense, adv_bm25, k=60, top_k=3)
                for ac in adv_fused:
                    # Do not duplicate existing top evidence
                    if any(e.chunk_id == ac["chunk_id"] for e in evidence_records):
                        continue
                    if any(ce.chunk_id == ac["chunk_id"] for ce in counter_evidence_records):
                        continue
                    counter_evidence_records.append(
                        EvidenceRecord(
                            chunk_id=ac["chunk_id"],
                            document_id=ac["document_id"],
                            page_number=ac["page_number"],
                            chunk_type=ac["chunk_type"],
                            section_title=ac.get("section_title"),
                            content=ac["content"],
                            company_ticker=ac.get("company_ticker"),
                            reporting_period=ac.get("reporting_period"),
                            score=ac["rrf_score"],
                            retrieval_routes=ac["routes"],
                            dense_score=ac.get("dense_score"),
                            bm25_score=ac.get("bm25_score"),
                        )
                    )

        return RetrievalResponse(
            query=query,
            evidence=evidence_records,
            structured_facts=facts,
            counter_evidence=counter_evidence_records,
            total_candidates=len(evidence_records),
            warning=warning,
        )

    def multi_hop_search(
        self,
        query: str,
        db: Session,
        company_ticker: Optional[str] = None,
        subquestions: Optional[List[str]] = None,
        max_hops: int = 2,
        top_k_per_hop: int = 5,
        document_ids: Optional[List[str]] = None,
    ) -> RetrievalResponse:
        """Execute bounded multi-hop retrieval with evidence graph traversal."""
        from app.db.repository import Repository

        repo = Repository(db)

        # 1. Query decomposition into explicit evidentiary requirements
        if not subquestions:
            subquestions = [
                query,
                f"{query} financial statement tables",
                f"{query} risk factors and operational headwinds",
            ]

        aggregated_evidence: Dict[str, EvidenceRecord] = {}
        all_facts: List[Dict[str, Any]] = []
        all_counter: Dict[str, EvidenceRecord] = {}
        warnings: List[str] = []

        # 2. Hop 1: Parallel subquestion hybrid search
        doc_id_filter = document_ids[0] if (document_ids and len(document_ids) == 1) else None
        for sq in subquestions:
            resp = self.search(
                query=sq,
                db=db,
                company_ticker=company_ticker,
                document_id=doc_id_filter,
                top_k=top_k_per_hop,
                include_structured_facts=True,
                include_counter_evidence=True,
            )
            for rec in resp.evidence:
                if rec.chunk_id not in aggregated_evidence:
                    aggregated_evidence[rec.chunk_id] = rec
            for f in resp.structured_facts:
                if not any(ef.get("fact_id") == f.get("fact_id") for ef in all_facts):
                    all_facts.append(f)
            for ce in resp.counter_evidence:
                if ce.chunk_id not in all_counter and ce.chunk_id not in aggregated_evidence:
                    all_counter[ce.chunk_id] = ce
            if resp.warning:
                warnings.append(resp.warning)

        # 3. Hop 2: Graph Relationship Traversal
        seed_entity_ids = list(aggregated_evidence.keys()) + [
            f"fact_{f.get('fact_id')}" for f in all_facts if f.get("fact_id")
        ]
        if company_ticker:
            seed_entity_ids.append(f"company_{company_ticker.upper()}")

        graph_rels = repo.traverse_evidence_subgraph(
            seed_entity_ids=seed_entity_ids, max_hops=max_hops, max_nodes=25
        )

        # Expand evidence with graph-connected chunks
        for rel in graph_rels:
            target_chunk_id = None
            if rel.source_id.startswith("chk_") and rel.source_id not in aggregated_evidence:
                target_chunk_id = rel.source_id
            elif rel.target_id.startswith("chk_") and rel.target_id not in aggregated_evidence:
                target_chunk_id = rel.target_id

            if target_chunk_id and target_chunk_id not in aggregated_evidence:
                chunk_obj = repo.get_chunk_by_id(target_chunk_id)
                if chunk_obj:
                    aggregated_evidence[target_chunk_id] = EvidenceRecord(
                        chunk_id=chunk_obj.id,
                        document_id=chunk_obj.document_id,
                        page_number=chunk_obj.page_number,
                        chunk_type=chunk_obj.chunk_type,
                        section_title=chunk_obj.section_title,
                        content=chunk_obj.content,
                        company_ticker=company_ticker,
                        reporting_period=rel.reporting_period,
                        score=float(rel.confidence_score),
                        retrieval_routes=["evidence_graph_traversal"],
                    )

        # 4. Direct SQLite Fallback if aggregated evidence is still empty
        if len(aggregated_evidence) == 0 and db:
            from app.db.models import DocumentChunk
            q_chunks = db.query(DocumentChunk)
            if document_ids:
                q_chunks = q_chunks.filter(DocumentChunk.document_id.in_(document_ids))
            elif company_ticker:
                from app.db.models import Company, Document
                comp = db.query(Company).filter(Company.ticker == company_ticker.upper()).first()
                if comp:
                    doc_ids_comp = [d.id for d in db.query(Document).filter(Document.company_id == comp.id).all()]
                    if doc_ids_comp:
                        q_chunks = q_chunks.filter(DocumentChunk.document_id.in_(doc_ids_comp))
            fallback_rows = q_chunks.limit(10).all()
            for chk in fallback_rows:
                if chk.id not in aggregated_evidence:
                    aggregated_evidence[chk.id] = EvidenceRecord(
                        chunk_id=chk.id,
                        document_id=chk.document_id,
                        page_number=chk.page_number,
                        chunk_type=chk.chunk_type,
                        section_title=chk.section_title,
                        content=chk.content,
                        company_ticker=company_ticker,
                        reporting_period=None,
                        score=0.5,
                        retrieval_routes=["sqlite_direct_fallback"],
                    )

        combined_evidence = list(aggregated_evidence.values())
        combined_evidence.sort(key=lambda x: x.score, reverse=True)

        return RetrievalResponse(
            query=query,
            evidence=combined_evidence,
            structured_facts=all_facts,
            counter_evidence=list(all_counter.values()),
            total_candidates=len(combined_evidence),
            warning="; ".join(set(warnings)) if warnings else None,
        )


# Global singleton retrieval service
retrieval_service = RetrievalService()
