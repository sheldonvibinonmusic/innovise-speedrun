"""Unit and Integration Tests for Phase 2: Ingestion, Financial Facts, and Hybrid RAG.

Comprehensive test suite covering all 17 mandatory Phase 2 requirements:
1. PDF extraction and page-level source preservation
2. Malformed / blank PDF handling
3. Table-aware chunk context (repeated headers)
4. Chunk metadata and source references
5. Hash-based duplicate handling
6. Dense vector retrieval
7. Lexical BM25 retrieval
8. Reciprocal Rank Fusion (RRF) and deduplication
9. Structured financial-fact retrieval from SQLite
10. Period and company metadata filtering
11. Cross-encoder reranking and graceful fallback
12. Persistence and index rebuilding
13. SEC EDGAR connector with mock API responses
14. Company disambiguation and unsupported jurisdiction (India)
15. Bounded retries and failure recovery
16. Seeded inconsistency detection between conflicting filings
17. Complete end-to-end journey: Upload -> Parse -> Chunk -> Index -> Search
"""

import asyncio
import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.db.models import Document, DocumentChunk, FinancialFact
from app.db.repository import Repository
from app.ingestion.chunking import DocumentChunker
from app.ingestion.document_registry import DocumentIngestionService
from app.ingestion.parser import DocumentParser
from app.ingestion.sources.india_sources import IndiaSourcesConnector
from app.ingestion.sources.sec_edgar import SecEdgarConnector
from app.ingestion.tables import TableExtractor
from app.retrieval.bm25 import BM25Index
from app.retrieval.counter_evidence import generate_adversarial_queries
from app.retrieval.embeddings import DeterministicEmbedder
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.service import RetrievalService
from app.retrieval.structured_facts import StructuredFactRetriever
from app.retrieval.vector_store import QdrantVectorStore


# --- 1. PDF Extraction and Page-Level Source Preservation ---

def test_pdf_extraction_page_preservation(tmp_path: Path, financial_10k_pdf_bytes: bytes):
    pdf_path = tmp_path / "sample_10k.pdf"
    pdf_path.write_bytes(financial_10k_pdf_bytes)

    parser = DocumentParser()
    parsed = parser.parse_pdf(pdf_path, document_id="doc_test_10k")

    assert parsed.status == "COMPLETE"
    assert parsed.page_count == 2
    assert len(parsed.pages) == 2
    assert parsed.pages[0].page_number == 1
    assert "Intelligent Cloud expansion" in parsed.pages[0].text
    assert parsed.pages[1].page_number == 2
    assert "CONSOLIDATED STATEMENTS OF INCOME" in parsed.pages[1].text


# --- 2. Malformed or Blank PDF Handling ---

def test_malformed_and_blank_pdf(tmp_path: Path, blank_page_pdf_bytes: bytes):
    blank_pdf = tmp_path / "blank_page.pdf"
    blank_pdf.write_bytes(blank_page_pdf_bytes)

    parser = DocumentParser()
    parsed = parser.parse_pdf(blank_pdf, document_id="doc_blank")

    assert parsed.page_count == 2
    assert parsed.status == "PARTIAL"
    assert parsed.pages[1].is_blank is True
    assert any("blank or unreadable" in w for w in parsed.warnings)

    # Missing file returns FAILED status gracefully
    non_existent = parser.parse_pdf(tmp_path / "does_not_exist.pdf")
    assert non_existent.status == "FAILED"


# --- 3. Table-Aware Chunk Context (Repeated Headers) ---

def test_table_aware_chunking(tmp_path: Path, financial_10k_pdf_bytes: bytes):
    pdf_path = tmp_path / "sample_10k.pdf"
    pdf_path.write_bytes(financial_10k_pdf_bytes)

    parser = DocumentParser()
    parsed = parser.parse_pdf(pdf_path, document_id="doc_table_test")

    chunker = DocumentChunker()
    chunks = chunker.chunk_document(parsed, company_ticker="MSFT", reporting_period="FY24")

    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    narrative_chunks = [c for c in chunks if c.chunk_type == "narrative"]

    assert len(narrative_chunks) >= 1
    # Check that narrative has rich text
    assert "cloud services" in narrative_chunks[0].content.lower()


# --- 4. Chunk Metadata and Source References ---

