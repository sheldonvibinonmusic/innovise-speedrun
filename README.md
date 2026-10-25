# Trustworthy Multi-Agent Financial Research and Decision Support System

An enterprise-grade, citation-backed AI research assistant designed to assist financial analysts, investment committees, and corporate researchers in analyzing public and private financial disclosures.

---

## Key Highlights

- **Verifiable Provenance**: Every financial figure and narrative insight is bound to an exact page number and text/table coordinate with SHA-256 integrity verification.
- **Deterministic Math**: Financial ratios, growth calculations, and reconciliations are computed exclusively in Python code (`Decimal`/`pandas`), completely bypassing LLM arithmetic.
- **Tripartite Verification**: Analytical findings are independently audited by an Evidence Auditor, a Financial Integrity Auditor, and an Adversarial Skeptic.
- **Seeded Inconsistency Detection**: Built to actively detect contradictions between narrative disclosures (e.g., MD&A) and audited financial tables.
- **Human-in-the-Loop Cockpit**: Explicit human review gates allow analysts to approve, qualify, or override AI-generated claims.
- **Zero Autonomous Trading**: Strictly a research and decision-support platform; no execution of financial transactions.
- **Free-First Architecture**: Operates with local execution, open-source models, and public APIs. Zero mandatory paid subscriptions or cloud lock-ins required for foundational execution.

---

## Operational Ingestion & Hybrid RAG Foundation (Phase 2)

Phase 2 introduces automated financial document discovery, layout-aware parsing, tabular fact extraction, and a production hybrid retrieval pipeline:
- **SEC EDGAR Discovery Connector**: Automated public filings discovery supporting Forms 10-K and 10-Q with CIK resolution, rate limiting, and structured coverage manifests. Graceful unsupported-jurisdiction handling for Indian filings (BSE/NSE/MCA) directing users to manual PDF uploads.
- **Layout-Aware PDF Ingestion & Normalization**: Native PyMuPDF parser with layout table detection (`find_tables()`), blank page warnings, and corrupted PDF fallback. Extracts structured tables and canonical accounting metrics (`TotalRevenue`, `NetIncome`, `OperatingCashFlow`, etc.) mapped into SQLite.
- **Table- & Page-Aware Chunking**: Specialized sliding-window chunkers preserving source document page boundaries, section titles, and repeating column header context for chunk rows.
- **Hybrid Retrieval Engine**:
  - **Dense Vector Search**: Qdrant persistent and in-memory engine storing 384-dimensional normalized embeddings (`BAAI/bge-small-en-v1.5` and deterministic offline fallback).
  - **Lexical BM25 Search**: Financial-tokenized inverted index preserving currency symbols, percentages, negative numbers, and accounting items with non-negative Lucene IDF weighting.
  - **Reciprocal Rank Fusion (RRF)**: Merges dense and lexical candidate lists (`k=60`) while logging explicit retrieval routes.
  - **Structured Financial Fact Queries**: Direct SQLite queries for exact numerical metrics, preventing semantic approximation.
  - **Counter-Evidence Retrieval**: Adversarial query generation targeting risk factors, margin compression, and contradictions.
  - **Index Rebuild & Synchronization**: Fast re-indexing from authoritative SQLite chunks on demand.

### Active API Endpoints
| Method | Endpoint | Status | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | **Implemented** | System health, database connectivity, and component readiness |
| `POST` | `/api/runs` | **Implemented** | Validates and persists a new research run (status: `pending`) |
| `GET` | `/api/runs/{run_id}` | **Implemented** | Retrieves persisted run status, parameters, and progress |
| `GET` | `/api/runs/{run_id}/trace` | **Implemented** | Retrieves chronological audit event log |
| `POST` | `/api/runs/{run_id}/execute` | **Implemented** | Executes the full LangGraph multi-agent research and verification graph |
| `POST` | `/api/documents/upload` | **Implemented** | Multipart upload, PDF/PPTX validation, deduplication, and auto-processing |
| `POST` | `/api/documents/{document_id}/process` | **Implemented** | Triggers layout parsing, fact extraction, and hybrid indexing |
| `GET` | `/api/documents/{document_id}` | **Implemented** | Retrieves document ingestion status, page counts, chunk and fact metrics |
| `POST` | `/api/company/discover` | **Implemented** | SEC EDGAR automated discovery and filing coverage manifest |
| `POST` | `/api/retrieval/search` | **Implemented** | Hybrid search (Dense + BM25 + RRF + Structured Facts + Counter-Evidence) |
| `POST` | `/api/retrieval/rebuild` | **Implemented** | Synchronizes and rebuilds search indices directly from SQLite |
| `GET` | `/api/reports/{run_id}` | **Implemented** | Returns synthesized, citation-backed report with deterministic calculations |
| `POST` | `/api/runs/{run_id}/review` | **Implemented** | Human review sign-off and claim override cockpit |

