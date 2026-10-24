"""Research Quality Supervisor — "The Third Eye".

Monitors the entire workflow lifecycle, verifies node executions, detects evidence gaps,
and enforces bounded recovery policies without ungrounded LLM hand-waving:
- Detects missing subquestion evidence and unsupported material claims
- Evaluates judge verdicts under non-majority deterministic rules
- Bounded corrective retrieval: up to max_retries (default 2) targeted repairs
- Detects no-progress loops to avoid infinite retrieval cycles
- Emits explicit control actions: CONTINUE, REPAIR_RETRIEVAL, RETRY_OPERATION,
  MARK_DEGRADED_COVERAGE, ESCALATE, or STOP
"""

from typing import Any, Dict, List, Optional, Set
from app.agents.analyst_models import JudgeVerdict, SupervisorDecision


class ResearchQualitySupervisor:
    """The Third Eye: Audits research graph execution and directs bounded recovery."""

    def __init__(self, max_repair_budget: int = 2):
        self.max_repair_budget = max_repair_budget
        self.history_queries: Set[str] = set()

    def evaluate_workflow_state(
        self,
        current_stage: str,
        analyst_outputs: List[Any],
        judge_verdicts: List[JudgeVerdict],
        retrieval_history: List[str],
        remaining_repairs: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> SupervisorDecision:
        """Inspect workflow health and determine whether to proceed, repair, escalate, or stop."""
        context = context or {}

        # 1. Critical Check: Numerical Integrity Gate (BLOCK rule is absolute)
        for jv in judge_verdicts:
            if jv.judge_role == "Numerical and Temporal Integrity" and jv.overall_verdict == "BLOCK":
                return SupervisorDecision(
                    action="STOP",
                    reason="Critical numerical violation: deterministic calculation failed (division by zero, incompatible unit/currency).",
                    failed_condition="NUMERICAL_INTEGRITY_VIOLATION",
                    remaining_retries=remaining_repairs,
                )

        # 2. Check for required follow-up retrieval from Evidence or Skeptic Judges
        repair_queries = []
        for jv in judge_verdicts:
            if jv.overall_verdict in ("RETRIEVE_MORE", "QUALIFY") and jv.required_followup_retrieval:
                repair_queries.append(jv.required_followup_retrieval)

        # Also inspect missing evidence reported by analysts
        for out in analyst_outputs:
            if hasattr(out, "missing_evidence") and out.missing_evidence:
                for gap in out.missing_evidence:
                    if "TotalRevenue" in gap or "Prior period" in gap:
                        repair_queries.append(f"financial table {gap}")

        # 3. Determine if repair retrieval is justified and budgeted
        if repair_queries and remaining_repairs > 0:
            target_query = repair_queries[0]

            # Detect No-Progress Loop
            if target_query in self.history_queries:
                return SupervisorDecision(
                    action="ESCALATE",
                    reason=f"No-progress retrieval loop detected on '{target_query}'. Bypassing repeated retrieval.",
                    failed_condition="NO_PROGRESS_LOOP",
                    remaining_retries=0,
                    unresolved_uncertainties=[f"Repeated query '{target_query}' failed to yield new disclosures."],
                )

            self.history_queries.add(target_query)
            return SupervisorDecision(
                action="REPAIR_RETRIEVAL",
                reason=f"Targeted follow-up retrieval required: {target_query}.",
                failed_condition="EVIDENCE_DEFICIT",
                target_stage="retrieve_evidence",
                repair_query=target_query,
                remaining_retries=remaining_repairs - 1,
            )

        # 4. Check if any judge flagged material uncertainties or contradictions
        unresolved: List[str] = []
        has_qualification = False
        for jv in judge_verdicts:
            if jv.overall_verdict in ("QUALIFY", "INDETERMINATE"):
                has_qualification = True
                unresolved.append(f"[{jv.judge_role}]: {jv.concise_explanation}")

        for out in analyst_outputs:
            if hasattr(out, "completion_status") and out.completion_status == "DEGRADED":
                unresolved.extend(out.warnings)

        if has_qualification or unresolved:
            return SupervisorDecision(
                action="ESCALATE",
                reason="Research completed with material qualifications or counter-evidence requiring human review.",
                remaining_retries=remaining_repairs,
                unresolved_uncertainties=unresolved,
            )

        # 5. Clean pass
        return SupervisorDecision(
            action="CONTINUE",
            reason="All deterministic calculations, citations, and counter-evidence checks passed successfully.",
            remaining_retries=remaining_repairs,
        )