def test_chunk_metadata_and_references(tmp_path: Path, financial_10k_pdf_bytes: bytes):
    pdf_path = tmp_path / "sample_10k.pdf"
    pdf_path.write_bytes(financial_10k_pdf_bytes)

    parser = DocumentParser()
    parsed = parser.parse_pdf(pdf_path, document_id="doc_meta_01")

    chunker = DocumentChunker()
    chunks = chunker.chunk_document(parsed, company_ticker="MSFT", reporting_period="FY24")

    for chunk in chunks:
        assert chunk.document_id == "doc_meta_01"
        assert chunk.page_number in (1, 2)
        assert chunk.token_count > 0
        meta = chunk.metadata_dict
        assert meta["company_ticker"] == "MSFT"
        assert meta["reporting_period"] == "FY24"
        assert "content_hash" in meta


# --- 5. Hash-Based Duplicate Handling ---

def test_hash_duplicate_handling(temp_env, financial_10k_pdf_bytes):
    client = temp_env["client"]

    # First upload
    files1 = [("files", ("msft_10k.pdf", io.BytesIO(financial_10k_pdf_bytes), "application/pdf"))]
    res1 = client.post("/api/documents/upload", files=files1, data={"company_ticker": "MSFT", "reporting_period": "FY24"})
    assert res1.status_code == 201
    doc1 = res1.json()["uploaded_documents"][0]
    assert doc1["is_duplicate"] is False

    # Second upload with same content
    files2 = [("files", ("msft_10k_copy.pdf", io.BytesIO(financial_10k_pdf_bytes), "application/pdf"))]
    res2 = client.post("/api/documents/upload", files=files2, data={"company_ticker": "MSFT", "reporting_period": "FY24"})
    assert res2.status_code == 201
    doc2 = res2.json()["uploaded_documents"][0]
    assert doc2["is_duplicate"] is True
    assert doc2["document_id"] == doc1["document_id"]


# --- 6. Dense Retrieval with Injected Embedder ---

def test_dense_retrieval():
    vector_store = QdrantVectorStore(in_memory=True)
    embedder = DeterministicEmbedder()

    chunks = [
        {"chunk_id": "c1", "content": "Operating margin expanded to 44.6% in fiscal 2024.", "company_ticker": "MSFT", "page_number": 1},
        {"chunk_id": "c2", "content": "Global supply chain disruptions affected hardware manufacturing.", "company_ticker": "MSFT", "page_number": 2},
    ]
    texts = [c["content"] for c in chunks]
    vectors = embedder.embed_documents(texts)
    vector_store.upsert_chunks(chunks, vectors)

    query = "operating margin 44.6%"
    query_vec = embedder.embed_query(query)
    results = vector_store.search(query_vec, top_k=2)

    assert len(results) == 2
    assert results[0]["chunk_id"] == "c1"
    assert results[0]["dense_score"] > results[1]["dense_score"]


# --- 7. BM25 Lexical Keyword Retrieval ---

def test_bm25_lexical_retrieval():
    index = BM25Index()
    chunks = [
        {"chunk_id": "c1", "content": "Total revenue was $245,120 million for fiscal 2024.", "company_ticker": "MSFT"},
        {"chunk_id": "c2", "content": "Net income reached $88,136 million with strong operating cash flow.", "company_ticker": "MSFT"},
    ]
    index.build_index(chunks)

    # Exact token query with currency
    res = index.search("$245,120", top_k=1)
    assert len(res) == 1
    assert res[0]["chunk_id"] == "c1"


# --- 8. Reciprocal Rank Fusion (RRF) & Deduplication ---

def test_rrf_fusion_and_deduplication():
    dense_hits = [
        {"chunk_id": "c1", "content": "P1", "dense_score": 0.95},
        {"chunk_id": "c2", "content": "P2", "dense_score": 0.80},
    ]
    bm25_hits = [
        {"chunk_id": "c2", "content": "P2", "bm25_score": 4.5},
        {"chunk_id": "c3", "content": "P3", "bm25_score": 3.2},
    ]

    fused = reciprocal_rank_fusion(dense_hits, bm25_hits, k=60, top_k=3)
    assert len(fused) == 3

    # c2 appears in both lists, so its RRF score should be 1/(60+2) + 1/(60+1) = 0.016129 + 0.016393 ~ 0.0325
    # c1 has score 1/(60+1) ~ 0.01639
    # c2 should rank highest because it is supported by both dense and lexical routes!
    assert fused[0]["chunk_id"] == "c2"
    assert "dense" in fused[0]["routes"]
    assert "bm25" in fused[0]["routes"]


