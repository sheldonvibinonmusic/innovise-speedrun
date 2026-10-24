"""Counter-Evidence Retrieval Service.

Generates targeted adversarial query transformations to search for disconfirming statements,
accounting restatements, risk caveats, and offsetting disclosures.
"""

import re
from typing import Any, Dict, List, Optional


OPPOSING_TERMS_MAP: Dict[str, List[str]] = {
    "growth": ["decline", "slowdown", "decrease", "contraction", "loss"],
    "increased": ["decreased", "declined", "reduced", "fell"],
    "expansion": ["compression", "headwinds", "margin pressure", "cost inflation"],
    "profitable": ["unprofitable", "operating loss", "impairment", "write-down"],
    "liquid": ["liquidity risk", "going concern", "debt maturity", "covenant breach"],
    "stable": ["volatile", "fluctuation", "material weakness", "restatement"],
    "strong": ["weakness", "deterioration", "adverse", "headwind"],
}


def generate_adversarial_queries(claim_statement: str) -> List[str]:
    """Generate adversarial query variations from a claim statement."""
    statement_lower = claim_statement.lower()
    queries = []

    # 1. Substitute positive sentiment terms with negative counterpart terms
    for term, counter_terms in OPPOSING_TERMS_MAP.items():
        if term in statement_lower:
            for c_term in counter_terms[:2]:
                neg_query = re.sub(rf"\b{term}\b", c_term, statement_lower)
                queries.append(neg_query)

    # 2. General risk & restatement search queries
    clean_nouns = re.findall(r"\b[A-Za-z]{4,}\b", statement_lower)
    core_nouns = " ".join(clean_nouns[:4])
    if core_nouns:
        queries.append(f"{core_nouns} risk factor adverse impact restatement")
        queries.append(f"{core_nouns} litigation contingency uncertainty")

    # Deduplicate and return top 3 variations
    unique_queries = []
    for q in queries:
        if q not in unique_queries:
            unique_queries.append(q)
    return unique_queries[:3]
