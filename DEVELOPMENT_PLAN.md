# Development Plan: 6-Hour Implementation Roadmap

This project is structured for a 6-hour execution window. Each phase builds sequentially on verified foundations without premature optimization or mock facades.

---

## Phase 0: Workspace and Project Initialization
**Status**: COMPLETED

### Primary Deliverables
1. Directory structure matching architectural specifications.
2. Development tooling: `.vscode/settings.json`, `.vscode/launch.json`, `.vscode/tasks.json`, `.vscode/extensions.json`.
3. Configuration manifest: `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`.
4. Architectural and contract documentation: `PROJECT_BRIEF.md`, `ARCHITECTURE.md`, `API_CONTRACT.md`, `DEVELOPMENT_PLAN.md`, and technical specifications in `docs/`.
5. Frontend and backend file scaffolding with module docstrings and boundary definitions.

### Acceptance Criteria Verified
- Workspace verified with zero redundant nested directories.
- Git repository initialized cleanly.
- Safe configuration templates established.

---

## Phase 1: Backend Foundation, Database, and Core Schemas
**Status**: COMPLETED

### Primary Deliverables
1. **Config & Settings**: Pydantic `BaseSettings` in `app/config.py` loading `.env` with strict type validation, directory auto-provisioning, and CORS handling.
2. **Database Engine & ORM Models**: SQLite relational store with SQLAlchemy models (`Company`, `Document`, `ResearchRun`, `RunEvent`, `FinancialFact`), foreign keys, decimal precision, and isolated session handling in `app/db/`.
3. **Pydantic Schemas**: Comprehensive schemas in `app/schemas/` enforcing request parameters, file metadata, run status lifecycles, and standardized error envelopes.
4. **FastAPI Application & Routing**: Centralized app factory in `app/main.py` with lifespan lifecycle management, error handlers, and modular routers in `app/api/routes/`.
5. **Core Operational Endpoints**:
   - `GET /api/health`: Database connectivity check and component readiness.
   - `POST /api/runs`: Request validation, company resolution, persistent run creation, and initial audit event logging.
   - `GET /api/runs/{run_id}`: Persisted run state retrieval and 404 handling.
   - `GET /api/runs/{run_id}/trace`: Chronological audit trail retrieval.
   - `POST /api/documents/upload`: Safe streaming upload, `%PDF-` signature verification, max size limiting (25 MB), SHA-256 deduplication, and metadata registration.
6. **Automated Test Suite**: 11 automated unit and integration tests passing cleanly in `tests/unit/test_backend_foundation.py`.

### Acceptance Criteria Verified
- `GET /api/health` returns `200 OK` with live SQLite database check verified.
- SQLite tables initialize deterministically on app startup.
- Full upload safety pipeline rejects non-PDFs, empty files, oversized payloads, and handles duplicates idempotently.
- All 11 automated unit tests pass in 0.78s.

---

## Phase 2: Ingestion, Financial Facts, and Hybrid RAG
**Status**: COMPLETED

### Primary Deliverables
1. **Document Ingestion & Parsing**:
   - Layout-aware PDF parser with PyMuPDF table detection (`page.find_tables()`), blank page warnings, and corrupted document fallback.
   - Financial table normalizer parsing row metrics, units, multipliers (`millions`, `crores`), and mapping into canonical accounting items.
   - Structured financial facts written to SQLite `financial_facts` table with exact page references.
2. **Page- & Table-Aware Chunking**:
   - Narrative sliding window (~500 tokens, 60 overlap) preserving page and section context.
   - Table-aware chunker repeating column headers across chunk rows to maintain row interpretability.
3. **Hybrid Retrieval Engine**:
   - Local Qdrant dense vector store (384-dimensional Cosine similarity) with `EmbeddingService` facade.
   - In-memory BM25 index with specialized financial tokenization (preserving `$`, `%`, negative parenthesis, tickers) and Lucene-style non-negative IDF weighting.
   - Reciprocal Rank Fusion (`k=60`) fusing dense and lexical retrieval channels with explicit provenance routing.
   - Structured financial facts retrieval querying SQLite directly to guarantee 100% numerical accuracy.
   - Counter-evidence query generator actively targeting risk factors, headwinds, and margin compression.
   - Index rebuild endpoint (`POST /api/retrieval/rebuild`) synchronizing indices directly from SQLite chunks.
4. **SEC EDGAR & Regional Connectors**:
   - `POST /api/company/discover` resolving ticker/CIK via SEC submissions API with rate limiting and coverage manifest.
   - Unsupported jurisdiction connector explicitly flagging Indian filings (BSE/NSE/MCA) with guidance to upload PDFs.
5. **Operational Verification**:
   - Comprehensive test suite in `tests/unit/test_ingestion_and_rag.py` covering all 17 requirements.
   - Total test suite expanded to 28 passing tests (11 Phase 1 + 17 Phase 2).

### Acceptance Criteria Verified
- PDF upload stores raw document and registers chunk embeddings in Qdrant and BM25.
- Financial tables parsed into discrete numerical facts in SQLite with canonical metric mapping.
- Hybrid search returns top-k passages with exact page citations, RRF scores, and multi-channel provenance.
- All 28 automated unit and integration tests pass cleanly in 9.49s.

---

## Phase 3: Multi-Agent Workflow, 7 Analysts, 3 Judges, & Gates
**Status**: COMPLETED

