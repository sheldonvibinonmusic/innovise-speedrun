# API Contract: Trustworthy Multi-Agent Financial Research System

## Overview

The backend exposes a RESTful JSON API using **FastAPI**. All request and response payloads adhere to strict Pydantic schemas. 

Long-running research jobs are executed asynchronously with explicit status tracking:
`pending` -> `running` -> `completed` / `completed_with_warnings` / `failed` / `needs_review`.

---

## Endpoint Implementation Status

| Method | Endpoint | Implementation Phase | Current Status |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Phase 1 | **Operational** |
| `POST` | `/api/runs` | Phase 1 (foundation) / Phase 3 (workflow) | **Operational (Pending State)** |
| `GET` | `/api/runs/{run_id}` | Phase 1 | **Operational** |
| `GET` | `/api/runs/{run_id}/trace` | Phase 1 | **Operational** |
| `POST` | `/api/documents/upload` | Phase 1 / Phase 2 (auto-processing) | **Operational** |
| `POST` | `/api/documents/{document_id}/process` | Phase 2 | **Operational** |
| `GET` | `/api/documents/{document_id}` | Phase 2 | **Operational** |
| `POST` | `/api/company/discover` | Phase 2 | **Operational** |
| `POST` | `/api/retrieval/search` | Phase 2 | **Operational** |
| `POST` | `/api/retrieval/rebuild` | Phase 2 | **Operational** |
| `GET` | `/api/reports/{run_id}` | Phase 3 | *Deferred (501 Not Implemented)* |
| `POST` | `/api/runs/{run_id}/review` | Phase 4 | *Deferred (501 Not Implemented)* |

---

## Endpoint Specifications

### 1. System Health Check
- **Endpoint**: `GET /api/health`
- **Summary**: Verify backend service status, database connectivity, and configuration flags.
- **Request**: None
- **Response** (`200 OK`):
  ```json
  {
    "status": "healthy",
    "version": "0.1.0",
    "environment": "development",
    "database_connected": true,
    "optional_components": {
      "llm_api_key_configured": false,
      "upload_dir_ready": true,
      "qdrant_dir_ready": true
    }
  }
  ```

---

### 2. Upload Financial Documents
- **Endpoint**: `POST /api/documents/upload`
- **Summary**: Upload one or more PDF financial reports with streaming validation, SHA-256 hashing, size limiting, and deduplication.
- **Request**: `multipart/form-data`
  - `files`: Array of binary PDF files
  - `company_ticker`: Optional string (e.g., `"AAPL"`)
  - `reporting_period`: Optional string (e.g., `"FY24"`)
  - `document_type`: Optional string (`"10-K"`, `"10-Q"`, `"Annual Report"`)
  - `jurisdiction`: Optional string (`"US"`)
- **Response** (`201 Created`):
  ```json
  {
    "uploaded_documents": [
      {
        "document_id": "doc_a1b2c3d4",
        "filename": "AAPL_2024_10K.pdf",
        "file_size_bytes": 1048576,
        "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "status": "REGISTERED",
        "source_type": "user_upload",
        "jurisdiction": "US",
        "reporting_period": "FY24",
        "warnings": "Registered successfully. Layout parsing, table extraction, and vector indexing are deferred to Phase 2.",
        "is_duplicate": false,
        "registered_at": "2026-10-25T02:00:00Z"
      }
    ],
    "message": "Successfully processed 1 document(s)."
  }
  ```

---

### 3. Initiate Multi-Agent Research Run
- **Endpoint**: `POST /api/runs`
- **Summary**: Register and persist a new financial research run.
- **Request** (`application/json`):
  ```json
  {
    "research_question": "Analyze operating cash flow stability and debt maturity headroom for FY24.",
    "company_ticker": "MSFT",
    "company_name": "Microsoft Corporation",
    "jurisdiction": "US",
    "reporting_periods": ["FY2023", "FY2024"],
    "analytical_areas": ["profitability", "cash_flow"],
    "document_ids": ["doc_a1b2c3d4"]
  }
  ```
