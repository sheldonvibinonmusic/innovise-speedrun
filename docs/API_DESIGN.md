# API Design & Status Conventions

## 1. RESTful Design Conventions

The backend follows RESTful principles with FastAPI:
- **Predictable URIs**: Resources are nouns (`/api/documents`, `/api/runs`, `/api/reports`).
- **HTTP Status Codes**:
  - `200 OK`: Successful synchronous retrieval or state update.
  - `201 Created`: Successful resource creation (e.g. document upload).
  - `202 Accepted`: Asynchronous job queued for execution.
  - `400 Bad Request`: Validation failure (invalid ticker, corrupt PDF, missing parameter).
  - `404 Not Found`: Resource ID not found.
  - `422 Unprocessable Entity`: Schema validation mismatch.
  - `500 Internal Server Error`: Unhandled server exception.

---

## 2. Research Run Lifecycle & Status Conventions

Because multi-agent financial research requires PDF parsing, hybrid retrieval, multiple analyst steps, and judge verification, research runs operate as asynchronous state machines.

```
       [POST /api/runs]
              │
              ▼
          [QUEUED] ── (Workers picked up job)
              │
              ▼
         [INGESTING] ── (Parsing PDFs, chunking, table extraction)
              │
              ▼
         [ANALYZING] ── (7 Analytical lenses executing research)
              │
              ▼
         [VERIFYING] ── (Tripartite Judges & Deterministic Gates)
              │
              ▼
    [AWAITING_HUMAN_REVIEW] ── (Draft Report ready for Analyst cockpit)
         /          \
  (Approved)      (Rejected)
       /              \
      ▼                ▼
 [COMPLETED]        [FAILED]
```

### Status Definitions
1. **`QUEUED`**: Research run has been registered in SQLite and placed in execution queue.
2. **`INGESTING`**: Source documents are being validated, parsed (Docling/PyMuPDF), and indexed into Qdrant/BM25.
3. **`ANALYZING`**: Active execution of the seven analytical perspectives.
4. **`VERIFYING`**: Evidence auditor, financial integrity auditor, and adversarial skeptic are evaluating proposed claims against deterministic gates.
5. **`AWAITING_HUMAN_REVIEW`**: Draft report and claim audit ledger have been compiled. Awaiting human analyst feedback.
6. **`COMPLETED`**: Final report signed off and published with audit events locked.
7. **`FAILED`**: Run halted due to irrecoverable error or unresolvable security constraint.

---

## 3. Error Handling and Problem Details

Errors return a structured RFC 7807-style error envelope:
```json
{
  "error": {
    "code": "INVALID_DOCUMENT_FORMAT",
    "message": "Uploaded file is not a valid PDF or exceeds the 25 MB limit.",
    "details": {
      "filename": "annual_report.exe",
      "mime_type": "application/x-dosexec"
    },
    "timestamp": "2026-10-25T02:00:00Z"
  }
}
```
