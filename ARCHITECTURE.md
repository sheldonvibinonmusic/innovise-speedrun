# System Architecture: Trustworthy Multi-Agent Financial Research

## 1. Architectural Overview & Design Philosophy

The Trustworthy Multi-Agent Financial Research and Decision Support System enforces an uncompromising principle: **Financial truth is anchored in immutable evidence and deterministic computation, not stochastic generation.**

```
+------------------------------------------------------------------------------------+
|                               Vanilla ES-Module Frontend                           |
|      (Research Console, Document Vault, Evidence Inspector, Review Cockpit)        |
+-----------------------------------------+------------------------------------------+
                                          | JSON over REST (Fetch)
                                          v
+------------------------------------------------------------------------------------+
|                                FastAPI Application Layer                           |
|        (Route Handlers, Pydantic Schema Validation, Security Boundaries)           |
+-----------------------------------------+------------------------------------------+
                                          | Job Trigger & Query State
                                          v
+------------------------------------------------------------------------------------+
|                         LangGraph Research Orchestration                           |
|           (Explicit State Graph, Bounded Retries, Deterministic Gates)             |
+-------------------+------------------------------------+---------------------------+
                    |                                    |
                    v                                    v
+--------------------------------------+   +-----------------------------------------+
|    Source Acquisition & Ingestion    |   |     Financial Knowledge & Retrieval     |
| - SEC EDGAR / File Upload Validation |   | - Authoritative SQLite DB (Facts & Meta)|
| - Docling / PyMuPDF Layout Parsing   |   | - Qdrant Vector DB (Dense Embeddings)   |
| - Table Extraction & SHA-256 Hashing |   | - BM25 Lexical Search & RRF Fusion      |
+--------------------------------------+   | - Cross-Encoder Reranker & Counter-Evid |
                                           +-----------------------------------------+
                                                         |
                                                         v
+------------------------------------------------------------------------------------+
|                         Seven Specialized Research Analysts                        |
|  1. Profitability  2. Cash Flow  3. Liquidity/Debt  4. Historical Trends           |
|  5. Business & Risk  6. Evidence Research  7. Data Quality & Anomaly Detection     |
+-----------------------------------------+------------------------------------------+
                                          | Proposed Claims & Citations
                                          v
+------------------------------------------------------------------------------------+
|                     Claim Registry & Tripartite Audit Judges                       |
|   - Evidence & Citation Auditor     (Checks exact source support & bounds)         |
|   - Financial Integrity Auditor     (Validates arithmetic, formulas, and balance)  |
|   - Adversarial Skeptic             (Hunts counter-evidence and disconfirmations)  |
+-----------------------------------------+------------------------------------------+
                                          | Deterministic Verification Gates
                                          | (PASS / QUALIFY / RETRIEVE_MORE / BLOCK)
                                          v
+------------------------------------------------------------------------------------+
|                   Report Generation & Human Review Governance                      |
|       - Structured JSON & Markdown Synthesis with Traceable Footnotes              |
|       - Analyst Sign-off, Item-by-item Override, and Feedback Persistence         |
+------------------------------------------------------------------------------------+
```

---

## 2. Key Subsystems and Design Invariants

### 2.1 Authoritative Dual-Store Model (SQLite vs. Qdrant)
- **SQLite Database**: The single authoritative source of truth for all structured financial facts (revenue, net income, balance sheet items, ratios), job runs, claim registries, audit trails, and user feedback.
- **Qdrant Vector Store**: An auxiliary semantic retrieval index for textual chunks, disclosures, footnotes, and risk factors. Vector search never supersedes verified tabular facts in SQLite.
- **Original Source Files**: Preserved locally under `data/raw/` with SHA-256 integrity hashes to allow bit-for-bit audit verification.

### 2.2 Independent Analytical Branches & Fault Isolation
- The seven analyst roles are logical research responsibilities:
  1. **Profitability**: Margin dynamics, revenue quality, cost structures.
  2. **Cash Flow**: Free cash flow conversion, operating cash trends, capex discipline.
  3. **Liquidity & Debt**: Solvency ratios, debt maturity profiles, covenant headroom.
  4. **Historical Trends**: Multi-year CAGRs, structural shifts, cyclical inflection points.
  5. **Business & Risk**: Competitive moat, regulatory risks, MD&A disclosures.
  6. **Evidence Research**: Targeted query expansion, contextual fact retrieval.
  7. **Data Quality & Anomaly**: Benford's law indications, restatements, round-number anomalies.
- **Fault Tolerance**: If an individual analyst branch encounters missing data or failure, it emits an explicit `INDETERMINATE` or `QUALIFY` state rather than failing the entire research run.

### 2.3 Tripartite Audit and Deterministic Gates
Claims emitted by analysts must pass through three verification checkpoints:
1. **Evidence & Citation Auditor**: Checks that the cited document chunk genuinely contains the assertions made.
2. **Financial Integrity Auditor**: Deterministically validates that calculated figures equal `formula(inputs)`.
3. **Adversarial Skeptic**: Actively queries the retrieval engine for contradicting statements in prior disclosures or risk factors.

Verdict options are strictly bounded:
- `PASS`: Claim verified against source document and calculation rules.
- `QUALIFY`: Minor discrepancy, uncertainty, or estimation acknowledged.
- `RETRIEVE_MORE`: Information insufficient; triggers a bounded secondary retrieval loop.
- `BLOCK`: Critical contradiction, mathematical falsehood, or hallucination detected.
- `INDETERMINATE`: Source material lacks verifiable information on the requested metric.

### 2.4 Retrieval Architecture
- **Dense Embeddings**: `BAAI/bge-small-en-v1.5` for English financial semantics.
- **Lexical Indexing**: BM25 for precise token matching (tickers, specific accounting line items, dates).
- **Reciprocal Rank Fusion (RRF)**: Combines dense and sparse candidate sets.
- **Second-Stage Reranking**: Cross-encoder model (`ms-marco-MiniLM-L-6-v2`) scoring passage relevance before passing context to agent prompts.
- **GraphRAG Scope**: Knowledge graphs / GraphRAG are strictly out of scope for the initial prototype to maintain architectural simplicity and rapid testability.

### 2.5 Security, Safety & Governance
- Maximum document upload size enforced at the HTTP gate (default 25 MB).
- Strict MIME-type and magic-number validation (PDF only).
- SSRF-safe URL fetching with allowlisted regulatory domains (e.g., `sec.gov`).
- Total isolation from automated brokerage APIs; decision support only.
