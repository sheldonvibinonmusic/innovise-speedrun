# Evaluation & Verification Framework

## 1. Evaluation Philosophy

Standard LLM benchmark metrics (such as BLEU or ROUGE) are useless for financial decision support. A report that reads fluently but misstates an operating margin by 200 basis points is dangerous.

The evaluation framework evaluates trustworthiness across six distinct axes:
1. **Retrieval Quality**
2. **Source-Support Correctness (Faithfulness)**
3. **Numerical & Mathematical Accuracy**
4. **Contradiction & Inconsistency Detection**
5. **Abstention & Calibration Quality**
6. **Operational Latency & Resource Consumption**

*Note: No target accuracy percentages are claimed prior to formal empirical benchmarking in Phase 4.*

---

## 2. Evaluation Axes & Metrics

### 2.1 Retrieval Quality
- **Context Recall**: Proportion of ground-truth filing passages retrieved in the top-10 candidates.
- **Context Precision**: Ratio of relevant retrieved chunks to total retrieved chunks.
- **MRR (Mean Reciprocal Rank)**: Position of the first relevant chunk containing the critical metric.

### 2.2 Source-Support Correctness (Faithfulness)
- **Citation Precision**: Proportion of claims where the cited chunk directly supports the assertion.
- **Hallucination Rate**: Frequency of factual claims made without any valid grounding in source documents.
- **Quote Exactness**: Verbatim fidelity of cited excerpts compared to original PDF text.

### 2.3 Numerical & Mathematical Accuracy
- **Formula Fidelity**: Percentage of ratio calculations matching deterministic Python `Decimal` results.
- **Scale Consistency**: Prevention of thousand/million/billion scale confusion errors.
- **Period Alignment**: Correct pairing of metrics across identical fiscal quarters/years without temporal blending.

### 2.4 Contradiction & Inconsistency Detection
- **Seeded Contradiction Recall**: Ability to detect deliberately planted discrepancies (e.g. Press release claims +15% revenue; 10-K shows -2%).
- **Discrepancy Reporting**: Correct escalation of real-world restatements and adjustments to the Discrepancy Ledger.
- **Gate Accuracy**: Appropriate triggering of `BLOCK` or `QUALIFY` gate verdicts on contradictory claims.

### 2.5 Abstention & Calibration Quality
- **Abstention Precision**: When information is missing from filings, the system must emit `INDETERMINATE` rather than guessing or interpolating.
- **Overconfidence Penalty**: High penalty for confident claims backed by weak or missing evidence.

### 2.6 Latency & Operational Efficiency
- **End-to-End Run Duration**: Time to complete document parsing, analysis, verification, and report synthesis.
- **Token Efficiency**: Prompt token usage and estimated inference cost per complete research report.

---

## 3. Benchmark Suite Architecture (`app/evaluation/`)

The evaluation test suite comprises:
- **`benchmark.py`**: Automated runner executing test cases against curated financial disclosures.
- **`metrics.py`**: Mathematical scoring routines for citation fidelity, mathematical error tolerance, and contradiction capture.
- **`tests/fixtures/`**: Paired PDF filings, ground-truth fact registries, and intentionally conflicting synthetic filings for stress testing.
