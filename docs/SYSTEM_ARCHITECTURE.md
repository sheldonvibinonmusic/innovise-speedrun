# System Architecture Specification

## 1. High-Level Architecture Flow

This document details the components, data boundaries, and operational lifecycles of the **Trustworthy Multi-Agent Financial Research and Decision Support System**.

```mermaid
flowchart TD
    User([User / Financial Analyst]) -->|Submit Ticker or PDF| API[FastAPI Gateway]
    API -->|Register Job| DB[(SQLite Authoritative DB)]
    API -->|Dispatch Job| WF[LangGraph Orchestrator]
    
    subgraph Ingestion_Stage [Document Ingestion & Preparation]
        WF --> Ingest[Docling / PyMuPDF Parser]
        Ingest --> Hashing[SHA-256 Checksum & Dedup]
        Ingest --> Tables[Table Extractor & Normalizer]
        Tables --> DB
        Ingest --> Chunker[Layout-Aware Chunker]
        Chunker --> VectorStore[(Qdrant Vector Store)]
        Chunker --> BM25[(BM25 In-Memory Index)]
    end
    
    subgraph Analysis_Stage [7 Analytical Perspectives]
        WF --> A1[Profitability Analyst]
        WF --> A2[Cash Flow Analyst]
        WF --> A3[Liquidity & Debt Analyst]
        WF --> A4[Historical Trends Analyst]
        WF --> A5[Business & Risk Analyst]
        WF --> A6[Evidence Researcher]
        WF --> A7[Data Quality & Anomaly Analyst]
    end
    
    subgraph Verification_Stage [Tripartite Audit & Gates]
        A1 & A2 & A3 & A4 & A5 & A6 & A7 --> ClaimReg[Claim Registry]
        ClaimReg --> J1[Evidence Auditor]
        ClaimReg --> J2[Financial Integrity Auditor]
        ClaimReg --> J3[Adversarial Skeptic]
        J1 & J2 & J3 --> Gates{Deterministic Gate}
        Gates -->|PASS / QUALIFY| ReportGen[Report Generator]
        Gates -->|RETRIEVE_MORE| WF
        Gates -->|BLOCK / CONTRADICTION| Ledger[Discrepancy Ledger]
        Ledger --> ReportGen
    end
    
    ReportGen --> HumanReview[Human Review Cockpit]
    HumanReview -->|Approve / Override / Reject| FinalReport([Final Verified Report])
```

---

## 2. Component Boundaries & Responsibilities

| Component | Technology | Primary Responsibility | Truth Guarantee |
| :--- | :--- | :--- | :--- |
| **Frontend UI** | HTML5, CSS3, Vanilla ES JS | Human review, evidence inspection, workflow monitoring | Displays claims with direct citation pills |
| **API Layer** | FastAPI, Pydantic | REST endpoints, input sanitization, background execution | Strictly typed request/response schemas |
| **State Machine** | LangGraph | Coordinates analysis steps, bounded retries, gates | Explicit transitions, no infinite loops |
| **Document Ingestion** | Docling, PyMuPDF | Layout preservation, table extraction, chunking | SHA-256 fingerprinting of all inputs |
| **Authoritative Store** | SQLite / SQLAlchemy | Entities, financial facts, job state, claims, feedback | ACID transactions, primary source of facts |
| **Vector Index** | Qdrant Local | Semantic text search across filings & footnotes | Auxiliary retrieval; not primary fact truth |
| **Lexical Index** | Rank-BM25 | Keyword & ticker matching | Prevents dense semantic drift on rare terms |
| **Reranker** | Cross-Encoder MiniLM | Second-stage passage relevance scoring | Top-K precision refinement |
| **Calculations** | Python `Decimal` / Pandas | Financial ratios, growth rates, margins | 100% deterministic arithmetic |
| **Review & Audit** | 3 Verification Judges | Source alignment, formula checking, contradiction check | Emits explicit gate verdicts |

---

## 3. Storage Architecture: SQLite vs. Qdrant

A key architectural requirement is the strict division of responsibility:
1. **SQLite (`data/financial_research.db`)**:
   - Contains normalized tables: `companies`, `documents`, `pages`, `financial_facts`, `runs`, `claims`, `citations`, `judge_reviews`, `audit_events`.
   - All balance sheet, income statement, and cash flow numbers are stored as structured decimal values with fiscal year, quarter, currency, and unit attributes.
2. **Qdrant (`data/qdrant/`)**:
   - Stores dense vectors of narrative text chunks and MD&A sections.
   - Used to locate qualitative context, management commentary, risk factors, and accounting footnotes.
   - Vector hits are always verified against SQLite facts before final report inclusion.

---

## 4. Failure Modes & Bounded Execution

- **Timeout & Retries**: External API requests (SEC EDGAR) are bounded by timeouts and exponential backoff (max 3 retries).
- **Missing Data Handling**: If a financial metric is absent (e.g., R&D expense for a holding company), the system records an explicit `INDETERMINATE` status with an explanation rather than hallucinating 0 or average estimates.
- **Circuit Breaker on Retrieval**: Retrieval loops (`RETRIEVE_MORE`) are hard-bounded to a maximum of 2 iterations to avoid execution runaway.
