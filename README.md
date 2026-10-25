# Trustworthy Multi-Agent Financial Research & Decision Support System

[![Tests](https://img.shields.io/badge/Tests-67%20Passed-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.14-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)](https://fastapi.tiangolo.com/)
[![Architecture](https://img.shields.io/badge/Architecture-LangGraph%20Multi--Agent-orange)](app/workflow/)
[![Offline First](https://img.shields.io/badge/Dependencies-100%25%20Offline%20Capable-success)](#)

An enterprise-grade, citation-backed AI research assistant designed to assist financial analysts, investment committees, and corporate researchers in analyzing public and private financial disclosures with verifiable provenance, deterministic arithmetic, and non-majority verification.

---

## Executive Summary & Core Philosophy

Conventional LLM financial analysis suffers from critical failure modes: arithmetic hallucinations, untraceable assertions, lack of counter-evidence review, and failure to reconcile conflicting disclosures. 

This platform solves these problems through a **six-tier verification architecture**:
1. **Verifiable Claim-Level Provenance**: Every metric, fact, and assertion is bound to an exact document ID, page number, and table reference with SHA-256 data integrity checks.
2. **Deterministic Arithmetic Engine**: Operating margins, revenue trajectories, current ratios, and leverage metrics are computed exclusively in Python code (`Decimal`/`pandas`), completely bypassing LLM arithmetic.
3. **Tripartite Independent Verification**: Analytical outputs are audited by three independent, non-majority judges: an **Evidence & Citation Auditor**, a **Numerical Integrity Auditor**, and an **Adversarial Skeptic**.
4. **Contradiction & Restatement Detection**: Actively interrogates disclosures for conflicting restatements, operating headwinds, litigation risks, or margin contractions between MD&A narratives and audited financial tables.
5. **Supervisor-Directed Bounded Repair**: An autonomous **Research Quality Supervisor ("The Third Eye")** evaluates workflow state, detects evidence gaps, and triggers targeted recovery retrieval.
6. **Publication-Ready Vector PDF Export**: Generates high-resolution institutional research reports featuring embedded Matplotlib financial performance charts, audit scorecards, and human-review cockpit sign-off blocks with zero external web dependencies.

---

## System Architecture

```
                    ┌────────────────────────────────────────────────────────┐
                    │               DOCUMENT INGESTION & HYBRID RAG          │
                    │  - SEC EDGAR Connector (10-K, 10-Q CIK Resolution)     │
                    │  - Native PyMuPDF Layout Table Parser (find_tables())  │
                    │  - Canonical Accounting Metric Extractor (SQLite)      │
                    │  - Dense Qdrant Vector Store + Lexical BM25 Engine     │
                    │  - Reciprocal Rank Fusion (RRF) & Counter-Evidence RAG │
                    └───────────────────────────┬────────────────────────────┘
                                                │
                                                ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           LANGGRAPH MULTI-AGENT ANALYTICAL GRAPH                                  │
│                                                                                                   │
│  [Validate Scope] ──► [Acquire Sources] ──► [Check Readiness] ──► [Decompose Questions]          │
│                                                                               │                   │
│  ┌────────────────────────────────────────────────────────────────────────────┘                   │
│  ▼                                                                                                │
│  [Retrieve Evidence] ──► [Calculate Metrics] (Deterministic Decimal Engine)                       │
│                                      │                                                            │
│  ┌───────────────────────────────────┘                                                            │
│  ▼                                                                                                │
│  [Run 7 Specialist Analysts]                                                                      │
│    1. SourceCoverageAnalyst          5. RiskCounterEvidenceAnalyst                                │
│    2. FinancialStatementsAnalyst     6. PeerComparisonAnalyst                                     │
│    3. HistoricalTrendsAnalyst        7. ResearchSynthesisAnalyst                                  │
│    4. ManagementGuidanceAnalyst                                                                   │
│                                      │                                                            │
│  ┌───────────────────────────────────┘                                                            │
│  ▼                                                                                                │
│  [Run Tripartite Verification Judges]                                                             │
│    - EvidenceCitationJudge  (Passage fidelity, token overlap, coordinate audit)                   │
│    - NumericalIntegrityJudge (Non-majority gate, mathematical equality audit)                     │
│    - AdversarialSkepticJudge (Counter-evidence, risk omissions, restatement check)                │
│                                      │                                                            │
│  ┌───────────────────────────────────┘                                                            │
│  ▼                                                                                                │
│  [Research Quality Supervisor] ◄─── (Bounded Targeted Retrieval Loop: Max 2 Repairs)              │
│         │ (Approved / Repaired)                                                                   │
│         ▼                                                                                         │
│  [Synthesize Substantive Report] (Scorecards, Risks, Verification Ledger, Caveats)               │
└───────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                │
                                                ▼
                    ┌────────────────────────────────────────────────────────┐
                    │                  PRESENTATION & DECISION               │
                    │  - Architectural Dark Glass UI (/ui)                   │
                    │  - Real-time 6-Stage Trace Stepper                     │
                    │  - Interactive Metric Scorecard & SVG Chart            │
                    │  - Claim-Level Provenance & Audit Inspector Drawer     │
                    │  - Human-in-the-Loop Cockpit Sign-Off                  │
                    │  - Audit-Grade Institutional PDF Export (/export/pdf)  │
                    └────────────────────────────────────────────────────────┘
```

---

## Active API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Comprehensive system health probe (SQLite, Qdrant, directories) |
| `POST` | `/api/runs` | Registers a new persistent research inquiry (state: `pending`) |
| `GET` | `/api/runs/{run_id}` | Retrieves persistent run status, stage, parameters, and progress |
| `GET` | `/api/runs/{run_id}/trace` | Retrieves chronological audit event log for the 6-stage UI stepper |
| `POST` | `/api/runs/{run_id}/execute` | Executes the compiled LangGraph multi-agent research workflow |
| `POST` | `/api/documents/upload` | Multipart PDF/PPTX upload, layout table parsing, and indexing |
| `POST` | `/api/documents/{doc_id}/process`| Explicit trigger for document layout parsing and RAG indexing |
| `GET` | `/api/documents/{doc_id}` | Retrieves document ingestion status, page counts, and extracted facts |
| `POST` | `/api/company/discover` | Discovers SEC EDGAR regulatory filings and generates coverage manifests |
| `POST` | `/api/retrieval/search` | Multi-hop hybrid search (Dense + BM25 + RRF + Facts + Counter-Evidence) |
| `POST` | `/api/retrieval/rebuild` | Synchronizes search indices directly from persistent SQLite chunks |
| `GET` | `/api/reports/{run_id}` | Returns synthesized research dossier, scorecard, and verification ledger |
| `GET` | `/api/reports/{run_id}/export/pdf`| **Downloads publication-ready PDF report with chart and audit ledger** |
| `POST` | `/api/runs/{run_id}/review` | Human review cockpit sign-off (`APPROVED`, `QUALIFIED`, `REJECTED`) |

---

## Implementation & Upgrading History

The system was developed and hardened across structured implementation phases:

- **Phase 1: Persistence, Schema & Boundaries**: SQLite relational architecture with foreign keys, Pydantic data schemas, repository design pattern, and deterministic seed migrations.
- **Phase 2: Ingestion & Hybrid RAG**: SEC EDGAR connector with rate limiting; native PyMuPDF layout parser (`find_tables()`); canonical metric mapper (`TotalRevenue`, `OperatingIncome`, `NetIncome`, `CurrentAssets`, `CurrentLiabilities`, `CostOfRevenue`, `TotalDebt`, `StockholdersEquity`); Qdrant vector store and financial BM25 inverted index with Lucene non-negative IDF weighting.
- **Phase 3: Multi-Agent Graph & Judges**: LangGraph workflow orchestrating 7 specialist analysts, tripartite non-majority judges, deterministic `Decimal` arithmetic calculations, and the Research Quality Supervisor.
- **Phase 4: Architectural Web Cockpit**: Dark glass frontend mounted at `/ui` featuring a central architectural arch, 6-stage execution trace stepper, responsive SVG metric charts, provenance inspector, and human review cockpit.
- **Hardening & Forensic Verification Sprint**:
  - **Disambiguated Metric Extraction**: Prevented `Cost of revenue` or `Cost of goods sold` from misclassifying as `TotalRevenue`, eliminating margin distortions.
  - **Column-Specific Period Attribution**: Corrected multi-year comparative columns (e.g. `FY24` vs `FY23`) so calculations never compare mismatched fiscal years.
  - **Deterministic Liquidity & Solvency Ratios**: Implemented `calculate_current_ratio` and `calculate_debt_to_equity` with currency and reporting scope parity checks.
  - **Strict Numerical Equality Audit**: Added `_numbers_match` in `NumericalIntegrityJudge` to catch fabricated numbers within exact relative tolerances.
  - **Adversarial Contradiction Routing**: Routed disconfirming evidence to `AdversarialSkepticJudge` to block or qualify contradictory restatements.
  - **Granular Node Trace Logging**: Added `RunEvent` logging across every LangGraph node, ensuring the 6-stage UI progress bar dynamically lights up in real time.
  - **Non-Blocking UI Report Transition**: Guaranteed that terminated runs (even with `BLOCKED` or `QUALIFIED` status) immediately load the report workspace so reviewers can inspect gate rationales.
  - **Institutional PDF Export Service**: Built an offline PyMuPDF + Matplotlib reporting engine exporting executive summaries, metric scorecards, high-resolution charts, verified claims, and human-review sign-off blocks.

---

## Step-by-Step Local Setup & Evaluation Guide (For Judges)

This step-by-step guide allows any hackathon judge or evaluator to set up, test, and run the entire application locally in under 3 minutes.

### System Requirements
- **Python**: Version `3.10`, `3.11`, `3.12`, or `3.14`
- **Operating System**: Windows, macOS, or Linux
- **Git**: Installed and available in PATH
- **Zero Paid Subscriptions**: The application runs completely offline by default using local models and deterministic arithmetic. No OpenAI, Anthropic, or external API keys are required for the full evaluation journey.

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/sheldonvibinonmusic/innovise-speedrun.git
cd innovise-speedrun
```

---

### Step 2: Create & Activate a Python Virtual Environment

#### On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
*(If execution policy restricts scripts, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

#### On Windows (Command Prompt):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

#### On macOS / Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### Step 3: Upgrade Pip & Install Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

### Step 4: Configure Environment Variables

Copy the provided environment template to `.env`:

#### On Windows:
```powershell
Copy-Item .env.example .env
```

#### On macOS / Linux:
```bash
cp .env.example .env
```

*(The default `.env` is pre-configured for local execution with SQLite and offline fallback embeddings. No changes are required.)*

---

### Step 5: Run Automated Verification Tests

Verify system integrity by running the complete pytest test suite:

```bash
python -m pytest
```

**Expected Outcome:**
```
============================== 67 passed, 3 warnings in ~15s ==============================
```
All 67 unit, integration, and end-to-end regression tests will pass.

---

### Step 6: Start the FastAPI Application Server

Launch the backend with Uvicorn:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, verify that the startup log confirms:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

---

### Step 7: Open the Application in Your Browser

- **Interactive Financial Research Cockpit**: [http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui)
- **Interactive OpenAPI / Swagger Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **API Health Check Probe**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## Recommended Demonstration Journeys for Judges

### Journey 1: Financial PDF Upload, Deterministic Analysis & PDF Export (Primary Vertical Slice)

1. Navigate to [http://127.0.0.1:8000/ui](http://127.0.0.1:8000/ui).
2. Click the **Upload Documents** tab (Mode B).
3. Drag and drop any 10-K financial filing or select a pre-packaged sample from `data/uploads/` (e.g. `713f8f9f315f1e1a_MSFT_FY24_10K.pdf`).
4. Enter the research inquiry:
   ```
   Analyze Microsoft FY24 operating profitability, revenue trajectory, and key operational risks.
   ```
5. Set Ticker to `MSFT` and Period to `FY24`.
6. Click **Execute Research Run**.
7. **Observe the Live 6-Stage Progress Stepper**:
   - Stage 1: Document Acquisition & Scope
   - Stage 2: Parsing & Readiness
   - Stage 3: Retrieval & Expansion
   - Stage 4: Deterministic Calculations
   - Stage 5: Analyst & Judge Claims
   - Stage 6: Quality Supervisor & Synthesis
8. **Inspect the Research Dossier**:
   - Verification Badge: Displays `VERIFIED` or `QUALIFIED`.
   - **Deterministic Scorecard**: Operating Margin (e.g. `44.64%`), Net Margin (`35.96%`), Revenue Growth (`15.67%`), Current Ratio (`1.22x`), Debt-to-Equity (`0.19x`).
   - **Responsive SVG Performance Chart**: Visualizes margins and financial health indicators.
   - **Core Findings**: Verified assertions with clickable document chunk provenance citations.
   - **Independent Verification Ledger**: Review findings from the Evidence Auditor, Financial Integrity Auditor, and Adversarial Skeptic.
9. **Export PDF**:
   - Click the **Export PDF** button in the top right of the report header.
   - Inspect the downloaded audit-grade PDF report complete with the scorecard, Matplotlib chart, cited claims, and reviewer block.

---

### Journey 2: Contradictory Disclosure Detection (Adversarial Skeptic Audit)

1. Under the **Upload Documents** tab, upload a document containing planted or authentic risk restatements (e.g. `data/uploads/799c18cdac6f608f_MSFT_FY24_Conflicting.pdf`).
2. Run an inquiry on revenue growth and operational stability.
3. Observe that the system **prevents a false `VERIFIED` status**.
4. The **Adversarial Skeptic Judge** surfaces the contradiction, and the overall status is properly downgraded to `QUALIFIED` with prominent risk warnings in the Executive Summary.

---

### Journey 3: Qualitative / Proxy Statement Processing (Zero False Blocks)

1. Upload a proxy statement or narrative disclosure without balance sheet tables (e.g. `data/uploads/2379e9270e8c50f0_Amazon-2026-Proxy-Statement.pdf`).
2. Run an inquiry on governance and operational risk.
3. Observe that the workflow cleanly retrieves qualitative evidence passages, formulates grounded narrative claims, and completes with `QUALIFIED` status rather than crashing or triggering false `BLOCKED` failures.

---

### Journey 4: Human Review Cockpit Sign-Off

1. At the bottom of any synthesized report in `/ui`, locate the **Human Review Cockpit**.
2. Select your decision: **APPROVED**, **QUALIFIED**, or **REJECTED**.
3. Enter reviewer name and audit comments.
4. Click **Submit Review**.
5. The review status is saved to SQLite, and the report badge immediately updates to reflect official sign-off.

---

### Journey 5: Direct PDF Export via REST API

You can also export reports directly via HTTP:

```bash
# Replace {run_id} with your active run ID (e.g. run_828c67e084c4)
curl -X GET "http://127.0.0.1:8000/api/reports/{run_id}/export/pdf" --output report.pdf
```

The server returns binary `application/pdf` data suitable for institutional archival.

---

## Project Directory Layout

```
.
├── app/
│   ├── agents/                  # Multi-agent analytical roles & judges
│   │   ├── analysts/            # 7 Specialist analytical roles
│   │   ├── judges/              # Tripartite verification judges
│   │   └── supervisor.py        # Research Quality Supervisor ("The Third Eye")
│   ├── api/                     # FastAPI route controllers & dependencies
│   │   └── routes/              # health, runs, documents, company, retrieval, reports
│   ├── config.py                # Pydantic environment configuration
│   ├── db/                      # SQLAlchemy ORM models, session, and repository
│   ├── finance/                 # Pure Python deterministic math calculations
│   ├── ingestion/               # Document layout parsing & canonical fact extraction
│   ├── main.py                  # FastAPI application factory & startup warmup
│   ├── retrieval/               # Hybrid RAG (Qdrant Dense + BM25 + RRF + Counter-Evidence)
│   ├── schemas/                 # Strongly typed Pydantic contracts
│   ├── services/
│   │   └── pdf_export.py        # PyMuPDF + Matplotlib institutional PDF export
│   └── workflow/                # LangGraph state graph compilation & node callables
├── data/                        # Persistent storage (SQLite DB, Qdrant indices, uploads)
├── frontend/                    # Single-page architectural dark glass interface
│   ├── assets/js/               # app.js, api.js, state.js
│   ├── assets/css/              # Custom design system tokens & glass styling
│   └── index.html               # Frontend dashboard entry point
├── tests/                       # 67 automated unit, integration, and E2E tests
│   ├── unit/                    # Fast isolated component tests
│   ├── integration/             # Multi-component & database integration tests
│   └── end_to_end/              # Complete vertical slice journey & PDF export tests
├── pyproject.toml               # Project build configuration & pytest options
├── requirements.txt             # Locked Python dependency manifest
└── README.md                    # System documentation & reproduction guide
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
