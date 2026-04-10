"""BugHive v2 — Fix Planner Agent (LLM-backed)."""
from __future__ import annotations
from bughive.core.base_agent import BaseAgent
from bughive.core.models import PipelineState, FixPlan, Confidence

class FixPlannerAgent(BaseAgent):
    @property
    def name(self): return "FixPlannerAgent"
    @property
    def description(self): return "Propose root cause hypothesis and patch plan"
    @property
    def system_prompt(self):
        return """You are a principal engineer diagnosing a bug's root cause and proposing a fix.
Given all investigation evidence (triage, logs, code, reproduction results, dependency analysis),
return a JSON object:
{
  "root_cause": "detailed technical explanation of why the bug occurs",
  "confidence": "high|medium|low",
  "affected_files": ["file paths"],
  "patch_approach": "step-by-step description of the fix",
  "risks": ["risk 1", "risk 2"],
  "validation_plan": ["test to add 1", "test to add 2"],
  "regression_checks": ["check 1", "check 2"]
}
Reference specific evidence: reproduction output, log entries, source code lines.
Return ONLY valid JSON."""

    def _execute(self, state: PipelineState) -> PipelineState:
        plan = FixPlan()

        repro_ok = state.repro and state.repro.success
        log_ok = state.log_evidence and len(state.log_evidence.key_errors) > 0
        repo_ok = state.repo_map and len(state.repo_map.suspect_functions) > 0

        self.logger.info(f"Evidence: repro={repro_ok}, logs={log_ok}, repo={repo_ok}")

        if self.llm.is_available:
            self.logger.info("Using LLM to formulate fix plan...")
            context_parts = []
            if state.triage:
                context_parts.append(f"TRIAGE: {state.triage.summary}\nHypotheses: {state.triage.hypotheses}")
            if state.log_evidence:
                context_parts.append(f"LOG EVIDENCE:\n  Key errors: {state.log_evidence.key_errors}\n  Anomalies: {state.log_evidence.anomalies}\n  Deploys: {state.log_evidence.correlated_deploys}")
            if state.repo_map:
                context_parts.append(f"REPO:\n  Suspect files: {state.repo_map.suspect_files}\n  Suspect functions: {state.repo_map.suspect_functions}")
                for s in state.repo_map.code_snippets:
                    context_parts.append(f"SOURCE ({s['function']}):\n{s['source']}")
            if state.repro:
                context_parts.append(f"REPRODUCTION:\n  Bug confirmed: {state.repro.success}\n  Exit code: {state.repro.exit_code}\n  Output:\n{state.repro.stdout[:1000]}")
            if state.dependency_info:
                context_parts.append(f"DEPENDENCIES:\n  Blast radius: {state.dependency_info.blast_radius}\n  Risk: {state.dependency_info.risk_assessment}")

            data = self.ask_llm_json(f"Propose a fix plan:\n\n" + "\n\n".join(context_parts))
            self.record_tool_call("llm_chat", {"task": "fix_plan"}, f"Got {len(data)} keys")

            plan.root_cause = data.get("root_cause", "")
            conf = data.get("confidence", "medium").lower()
            for c in Confidence:
                if c.value == conf: plan.confidence = c; break
            plan.affected_files = data.get("affected_files", [])
            plan.patch_approach = data.get("patch_approach", "")
            plan.risks = data.get("risks", [])
            plan.validation_plan = data.get("validation_plan", [])
            plan.regression_checks = data.get("regression_checks", [])
        else:
            self.logger.info("FALLBACK: Deterministic fix plan...")
            plan.root_cause = (
                "In OrderProcessor.calculate_total(), tax is computed as subtotal * TAX_RATE "
                "instead of discounted_subtotal * TAX_RATE. The 8% tax is applied to the "
                "original subtotal, ignoring discounts."
            )
            score = sum([repro_ok, log_ok, repo_ok])
            plan.confidence = Confidence.HIGH if score >= 3 else Confidence.MEDIUM if score >= 2 else Confidence.LOW
            plan.affected_files = [f.get("file", f) if isinstance(f, dict) else f for f in (state.repo_map.suspect_files if state.repo_map else ["src/order_processor.py"])]
            plan.patch_approach = "Change `tax = (subtotal * self.TAX_RATE)` to `tax = (discounted_subtotal * self.TAX_RATE)`"
            plan.risks = ["~340 orders need refund processing", "Verify no other tax code paths exist", "Payment gateway refunds needed"]
            plan.validation_plan = ["Test discount+tax interaction", "Test no-discount orders", "Test all discount codes", "Run full test suite"]
            plan.regression_checks = ["No-discount orders unchanged", "HALFOFF 50% edge case", "Small order rounding"]

        self.logger.info(f"  Root cause: {plan.root_cause[:100]}...")
        self.logger.info(f"  Confidence: {plan.confidence.value}")
        self.logger.info(f"  Risks: {len(plan.risks)}")
        self.logger.info(f"  Validation steps: {len(plan.validation_plan)}")

        state.fix_plan = plan
        self.set_trace_detail("propose_fix",
            f"Root cause identified ({plan.confidence.value} confidence). {len(plan.risks)} risks, {len(plan.validation_plan)} validation steps.")
        return state
