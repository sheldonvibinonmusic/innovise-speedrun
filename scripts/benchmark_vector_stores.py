"""Benchmark Vector Store Engines: Qdrant vs Milvus Lite.

Evaluates dense retrieval performance under identical financial-research workloads:
- Identical 384-dimensional normalized vectors (DeterministicEmbedder)
- Identical 120 synthetic financial report chunks (MSFT, AAPL, GOOGL across FY22-FY24)
- Isolated temporary storage paths (zero production DB interference)
- Metrics: Ingestion time, Query latency (p50, p95, p99), Filtered retrieval accuracy,
  Persistence & reload integrity, and operational trade-offs.
"""

import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import Any, Dict, List
import numpy as np

from app.retrieval.embeddings import DeterministicEmbedder
from app.retrieval.vector_store import QdrantVectorStore


def generate_benchmark_dataset(count: int = 120) -> List[Dict[str, Any]]:
    """Generate deterministic synthetic financial passages with metadata."""
    tickers = ["MSFT", "AAPL", "GOOGL"]
    periods = ["FY22", "FY23", "FY24"]
    sections = [
        "Item 7. Management Discussion and Analysis",
        "Item 8. Financial Statements and Supplementary Data",
        "Item 1A. Risk Factors",
        "Item 7A. Quantitative Disclosures About Market Risk",
    ]
    templates = [
        "Total revenue reached ${val} million representing steady year-over-year growth in cloud services.",
        "Operating income margin was {pct}% reflecting sustained cost discipline and capital efficiency.",
        "Cash flow from operations totaled ${val} million providing liquidity for strategic investments.",
        "Foreign currency fluctuations and supply chain constraints presented commercial headwinds.",
        "Net income amounted to ${val} million after provision for income taxes and amortization.",
        "Capital expenditures for infrastructure and data centers increased to ${val} million.",
    ]

    chunks = []
    for i in range(count):
        ticker = tickers[i % len(tickers)]
        period = periods[(i // len(tickers)) % len(periods)]
        section = sections[i % len(sections)]
        tpl = templates[i % len(templates)]
        val = 10000 + (i * 739) % 250000
        pct = 15.0 + (i * 1.7) % 35.0
        content = f"{ticker} {period} {section}: " + tpl.format(val=val, pct=round(pct, 1))

        chunks.append({
            "chunk_id": f"chk_{ticker.lower()}_{period.lower()}_{i:04d}",
            "document_id": f"doc_{ticker.lower()}_{period.lower()}",
            "company_ticker": ticker,
            "reporting_period": period,
            "page_number": (i % 45) + 1,
            "chunk_type": "narrative" if (i % 3 != 0) else "table",
            "section_title": section,
            "content": content,
        })
    return chunks


def benchmark_qdrant(chunks: List[Dict[str, Any]], vectors: List[List[float]], queries: List[str], embedder: DeterministicEmbedder) -> Dict[str, Any]:
    """Benchmark local persistent Qdrant."""
    temp_dir = tempfile.mkdtemp(prefix="bench_qdrant_")
    from pathlib import Path
    storage_path = Path(temp_dir)

    try:
        # 1. Ingestion / Indexing
        t0 = time.perf_counter()
        store = QdrantVectorStore(path=storage_path, in_memory=False)
        store.upsert_chunks(chunks, vectors)
        ingest_time_ms = (time.perf_counter() - t0) * 1000.0

        # 2. Raw Search Latency (50 iterations)
        latencies = []
        for q in queries * 5:
            q_vec = embedder.embed_query(q)
            t_start = time.perf_counter()
            res = store.search(q_vec, top_k=5)
            latencies.append((time.perf_counter() - t_start) * 1000.0)

        # 3. Filtered Search (Ticker + Period)
        t_filter_start = time.perf_counter()
        q_vec = embedder.embed_query("cloud revenue growth")
        filtered_res = store.search(q_vec, top_k=5, company_ticker="MSFT", reporting_period="FY24")
        filtered_latency_ms = (time.perf_counter() - t_filter_start) * 1000.0
        all_match_filters = all(r.get("company_ticker") == "MSFT" and r.get("reporting_period") == "FY24" for r in filtered_res)

        # 4. Persistence Reload Test
        del store
        store_reloaded = QdrantVectorStore(path=storage_path, in_memory=False)
        reload_res = store_reloaded.search(q_vec, top_k=5)
        persistence_ok = len(reload_res) > 0

        # Disk size
        disk_size_kb = sum(f.stat().st_size for f in storage_path.glob("**/*") if f.is_file()) / 1024.0

        return {
            "engine": "Qdrant (Local Persistent)",
            "ingest_time_ms": round(ingest_time_ms, 2),
            "p50_latency_ms": round(float(np.percentile(latencies, 50)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
            "p99_latency_ms": round(float(np.percentile(latencies, 99)), 2),
            "filtered_latency_ms": round(filtered_latency_ms, 2),
            "filter_accuracy": 1.0 if all_match_filters and len(filtered_res) > 0 else 0.0,
            "persistence_reload_ok": persistence_ok,
            "disk_size_kb": round(disk_size_kb, 1),
            "top_hit_ids": [r["chunk_id"] for r in reload_res[:3]],
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def benchmark_milvus_lite(chunks: List[Dict[str, Any]], vectors: List[List[float]], queries: List[str], embedder: DeterministicEmbedder) -> Dict[str, Any]:
    """Benchmark local persistent Milvus Lite."""
    temp_dir = tempfile.mkdtemp(prefix="bench_milvus_")
    db_file = os.path.join(temp_dir, "milvus_bench.db")

    try:
        from pymilvus import MilvusClient

        # 1. Ingestion / Indexing
        t0 = time.perf_counter()
        client = MilvusClient(db_file)
        col_name = "financial_chunks"
        if client.has_collection(col_name):
            client.drop_collection(col_name)
        client.create_collection(collection_name=col_name, dimension=384, metric_type="COSINE")

        data = []
        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            data.append({
                "id": i,
                "vector": vec,
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "company_ticker": chunk["company_ticker"],
                "reporting_period": chunk["reporting_period"],
                "page_number": chunk["page_number"],
                "chunk_type": chunk["chunk_type"],
                "section_title": chunk["section_title"],
                "content": chunk["content"],
            })
        client.insert(collection_name=col_name, data=data)
        ingest_time_ms = (time.perf_counter() - t0) * 1000.0

        # 2. Raw Search Latency (50 iterations)
        latencies = []
        for q in queries * 5:
            q_vec = embedder.embed_query(q)
            t_start = time.perf_counter()
            res = client.search(
                collection_name=col_name,
                data=[q_vec],
                limit=5,
                output_fields=["chunk_id", "company_ticker", "reporting_period"]
            )
            latencies.append((time.perf_counter() - t_start) * 1000.0)

        # 3. Filtered Search (Ticker + Period)
        t_filter_start = time.perf_counter()
        q_vec = embedder.embed_query("cloud revenue growth")
        filtered_res = client.search(
            collection_name=col_name,
            data=[q_vec],
            limit=5,
            filter='company_ticker == "MSFT" and reporting_period == "FY24"',
            output_fields=["chunk_id", "company_ticker", "reporting_period"]
        )
        filtered_latency_ms = (time.perf_counter() - t_filter_start) * 1000.0
        hits = filtered_res[0] if filtered_res else []
        all_match_filters = all(h.get("entity", {}).get("company_ticker") == "MSFT" and h.get("entity", {}).get("reporting_period") == "FY24" for h in hits)

        # 4. Persistence Reload Test
        client.close()
        client_reloaded = MilvusClient(db_file)
        reload_res = client_reloaded.search(
            collection_name=col_name,
            data=[q_vec],
            limit=5,
            output_fields=["chunk_id"]
        )
        persistence_ok = len(reload_res[0]) > 0 if reload_res else False
        top_hits = [h.get("entity", {}).get("chunk_id") for h in reload_res[0][:3]] if reload_res else []
        client_reloaded.close()

        # Disk size
        disk_size_kb = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(temp_dir) for f in fs) / 1024.0

        return {
            "engine": "Milvus Lite (Local Persistent)",
            "ingest_time_ms": round(ingest_time_ms, 2),
            "p50_latency_ms": round(float(np.percentile(latencies, 50)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
            "p99_latency_ms": round(float(np.percentile(latencies, 99)), 2),
            "filtered_latency_ms": round(filtered_latency_ms, 2),
            "filter_accuracy": 1.0 if all_match_filters and len(hits) > 0 else 0.0,
            "persistence_reload_ok": persistence_ok,
            "disk_size_kb": round(disk_size_kb, 1),
            "top_hit_ids": top_hits,
        }
    finally:
        # Note: on Windows, the C++ faiss/milvus engine may retain file lock until process exit
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def main():
    print("=" * 65)
    print("VECTOR DATABASE RE-EVALUATION BENCHMARK: QDRANT VS MILVUS LITE")
    print("=" * 65)

    embedder = DeterministicEmbedder()
    chunks = generate_benchmark_dataset(120)
    vectors = embedder.embed_documents([c["content"] for c in chunks])

    test_queries = [
        "What was the total revenue growth in cloud services?",
        "Operating margin cost discipline and efficiency",
        "Operating cash flow and capital expenditure for infrastructure",
        "Foreign currency fluctuations and supply chain headwinds",
        "Net income after income taxes and amortization",
        "Capital allocation and liquidity for strategic investments",
        "Commercial hardware customer slowdown and operating margin",
        "Total debt maturity and cash equivalents headroom",
        "Segment revenue expansion and profitability",
        "Research and development investments across fiscal years",
    ]

    print(f"Dataset: {len(chunks)} chunks, 384-dim normalized vectors across 3 companies (MSFT, AAPL, GOOGL).")
    print(f"Queries: {len(test_queries)} unique financial queries, 50 search iterations per engine.\n")

    print("Running Qdrant benchmark...")
    qdrant_metrics = benchmark_qdrant(chunks, vectors, test_queries, embedder)

    print("Running Milvus Lite benchmark...")
    milvus_metrics = benchmark_milvus_lite(chunks, vectors, test_queries, embedder)

    # Print summary table
    print("\n" + "=" * 65)
    print(f"{'Metric':<30} | {'Qdrant (Local)':<16} | {'Milvus Lite':<16}")
    print("-" * 65)
    print(f"{'Ingestion Time (120 chunks)':<30} | {qdrant_metrics['ingest_time_ms']:>10.2f} ms | {milvus_metrics['ingest_time_ms']:>10.2f} ms")
    print(f"{'Search Latency p50':<30} | {qdrant_metrics['p50_latency_ms']:>10.2f} ms | {milvus_metrics['p50_latency_ms']:>10.2f} ms")
    print(f"{'Search Latency p95':<30} | {qdrant_metrics['p95_latency_ms']:>10.2f} ms | {milvus_metrics['p95_latency_ms']:>10.2f} ms")
    print(f"{'Search Latency p99':<30} | {qdrant_metrics['p99_latency_ms']:>10.2f} ms | {milvus_metrics['p99_latency_ms']:>10.2f} ms")
    print(f"{'Filtered Query Latency':<30} | {qdrant_metrics['filtered_latency_ms']:>10.2f} ms | {milvus_metrics['filtered_latency_ms']:>10.2f} ms")
    print(f"{'Filter Precision (Metadata)':<30} | {qdrant_metrics['filter_accuracy']*100:>9.1f}% | {milvus_metrics['filter_accuracy']*100:>9.1f}%")
    print(f"{'Persistence & Reopen Valid':<30} | {'Yes' if qdrant_metrics['persistence_reload_ok'] else 'No':>13} | {'Yes' if milvus_metrics['persistence_reload_ok'] else 'No':>13}")
    print(f"{'Disk Footprint':<30} | {qdrant_metrics['disk_size_kb']:>10.1f} KB | {milvus_metrics['disk_size_kb']:>10.1f} KB")
    print("=" * 65)

    # Compare top hit consistency
    q_top = qdrant_metrics.get("top_hit_ids", [])
    m_top = milvus_metrics.get("top_hit_ids", [])
    print(f"\nTop retrieved chunk IDs (Qdrant):     {q_top}")
    print(f"Top retrieved chunk IDs (Milvus Lite): {m_top}")
    overlap = len(set(q_top).intersection(set(m_top)))
    print(f"Top-3 Result Overlap: {overlap}/3 ({overlap/3*100:.1f}%)")


if __name__ == "__main__":
    main()