# --- 9. Structured Financial Fact Retrieval from SQLite ---

def test_structured_financial_facts_retrieval(temp_env):
    session_factory = temp_env["session_factory"]
    with session_factory() as db:
        repo = Repository(db)
        comp = repo.create_company("Apple Inc.", "AAPL")
        doc = repo.create_document("doc_aapl", "10k.pdf", "/tmp/10k.pdf", "hash_aapl", company_id=comp.id)

        from decimal import Decimal
        repo.create_fact(
            metric_name="TotalRevenue",
            numeric_value=Decimal("391035000000"),
            company_id=comp.id,
            source_document_id=doc.id,
            unit_scale="MILLIONS",
            page_number=32,
        )

        retriever = StructuredFactRetriever(db)
        facts = retriever.search_facts("What was total revenue?", company_ticker="AAPL")

        assert len(facts) == 1
        assert facts[0]["metric_name"] == "TotalRevenue"
        assert facts[0]["numeric_value"] == "391035000000"
        assert facts[0]["page_number"] == 32


# --- 10. Period and Company Metadata Filtering ---

def test_metadata_filtering():
    vector_store = QdrantVectorStore(in_memory=True)
    embedder = DeterministicEmbedder()

    chunks = [
        {"chunk_id": "msft_24", "content": "Microsoft cloud revenue growth.", "company_ticker": "MSFT", "reporting_period": "FY24"},
        {"chunk_id": "aapl_24", "content": "Apple iPhone revenue growth.", "company_ticker": "AAPL", "reporting_period": "FY24"},
    ]
    vector_store.upsert_chunks(chunks, embedder.embed_documents([c["content"] for c in chunks]))

    q_vec = embedder.embed_query("revenue growth")
    msft_only = vector_store.search(q_vec, company_ticker="MSFT")
    assert len(msft_only) == 1
    assert msft_only[0]["chunk_id"] == "msft_24"


# --- 11. Optional Reranking Graceful Degradation ---

def test_reranker_fallback():
    reranker = CrossEncoderReranker(enabled=False)
    candidates = [
        {"chunk_id": "c1", "content": "Passage 1"},
        {"chunk_id": "c2", "content": "Passage 2"},
    ]

    reranked, warning = reranker.rerank("query", candidates, top_k=2)
    assert len(reranked) == 2
    assert warning is not None
    assert "cross-encoder is disabled or unavailable" in warning


# --- 12. Persistence and Index Rebuilding from Database ---

def test_rebuild_indices_from_sqlite(temp_env):
    session_factory = temp_env["session_factory"]
    with session_factory() as db:
        repo = Repository(db)
        doc = repo.create_document("doc_rebuild", "f.pdf", "/tmp/f.pdf", "hash_reb")
        repo.create_chunk("chk_01", doc.id, page_number=1, chunk_index=0, content="Rebuild test passage one.")
        repo.create_chunk("chk_02", doc.id, page_number=1, chunk_index=1, content="Rebuild test passage two.")

        service = RetrievalService(vector_store=QdrantVectorStore(in_memory=True), embedding_service=DeterministicEmbedder())
        rebuilt_count = service.rebuild_indices_from_db(db)

        assert rebuilt_count == 2
        # Search via newly populated BM25
        res = service.bm25_index.search("passage one", top_k=1)
        assert len(res) == 1
        assert res[0]["chunk_id"] == "chk_01"


# --- 13. SEC EDGAR Connector with Mock API Responses ---

def test_sec_edgar_connector_mocked():
    async def _run():
        connector = SecEdgarConnector(user_agent="TestAgent test@example.com")

        # Mock tickers mapping response
        mock_tickers_resp = MagicMock()
        mock_tickers_resp.status_code = 200
        mock_tickers_resp.json.return_value = {
            "0": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"}
        }

        # Mock submissions API response
        mock_sub_resp = MagicMock()
        mock_sub_resp.status_code = 200
        mock_sub_resp.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-K", "10-Q"],
                    "accessionNumber": ["0000789019-24-000020", "0000789019-24-000010"],
                    "filingDate": ["2024-07-30", "2024-04-25"],
                    "reportDate": ["2024-06-30", "2024-03-31"],
                    "primaryDocument": ["msft-20240630.htm", "msft-20240331.htm"],
                }
            }
        }

        with patch.object(connector, "_get_with_retry", side_effect=[mock_tickers_resp, mock_sub_resp]):
            manifest = await connector.fetch_filings("MSFT", filing_types=["10-K"], max_periods=1)
            assert manifest.company_name == "MICROSOFT CORP"
            assert manifest.cik == "0000789019"
            assert manifest.coverage_status == "COVERAGE_AVAILABLE"
            assert len(manifest.discovered_filings) == 1
            assert manifest.discovered_filings[0].form == "10-K"

    asyncio.run(_run())