- **Response** (`201 Created`):
  ```json
  {
    "run_id": "run_987654321",
    "status": "pending",
    "research_question": "Analyze operating cash flow stability and debt maturity headroom for FY24.",
    "company_id": 1,
    "company_ticker": "MSFT",
    "jurisdiction": "US",
    "current_stage": "initialization",
    "progress_percent": 0,
    "created_at": "2026-10-25T02:00:00Z",
    "updated_at": "2026-10-25T02:00:00Z",
    "error_summary": null,
    "requested_periods": ["FY2023", "FY2024"],
    "input_document_ids": ["doc_a1b2c3d4"],
    "message": "Research run registered successfully in 'pending' state. Multi-agent execution will commence in Phase 3."
  }
  ```

---

### 4. Get Research Run Status & Metadata
- **Endpoint**: `GET /api/runs/{run_id}`
- **Summary**: Retrieve live progress, active stage, and parameters from SQLite.
- **Response** (`200 OK`):
  ```json
  {
    "run_id": "run_987654321",
    "status": "pending",
    "research_question": "Analyze operating cash flow stability and debt maturity headroom for FY24.",
    "company_id": 1,
    "company_ticker": "MSFT",
    "jurisdiction": "US",
    "current_stage": "initialization",
    "progress_percent": 0,
    "created_at": "2026-10-25T02:00:00Z",
    "updated_at": "2026-10-25T02:00:00Z",
    "error_summary": null,
    "requested_periods": ["FY2023", "FY2024"],
    "input_document_ids": ["doc_a1b2c3d4"],
    "message": "Current run status: pending"
  }
  ```

---

### 5. Get Execution Trace & Audit Log
- **Endpoint**: `GET /api/runs/{run_id}/trace`
- **Summary**: Detailed step-by-step audit trace of all execution events, timestamps, and parameters.
- **Response** (`200 OK`):
  ```json
  {
    "run_id": "run_987654321",
    "total_events": 1,
    "events": [
      {
        "event_id": 1,
        "run_id": "run_987654321",
        "node_or_stage": "initialization",
        "event_timestamp": "2026-10-25T02:00:00Z",
        "status_or_code": "INFO",
        "duration_ms": null,
        "details": {
          "action": "run_created",
          "research_question": "Analyze operating cash flow stability...",
          "analytical_areas": ["profitability", "cash_flow"],
          "document_count": 1
        },
        "model_or_parser_version": null
      }
    ]
  }
  ```

---

### 6. Company Discovery & Connector Fetch
- **Endpoint**: `POST /api/company/discover`
- **Summary**: Discover company CIK and recent filings from SEC EDGAR or flag unsupported jurisdictions.
- **Request** (`application/json`):
  ```json
  {
    "ticker_or_cik": "AAPL",
    "jurisdiction": "US",
    "filing_types": ["10-K", "10-Q"],
    "max_periods": 3
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "company_name": "Apple Inc.",
    "cik": "0000320193",
    "ticker": "AAPL",
    "jurisdiction": "US",
    "coverage_status": "COVERAGE_AVAILABLE",
    "requested_period": null,
    "available_periods": ["2024-09-28", "2024-06-29"],
    "discovered_filings": [
      {
        "accession_number": "0000320193-24-000106",
        "form": "10-K",
        "filing_date": "2024-11-01",
        "report_date": "2024-09-28",
        "primary_document": "aapl-20240928.htm",
        "document_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000106/aapl-20240928.htm",
        "description": "Annual report [Section 13 and 15(d), not S-K Item 405]"
      }
    ],
    "warnings": []
  }
  ```

---

### 7. Process Document Pipeline & Inspect Metadata
- **Endpoints**:
  - `POST /api/documents/{document_id}/process` (Trigger layout parsing, fact extraction, and indexing)
  - `GET /api/documents/{document_id}` (Inspect status, page count, chunks, and facts)
- **Response** (`200 OK`):
  ```json
  {
    "document_id": "doc_a1b2c3d4",
    "filename": "AAPL_2024_10K.pdf",
    "status": "INDEXED",
    "page_count": 68,
    "chunks_indexed": 142,
    "facts_extracted": 38,
    "extraction_warnings": [],
    "indexed_at": "2026-10-25T02:05:00Z"
  }
  ```

---

