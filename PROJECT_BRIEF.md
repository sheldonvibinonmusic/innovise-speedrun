# Project Brief: Trustworthy Multi-Agent Financial Research and Decision Support System

## 1. Executive Summary & Problem Statement

Financial analysts, investment committees, and corporate researchers face severe challenges when conducting in-depth financial analysis from complex disclosures (such as SEC 10-K/10-Q filings, earnings transcripts, and statutory filings):
1. **Hallucination & Numerical Fabrications**: Generative AI models regularly fabricate plausible-sounding financial metrics, misread complex financial tables, or mix up fiscal quarters.
2. **Lack of Traceability & Provenance**: Standard LLM-based summaries rarely cite exact page numbers, line items, and audit-verifiable excerpts.
3. **Unchecked Contradictions**: Discrepancies between MD&A narratives and statutory financial tables often go unnoticed without adversarial scrutiny.
4. **Lack of Bounded Human Oversight**: Automated agents frequently overstep boundaries without explicit human approval gates.

The **Trustworthy Multi-Agent Financial Research and Decision Support System** solves this by establishing a verifiable, citation-backed, multi-agent financial research architecture. The system combines deterministic calculation routines, multi-stage hybrid retrieval, seven specialized analytical lenses, three independent auditor/judge personas, and an explicit human review boundary.

---

## 2. Core Mandatory Requirements

- **Zero Autonomous Execution**: The system is strictly a decision support and research tool. It **must never autonomously execute financial transactions**, submit trades, or initiate binding legal/financial commitments.
- **Traceable Grounding**: Every numerical fact and narrative assertion must link directly to an immutable source document chunk, table cell, or SEC filing coordinate with SHA-256 provenance.
- **Deterministic Supremacy**: Hard mathematical calculations (e.g., margins, debt ratios, growth rates, cash flow reconciliations) are computed using deterministic Python code (`Decimal`/`pandas`), never LLM arithmetic.
- **Explicit Evaluation Verdicts**: Claims must receive deterministic status classifications: `PASS`, `QUALIFY`, `RETRIEVE_MORE`, `BLOCK`, or `INDETERMINATE`.
- **Seeded Inconsistency Detection**: The system must detect, flag, and escalate planted or real contradictory disclosures (e.g., narrative revenue growth claimed in MD&A vs. flat/declining GAAP revenues in the income statement).
- **Human-in-the-Loop Governance**: Analysts retain final authority to approve, reject, or adjust claims and reports before publication.

---

## 3. Researcher Workflow & Input Modes

The system supports two primary input modes:
1. **Automated Company Discovery**: The user enters a company identifier (e.g., Ticker `AAPL`, `MSFT`, or CIK) and selects target filing periods. The system automatically fetches verified regulatory disclosures from SEC EDGAR / official APIs.
2. **Direct Document Upload**: The user uploads local PDF filings, balance sheets, or earnings reports (with strict security validation and SHA-256 content deduplication).

### End-to-End Workflow:
```
[User Input: Ticker or Upload] 
         ↓
[Ingestion & Validation] ──→ SHA-256 deduplication, layout parsing, table extraction
         ↓
[Dual-Layer Knowledge Store] ──→ Normalized SQLite facts + Qdrant/BM25 retrieval index
         ↓
[Orchestrated Analysis] ──→ 7 Specialized Analysts run bounded research tasks
         ↓
[Tripartite Audit] ──→ Evidence Auditor, Financial Integrity, Adversarial Skeptic
         ↓
[Deterministic Gates] ──→ PASS / QUALIFY / RETRIEVE_MORE / BLOCK / INDETERMINATE
         ↓
[Draft Report Generation] ──→ Synthesized findings, metrics, and risk factors
         ↓
[Human Review Interface] ──→ Line-by-line claim inspection, feedback, and final sign-off
```

---

## 4. Expected Report Output

The generated Research & Decision Support Report contains:
- **Executive Summary & Stance**: Key findings, thesis, and overall risk posture.
- **Core Financial Health Scorecard**: Standardized solvency, profitability, and cash flow metrics calculated deterministically.
- **Detailed Segment & Operational Findings**: Narrative insights linked to specific citations.
- **Evidence & Discrepancy Ledger**: Complete disclosure of all detected inconsistencies, accounting anomalies, or conflicting statements.
- **Audit Verification Trace**: The verdicts from the three independent review judges.
- **Claim-Level Confidence Status**: Visual indicators distinguishing verified facts, qualified judgments, and abstentions.

---

## 5. Seeded Inconsistency Demonstration

To prove trustworthiness, the benchmark includes deliberate test cases containing:
- Conflicting revenue figures between text press releases and audited balance sheets.
- Incompatible restatements across multiple fiscal years.
- Non-GAAP metric adjustments that obscure underlying operating cash flow erosion.

The system is evaluated on its ability to trigger `BLOCK` or `QUALIFY` verdicts rather than hallucinating consensus.
