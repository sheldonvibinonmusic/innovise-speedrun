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

        def _get_field(obj: Any, key: str, default: Any = None) -> Any:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        # 1. Critical Check: Any Judge BLOCK verdict is absolute
        for jv in judge_verdicts:
            if jv.overall_verdict == "BLOCK":
                failed_cond = "NUMERICAL_INTEGRITY_VIOLATION" if jv.judge_role == "Numerical and Temporal Integrity" else "VERIFICATION_GATE_BLOCK"
                return SupervisorDecision(
                    action="STOP",
                    reason=f"Verification gate BLOCKED by {jv.judge_role}: {jv.concise_explanation}",
                    failed_condition=failed_cond,
                    remaining_retries=remaining_repairs,
                    unresolved_uncertainties=[f"[{jv.judge_role}]: {jv.concise_explanation}"],
                )

        # 2. Check for required follow-up retrieval from Evidence or Skeptic Judges
        repair_queries = []
        for jv in judge_verdicts:
            if jv.overall_verdict in ("RETRIEVE_MORE", "QUALIFY") and jv.required_followup_retrieval:
                repair_queries.append(jv.required_followup_retrieval)

        # Also inspect missing evidence reported by analysts (dictionary or model aware)
        for out in analyst_outputs:
            missing = _get_field(out, "missing_evidence", [])
            if missing:
                for gap in missing:
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

        # Check if analyst outputs are missing when not in repair or block
        if not analyst_outputs and not judge_verdicts:
            return SupervisorDecision(
                action="STOP",
                reason="No specialist analyst outputs or judge evaluations were produced.",
                failed_condition="NO_ANALYST_OUTPUTS",
                remaining_retries=0,
                unresolved_uncertainties=["Specialist analysts failed to produce research findings."],
            )

        # 4. Check if any judge flagged material uncertainties or contradictions
        unresolved: List[str] = []
        has_qualification = False
        for jv in judge_verdicts:
            if jv.overall_verdict in ("QUALIFY", "INDETERMINATE"):
                has_qualification = True
                unresolved.append(f"[{jv.judge_role}]: {jv.concise_explanation}")

        # Also inspect degraded/failed completion status and missing evidence from analysts
        for out in analyst_outputs:
            c_status = _get_field(out, "completion_status", "COMPLETE")
            warnings = _get_field(out, "warnings", [])
            missing = _get_field(out, "missing_evidence", [])
            role = _get_field(out, "analyst_role", "Analyst")
            if c_status in ("DEGRADED", "FAILED", "UNAVAILABLE"):
                has_qualification = True
                unresolved.extend(warnings or [f"{role} reported {c_status} completion status."])
            if missing:
                has_qualification = True
                unresolved.extend([f"[{role}] Evidence gap: {m}" for m in missing])

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