### Primary Deliverables
1. **Vector Store Benchmark & Selection**:
   - Rigorous empirical benchmark of Qdrant vs Milvus Lite across 120 chunks and 50 iterations.
   - Result: Qdrant selected (~104x faster p50 latency, ~226x faster p99 latency, 100% filter precision, zero Windows file locks).
2. **Document Acquisition (Mode A & Mode B)**:
   - Mode A: SSRF-protected website financial crawler with structured coverage manifests.
   - Mode B: PowerPoint (`.pptx`) presentation ingestion extracting slide titles, text, tables, and speaker notes alongside PDF.
3. **LangGraph State Graph & Research Quality Supervisor**:
   - Compiled typed state machine (`ResearchWorkflowState`) orchestrating multi-hop retrieval, 7 analysts, 3 judges, supervisor, and report synthesis.
   - Research Quality Supervisor ("The Third Eye") enforcing non-majority deterministic verification, bounded retrieval repairs, and no-progress loop detection.
4. **Seven Specialized Analysts & Tripartite Judges**:
   - 7 Analysts (`SourceCoverage`, `FinancialStatements`, `HistoricalTrends`, `ManagementGuidance`, `RiskCounterEvidence`, `PeerComparison`, `ResearchSynthesis`).
   - 3 Tripartite Judges (`EvidenceCitationJudge`, `NumericalIntegrityJudge`, `AdversarialSkepticJudge`).
5. **Deterministic Arithmetic & Lightweight Evidence Graph**:
   - Exact `Decimal` arithmetic for revenue growth, operating margin, net margin, current ratio, and leverage with currency/period comparability validation.
   - SQLite `evidence_relationships` table supporting bounded graph traversal (`traverse_evidence_subgraph`).
6. **API Endpoints**:
   - `POST /api/runs/{run_id}/execute`: Triggers full multi-agent execution pipeline.
   - `GET /api/reports/{run_id}`: Serves synthesized Markdown/JSON report with claims, calculations, and provenance citations.
7. **Operational Verification**:
   - 12 comprehensive unit and integration tests in `tests/unit/test_multi_agent_workflow.py`.
   - Complete project test suite expanded to 40 passing tests (11 Phase 1 + 17 Phase 2 + 12 Phase 3).

### Acceptance Criteria Verified
- Empirical vector store benchmark executed and Qdrant retained on evidence.
- LangGraph compiles and executes deterministically with typed state.
- 7 analysts emit structured claims with explicit materiality and citation coordinates.
- 3 judges audit evidence, arithmetic, and counter-evidence independently.
- Deterministic numerical gate overrides LLM majorities on arithmetic discrepancy.
- Supervisor detects no-progress loops and caps corrective repairs at 2 iterations.
- Complete test suite: 40 tests passing in 9.63s.

---

## Phase 4: Frontend Integration, Human Review, & Evaluation
**Status**: COMPLETED

### Primary Deliverables
1. **Architectural Frontend Design System**:
   - Monolithic stone arch & dark navy atmosphere with persistent scene layer ([`frontend/assets/images/hero-arch.png`](file:///c:/Users/Sheldon%20Pais/Desktop/Innovise%20speedrun/frontend/assets/images/hero-arch.png)).
   - Fine architectural frame with chamfered corner markers and hairline dividers.
   - Restrained glass surfaces, subtle pointer parallax, and `prefers-reduced-motion` compliance.
2. **Dual Acquisition Interfaces**:
   - Mode A (Web Search): SEC EDGAR & company disclosure discovery with structured coverage manifests.
   - Mode B (Document Upload): Accessible drag-and-drop zone and queue supporting up to 300 files (PDF & PPTX) with byte-progress tracking and 3-file concurrent upload throttle.
3. **Signature Research Scan & Progress Animation**:
   - Live execution tracking mapping backend trace events to 6 concise stages without fake timers.
   - Supervisor repair status reflection ("Checking additional evidence").
4. **Report & Evidence Workspace**:
   - Deterministic metric scorecard (`Operating Margin`, `Revenue Growth`, `Net Margin`, `Current Ratio`, `Debt-to-Equity`).
   - Claim cards with materiality badges and clickable citation coordinates.
   - Risk factors and counter-evidence audit section.
   - Side-drawer Evidence Inspector with safe text rendering (`textContent`) and provenance coordinates.
5. **Human Review Sign-Off Cockpit**:
   - Operational `POST /api/runs/{run_id}/review` endpoint persisting overall decision (`APPROVED`, `QUALIFIED`, `REJECTED`), reviewer remarks, and claim-level overrides in SQLite and audit trace logs.
6. **Operational Verification**:
   - FastAPI static mount at `/ui` serving the production single-page application.
   - Comprehensive integration test suite in `tests/integration/test_phase4_frontend_and_review.py`.
   - Complete project test suite expanded to 43 passing tests across all 4 phases.

### Acceptance Criteria Verified
- Persistent scene background remains mounted across all mode and view transitions.
- Both acquisition modes trigger real backend discovery and upload pipelines.
- Research progress accurately reflects actual backend workflow events.
- Reports display verified deterministic formulas, citations, and risk counter-evidence.
- Human review decisions persist to SQLite and update the UI immediately.
- 43/43 automated tests passing in 12.33s.