---

## Interactive Frontend Experience (Phase 4 Implemented)

Phase 4 introduces an architectural single-page financial research interface mounted directly at `/ui` (or runnable via static web servers):
- **Visual Identity**: Dark navy atmosphere (`#04070d`), dark glass panels (`rgba(11, 16, 26, 0.78)`), fine borders (`rgba(255, 255, 255, 0.13)`), warm stone/ivory accents (`#e8d1cb`), and subtle pointer parallax.
- **Persistent Scene**: The central architectural arch image remains mounted continuously across all modes, uploads, progress phases, report reviews, and inspector drawers.
- **Acquisition Modes**:
  - **Mode A (Web Search)**: SEC EDGAR and official company disclosure discovery with live filing coverage manifests.
  - **Mode B (Upload Documents)**: Drag-and-drop queue supporting PDF and PowerPoint (`.pptx`) decks with real byte progress and bounded 3-file transfer concurrency.
- **Signature Architectural Scan**: Maps backend execution trace events to 6 user-facing stages without simulated timers.
- **Report & Scorecard Workspace**: Interactive metric scorecard, risk audit factors, claim-level evidence inspector, and human review sign-off cockpit.

---

## Getting Started

### 1. Environment Setup
Install dependencies using pip:
```bash
python -m pip install -r requirements.txt
```
Copy the configuration template:
```bash
cp .env.example .env
```

### 2. Run the FastAPI Backend
Launch the server with Uvicorn:
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Interactive Research Web UI: `http://127.0.0.1:8000/ui`
- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- Health check probe: `http://127.0.0.1:8000/api/health`

### 3. Run the Automated Tests
Run pytest across the test suite:
```bash
python -m pytest tests -v
```

---

## Multi-Agent Architecture & Verification (Phase 3 Implemented)

The analytical engine comprises a compiled LangGraph workflow orchestrated by the Research Quality Supervisor:
- **Seven Specialist Analysts**:
  1. `SourceCoverageAnalyst`: Audits disclosure coverage, unread filings, and scope.
  2. `FinancialStatementsAnalyst`: Extracts GAAP/IFRS line items and audits margins.
  3. `HistoricalTrendsAnalyst`: Analyzes trajectories, growth, and volatility.
  4. `ManagementGuidanceAnalyst`: Evaluates guidance vs audited results.
  5. `RiskCounterEvidenceAnalyst`: Actively targets risk factors and counter-evidence.
  6. `PeerComparisonAnalyst`: Evaluates benchmarks and competitive positioning.
  7. `ResearchSynthesisAnalyst`: Integrates perspectives and balances material findings.
- **Tripartite Verification Judges**:
  1. `EvidenceCitationJudge`: Verifies exact provenance, page numbers, and chunk references.
  2. `NumericalIntegrityJudge`: Strict deterministic non-majority gate verifying `Decimal` arithmetic.
  3. `AdversarialSkepticJudge`: Checks completeness, unaddressed risks, and counter-evidence.
- **Research Quality Supervisor ("The Third Eye")**:
  - Monitors convergence, detects no-progress retrieval loops, triggers bounded targeted repairs, and blocks unverified reports from passing gates.
- **Acquisition Modes**:
  - **Mode A**: SSRF-protected website financial crawler with structured coverage manifests.
  - **Mode B**: Uploaded PDFs and PowerPoint (`.pptx`) presentations with slide, table, and speaker notes extraction.
- **Vector Engine Selection**: Qdrant retained after empirical benchmarking (104x lower p50 latency than Milvus Lite, zero Windows file locking).

---

## Documentation Links

- [Project Brief](PROJECT_BRIEF.md): Core problem statement, requirements, and constraints.
- [System Architecture](ARCHITECTURE.md): Comprehensive system design and data flows.
- [API Contract](API_CONTRACT.md): REST endpoints and JSON payload specifications.
- [Development Plan](DEVELOPMENT_PLAN.md): 6-hour phased implementation roadmap.
- Technical Specs in `docs/`:
  - [System Architecture Details](docs/SYSTEM_ARCHITECTURE.md)
  - [Data Model & Schemas](docs/DATA_MODEL.md)
  - [Retrieval Architecture](docs/RETRIEVAL_DESIGN.md)
  - [Agent & Judge Design](docs/AGENT_DESIGN.md)
  - [API Design Guidelines](docs/API_DESIGN.md)
  - [Security & Guardrails](docs/SECURITY.md)
  - [Evaluation & Benchmarking](docs/EVALUATION.md)