### 8. Hybrid Retrieval Search
- **Endpoint**: `POST /api/retrieval/search`
- **Summary**: Multi-modal search fusing dense vector similarity, BM25 lexical matches (RRF), verified SQLite financial facts, and counter-evidence.
- **Request** (`application/json`):
  ```json
  {
    "query": "Intelligent Cloud operational momentum and operating margins",
    "company_ticker": "MSFT",
    "top_k": 5,
    "include_structured_facts": true,
    "include_counter_evidence": true
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "query": "Intelligent Cloud operational momentum and operating margins",
    "total_hits": 5,
    "evidence": [
      {
        "chunk_id": "chk_10k_msft_01",
        "document_id": "doc_msft_10k",
        "page_number": 1,
        "chunk_type": "narrative",
        "section_title": "Item 7. Management's Discussion and Analysis",
        "content": "Our cloud services continued strong operational momentum throughout FY24...",
        "rrf_score": 0.0325,
        "retrieval_routes": ["dense", "bm25"],
        "company_ticker": "MSFT",
        "reporting_period": "FY24"
      }
    ],
    "structured_facts": [
      {
        "metric_name": "TotalRevenue",
        "numeric_value": "245120",
        "currency": "USD",
        "unit_scale": "MILLIONS",
        "page_number": 2,
        "table_reference": "CONSOLIDATED STATEMENTS OF INCOME"
      }
    ],
    "counter_evidence": []
  }
  ```

---

### 9. Execute Research Run Workflow (Phase 3 Implemented)
- **Endpoint**: `POST /api/runs/{run_id}/execute`
- **Summary**: Triggers execution of the LangGraph multi-agent research and verification graph.
- **Response** (`200 OK`):
  ```json
  {
    "run_id": "run_987654321",
    "status": "completed",
    "current_stage": "synthesize_report",
    "verification_status": "VERIFIED",
    "claims_count": 6,
    "calculations_count": 2,
    "unresolved_uncertainties": [],
    "message": "Multi-agent research and verification workflow executed successfully."
  }
  ```

---

### 10. Retrieve Generated Research Report (Phase 3 Implemented)
- **Endpoint**: `GET /api/reports/{run_id}`
- **Summary**: Returns complete synthesized report with provenance citations, candidate claims, verification verdicts, and deterministic calculations.
- **Response** (`200 OK`):
  ```json
  {
    "report_id": "rep_run_987654321",
    "run_id": "run_987654321",
    "title": "Financial Research & Verification Report: MSFT",
    "company_ticker": "MSFT",
    "executive_summary": "Multi-agent research analysis for MSFT addressing inquiry...",
    "verification_status": "VERIFIED",
    "markdown_content": "# Financial Research & Verification Report: MSFT...",
    "claims": [
      {
        "claim_id": "clm_62d8_0000",
        "claim_text": "Operating margins remained highly profitable at 44.6%...",
        "claim_type": "reported_fact",
        "materiality": "MEDIUM",
        "status": "ACCEPTED",
        "evidence_references": ["chk_doc_62d8_0000"]
      }
    ],
    "calculations": [
      {
        "metric_name": "OperatingMargin",
        "numeric_result": 44.64,
        "formatted_result": "44.64%",
        "formula": "(OperatingIncome / TotalRevenue) * 100",
        "validation_outcome": "VALID"
      }
    ],
    "unresolved_uncertainties": []
  }
  ```

---

### 11. Submit Human Review Decision (Phase 4 Implemented)
- **Endpoint**: `POST /api/runs/{run_id}/review`
- **Summary**: Records human analyst sign-off (`APPROVED`, `QUALIFIED`, or `REJECTED`), audit remarks, and claim-level overrides in SQLite.
- **Request** (`application/json`):
  ```json
  {
    "overall_decision": "APPROVED",
    "reviewer_name": "Chief Risk Officer",
    "comments": "Audited against primary Form 10-K filing; calculations reconciled.",
    "claim_overrides": [
      {
        "claim_id": "clm_62d8_0000",
        "new_status": "VERIFIED",
        "notes": "Verified against 10-K Income Statement table."
      }
    ]
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "run_id": "run_987654321",
    "overall_decision": "APPROVED",
    "reviewer_name": "Chief Risk Officer",
    "status": "approved",
    "verification_status": "APPROVED",
    "claim_overrides_applied": 1,
    "comments": "Audited against primary Form 10-K filing; calculations reconciled.",
    "reviewed_at": "2026-10-25T05:30:00Z",
    "message": "Human review decision 'APPROVED' recorded successfully."
  }
  ```
