# Agent Architecture: Analysts, Reviewers, and Deterministic Gates

## 1. Multi-Agent Design Philosophy

In financial research, model consensus is not a guarantee of truth. Two or three LLMs can readily agree on a plausible hallucination or a flawed mathematical calculation.

Therefore, our architecture enforces a strict hierarchy:
1. **Deterministic Verification Gates** have absolute veto power over any LLM consensus.
2. **Specialized Logical Roles** split complex research into 7 distinct investigative angles.
3. **Tripartite Review Judges** provide adversarial skepticism and citation audit before any claim enters a report.

---

## 2. Seven Specialized Analyst Responsibilities

The seven analyst roles represent modular analytical functions (invoked with distinct prompts and tool constraints):

```
                                  [Research Task]
                                         │
        ┌──────────────┬──────────────┬──┴───────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼              ▼              ▼
  Profitability    Cash Flow    Liquidity/Debt   Historical     Business/Risk   Data Quality
     Analyst        Analyst        Analyst         Trends          Analyst        Analyst
        │              │              │              │              │              │
        └──────────────┴──────────────┴──┬───────────┴──────────────┴──────────────┘
                                         ▼
                                [Evidence Researcher]
                                (Cross-cutting query
                                & context gathering)
```

### 1. Profitability Analyst (`app/agents/analysts/profitability.py`)
- **Focus**: Gross margins, operating margins, EBITDA, net margin progression.
- **Analysis**: Revenue segment breakdowns, product vs. service margin shifts, COGS drivers.
- **Rules**: Must identify whether margin expansion stems from operational efficiency or one-off accounting items.

### 2. Cash Flow Analyst (`app/agents/analysts/cash_flow.py`)
- **Focus**: Operating cash flow (OCF), capital expenditures (CapEx), and free cash flow (FCF).
- **Analysis**: Quality of earnings (OCF vs. Net Income divergence), working capital changes.
- **Rules**: Emphasizes cash generation over accrual accounting profits.

### 3. Liquidity and Debt Analyst (`app/agents/analysts/liquidity_debt.py`)
- **Focus**: Balance sheet health, debt maturities, leverage ratios.
- **Analysis**: Current ratio, quick ratio, debt-to-equity, interest coverage ratio, covenant compliance.
- **Rules**: Highlights impending debt maturities within 12–24 months.

### 4. Historical Trend Analyst (`app/agents/analysts/historical_trends.py`)
- **Focus**: Multi-year trajectories (3-year and 5-year CAGR), cyclical patterns.
- **Analysis**: Baseline normalizations, comparison across constant fiscal reporting periods.
- **Rules**: Flags changes in accounting definitions or fiscal year calendar shifts.

### 5. Business and Risk Analyst (`app/agents/analysts/business_risk.py`)
- **Focus**: MD&A disclosures, Item 1A Risk Factors, legal proceedings.
- **Analysis**: Customer concentration, supply chain vulnerabilities, regulatory threats.
- **Rules**: Correlates qualitative risk warnings with observed numerical variances.

### 6. Evidence Research Analyst (`app/agents/analysts/evidence_research.py`)
- **Focus**: Query reformulation, targeted footnote retrieval, and context expansion.
- **Analysis**: Searches supporting details for claims made by other analysts.
- **Rules**: Retrieves exact sentence quotes and page coordinates.

### 7. Data Quality & Anomaly Analyst (`app/agents/analysts/data_quality.py`)
- **Focus**: Accounting anomalies, restatements, round-number patterns, Benford's law flags.
- **Analysis**: Discrepancies between press release headlines and official SEC tables.
- **Rules**: Highlights unexplained balance sheet balancing plugs or audit opinion qualifications.

---

## 3. Three Independent Review Judges

### 1. Evidence and Citation Auditor (`app/agents/judges/evidence_auditor.py`)
- **Mandate**: Verify that cited document chunks explicitly support the proposed claim.
- **Methodology**: Checks verbatim overlap, semantic entailment, and verifies the source page exists.
- **Verdicts**: `PASS` if grounded; `RETRIEVE_MORE` if citation is incomplete; `BLOCK` if quote does not support claim.

### 2. Financial Integrity and Consistency Auditor (`app/agents/judges/financial_integrity.py`)
- **Mandate**: Validate that mathematical formulas, ratio calculations, and balance sheet balances are arithmetically exact.
- **Methodology**: Recomputes ratios using deterministic code (`Decimal` precision).
- **Verdicts**: `PASS` if math matches; `BLOCK` if calculation diverges.

### 3. Adversarial Skeptic and Counter-Evidence Reviewer (`app/agents/judges/adversarial_skeptic.py`)
- **Mandate**: Actively attempt to falsify positive claims.
- **Methodology**: Executes targeted counter-evidence queries against the retrieval engine.
- **Verdicts**: `PASS` if no contradiction found; `QUALIFY` if offsetting risks exist; `BLOCK` if direct counter-evidence proves claim false.

---

## 4. Deterministic Gates vs. Model Consensus

```
                   Analyst Proposed Claim
                             │
                             ▼
             [Deterministic Python Validation]
           (Formula exact? Dates aligned? Units valid?)
                     /                \
                   FAIL              PASS
                   /                    \
     [BLOCK: Immediate Rejection]    [Tripartite Judge Audit]
                                     /          |          \
                                  Evidence  Financial   Adversarial
                                   Auditor  Integrity     Skeptic
                                     \          |          /
                                      ▼         ▼         ▼
                                    [Final Aggregation Gate]
                                    (PASS/QUALIFY/BLOCK/etc.)
```

**Why Deterministic Rules Win**:
- If an LLM states "Gross margin increased by 200 bps to 45%", and `(Gross Profit / Revenue)` computed in Python yields `41.2%`, the deterministic calculation **immediately blocks** the claim. No LLM discussion or voting can override verified arithmetic.