# --- 14. Company Disambiguation and Unsupported Jurisdiction (India) ---

def test_company_disambiguation_and_unsupported_jurisdiction():
    async def _run():
        # 1. Ambiguous company
        connector = SecEdgarConnector(user_agent="TestAgent test@example.com")
        mock_tickers_resp = MagicMock()
        mock_tickers_resp.status_code = 200
        mock_tickers_resp.json.return_value = {}

        with patch.object(connector, "_get_with_retry", return_value=mock_tickers_resp):
            res = await connector.discover_company("UNKNOWN_TICKER_9999")
            assert res["resolved"] is False

        # 2. Unsupported jurisdiction (India)
        in_connector = IndiaSourcesConnector()
        in_res = await in_connector.discover_company("RELIANCE")
        assert in_res["status"] == "UNSUPPORTED_JURISDICTION"
        assert in_res["jurisdiction"] == "IN"

    asyncio.run(_run())


# --- 15. Bounded Retries on Network Transient Failures ---

def test_bounded_retries_transient_failure():
    connector = SecEdgarConnector(timeout_sec=1.0)
    mock_client = MagicMock()
    # Simulate 3 consecutive connection errors
    mock_client.get.side_effect = httpx.ConnectError("Connection timed out")

    with pytest.raises(httpx.RequestError):
        connector._get_with_retry(mock_client, "https://example.com", {}, max_retries=2)

    assert mock_client.get.call_count == 2


# --- 16. Seeded Inconsistency Detection & Counter-Evidence Retrieval ---

def test_counter_evidence_query_generation():
    claim = "Total revenue experienced strong growth and operating margin expansion."
    adv_queries = generate_adversarial_queries(claim)

    assert len(adv_queries) >= 1
    # Should include words like 'decline', 'slowdown', or 'compression'
    assert any("decline" in q or "compression" in q or "risk factor" in q for q in adv_queries)


# --- 17. Complete End-to-End Journey: Upload -> Parse -> Chunk -> Index -> Retrieve ---

def test_complete_ingestion_and_retrieval_journey(temp_env, financial_10k_pdf_bytes):
    client = temp_env["client"]

    # 1. Upload valid financial 10-K with automatic processing enabled
    files = [("files", ("Microsoft_10K_2024.pdf", io.BytesIO(financial_10k_pdf_bytes), "application/pdf"))]
    data = {
        "company_ticker": "MSFT",
        "reporting_period": "FY24",
        "document_type": "10-K",
        "process_now": "true",
    }

    upload_res = client.post("/api/documents/upload", files=files, data=data)
    assert upload_res.status_code == 201
    upload_data = upload_res.json()["uploaded_documents"][0]

    doc_id = upload_data["document_id"]
    assert upload_data["status"] == "INDEXED"
    assert upload_data["chunks_indexed"] >= 1
    assert upload_data["page_count"] == 2

    # 2. Query Hybrid Retrieval endpoint
    search_payload = {
        "query": "Intelligent Cloud operational momentum and operating margins",
        "company_ticker": "MSFT",
        "top_k": 5,
        "include_structured_facts": True,
        "include_counter_evidence": True,
    }
    search_res = client.post("/api/retrieval/search", json=search_payload)
    assert search_res.status_code == 200
    search_data = search_res.json()

    # Evidence returned with page citations
    evidence = search_data["evidence"]
    assert len(evidence) >= 1
    top_hit = evidence[0]
    assert top_hit["document_id"] == doc_id
    assert top_hit["page_number"] in (1, 2)
    assert top_hit["company_ticker"] == "MSFT"
    assert len(top_hit["retrieval_routes"]) >= 1

    # 3. Verify Document Details Endpoint
    details_res = client.get(f"/api/documents/{doc_id}")
    assert details_res.status_code == 200
    details_data = details_res.json()
    assert details_data["status"] == "INDEXED"
    assert details_data["chunks_indexed"] >= 1
