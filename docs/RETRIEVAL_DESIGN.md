# Retrieval Architecture & Search Design

## 1. Overview: Multi-Stage Hybrid Retrieval

Financial disclosures feature dense narrative prose alongside intricate tabular financial data. A single retrieval method is inadequate:
- Dense embeddings capture conceptual similarities (e.g., "customer churn risk" vs. "client attrition") but struggle with precise numerical tokens or exact accounting terms.
- Lexical search (BM25) excels at exact matches for tickers, GAAP line items, and specific fiscal quarters, but lacks semantic understanding.

This system implements a **Two-Stage Hybrid Retrieval Pipeline** with structured fact retrieval and adversarial counter-evidence search.

```
                  User or Analyst Query
                            │
          ┌─────────────────┴─────────────────┐
          ▼                                   ▼
  [Dense Embedding]                    [Lexical Tokens]
(BAAI/bge-small-en-v1.5)                 (Rank-BM25)
          │                                   │
          ▼                                   ▼
   [Qdrant Search]                     [BM25 Scoring]
   (Cosine Sim, k=25)                 (BM25 Score, k=25)
          │                                   │
          └─────────────────┬─────────────────┘
                            ▼
              [Reciprocal Rank Fusion (RRF)]
                            │
                            ▼
                 Top-30 Unified Candidates
                            │
                            ▼
               [Cross-Encoder Reranker]
           (ms-marco-MiniLM-L-6-v2, Top-10)
                            │
          ┌─────────────────┴─────────────────┐
          ▼                                   ▼
[Context Window Expansion]        [Structured Fact Lookup]
  (Adjacent Chunks ±1)             (Authoritative SQLite DB)
          │                                   │
          └─────────────────┬─────────────────┘
                            ▼
               Grounded Ground-Truth Prompt
```

---

## 2. Component Details

### 2.1 Dense Vector Retrieval
- **Embedding Model**: `BAAI/bge-small-en-v1.5`
- **Dimensionality**: 384 dimensions
- **Vector Engine**: Qdrant (local persistent storage mode under `data/qdrant/`)
- **Distance Metric**: Cosine similarity
- **Chunk Metadata**: Each vector payload stores:
  - `document_id`: Target document identifier
  - `page_number`: Exact source page
  - `chunk_type`: `"TEXT"`, `"TABLE_ROW"`, `"FOOTNOTE"`
  - `fiscal_year`: Filing fiscal year
  - `fiscal_period`: `"FY"`, `"Q1"`, etc.

### 2.2 Lexical Retrieval (BM25)
- **Engine**: In-memory `rank-bm25` index built per loaded document/company.
- **Tokenization**: Custom financial tokenizer preserving symbols (`$`, `%`), periods in abbreviations, and negative signs (`(1,245)`).
- **Parameters**: $k_1 = 1.5$, $b = 0.75$.

### 2.3 Reciprocal Rank Fusion (RRF)
Combines dense ($R_{dense}$) and sparse ($R_{bm25}$) candidate rankings without requiring arbitrary score normalization:
$$RRF\_Score(d) = \sum_{m \in \{dense, bm25\}} \frac{1}{k + r_m(d)}$$
where $k = 60$ (standard smoothing constant) and $r_m(d)$ is the rank of document $d$ in method $m$.

### 2.4 Second-Stage Cross-Encoder Reranking
- **Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Evaluates the query-passage pair simultaneously via cross-attention.
- Narrows the top-30 fused candidates down to the top-8 to 10 most relevant chunks.

### 2.5 Structured Financial Fact Retrieval
When a query targets a specific metric (e.g., "What was operating cash flow in FY23?"):
- The system bypasses semantic search and queries the normalized `financial_facts` table in SQLite directly.
- Returns the exact value, unit, scale, and source table metadata.

### 2.6 Counter-Evidence Retrieval
When an analyst proposes a positive assertion (e.g., "Margins expanded across all divisions"):
- An adversarial query transformation is generated: `"margin contraction decline pressure risks"`.
- Hybrid retrieval specifically hunts for disconfirming statements or footnote caveats.

### 2.7 Context Expansion
For selected top passages, the system fetches immediately preceding and following chunks (`±1 chunk`) to ensure definitions and accounting footnotes are not severed by chunk boundaries.
