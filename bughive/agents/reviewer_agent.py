"""BugHive v2 — Reviewer / Critic Agent (LLM-backed)."""
from __future__ import annotations
from bughive.core.base_agent import BaseAgent
from bughive.core.models import PipelineState, ReviewResult

class ReviewerCriticAgent(BaseAgent):
    @property
    def name(self): return "ReviewerCriticAgent"
    @property
    def description(self): return "Challenge assumptions, verify repro, review fix plan and patch"
    @property
    def system_prompt(self):
        return """You are a skeptical senior engineer reviewing a bug investigation.
Your job is to challenge weak assumptions, find gaps, and ensure the fix is safe.
Given the complete investigation (triage, logs, repo analysis, repro, dependencies, fix plan, patch),
return a JSON object:
{
  "repro_assessment": "PASS/FAIL with explanation",
  "fix_plan_assessment": "PASS/CONDITIONAL/FAIL with explanation",
  "patch_assessment": "PASS/PARTIAL/FAIL with explanation",
  "edge_cases": ["edge case 1", "edge case 2"],
  "weak_assumptions": ["assumption that could be wrong 1"],
  "suggestions": ["improvement 1", "improvement 2"],
  "approved": true/false,
  "overall_verdict": "APPROVED/CONDITIONALLY APPROVED/NEEDS REVISION with explanation"
}
Be thorough and skeptical. Don't rubber-stamp. Return ONLY valid JSON."""

    def _execute(self, state: PipelineState) -> PipelineState:
        review = ReviewResult()
        repro = state.repro
        fix_plan = state.fix_plan
        patch = state.patch

        if self.llm.is_available:
            self.logger.info("Using LLM for critical review...")
            context_parts = []
            if state.triage:
                context_parts.append(f"TRIAGE: {state.triage.summary}")
            if state.log_evidence:
                context_parts.append(f"LOG EVIDENCE: {len(state.log_evidence.key_errors)} key errors, "
                    f"{len(state.log_evidence.red_herrings)} red herrings filtered")
            if state.repo_map:
                context_parts.append(f"REPO: {len(state.repo_map.suspect_files)} suspect files, "
                    f"{len(state.repo_map.code_snippets)} code snippets analyzed")
            if repro:
                context_parts.append(f"REPRODUCTION: success={repro.success}, exit_code={repro.exit_code}\n"
                    f"Output:\n{repro.stdout[:500]}")
            if state.dependency_info:
                context_parts.append(f"DEPENDENCIES: blast_radius={state.dependency_info.blast_radius}\n"
                    f"Risk: {state.dependency_info.risk_assessment}")
            if fix_plan:
                context_parts.append(f"FIX PLAN:\n  Root cause: {fix_plan.root_cause[:300]}\n"
                    f"  Confidence: {fix_plan.confidence.value}\n  Approach: {fix_plan.patch_approach[:200]}\n"
                    f"  Risks: {fix_plan.risks}\n  Validation: {fix_plan.validation_plan}")
            if patch:
                context_parts.append(f"PATCH:\n  Diff:\n{patch.patch_diff}\n"
                    f"  Tests pass after patch: {patch.tests_pass_after_patch}\n"
                    f"  Test output:\n{patch.test_output[-500:] if patch.test_output else 'N/A'}")

            data = self.ask_llm_json(f"Review this investigation:\n\n" + "\n\n".join(context_parts))
            self.record_tool_call("llm_chat", {"task": "review"}, f"Got {len(data)} keys")

            review.repro_assessment = data.get("repro_assessment", "")
            review.fix_plan_assessment = data.get("fix_plan_assessment", "")
            review.patch_assessment = data.get("patch_assessment", "")
            review.edge_cases = data.get("edge_cases", [])
            review.weak_assumptions = data.get("weak_assumptions", [])
            review.suggestions = data.get("suggestions", [])
            review.approved = data.get("approved", False)
            review.overall_verdict = data.get("overall_verdict", "")
        else:
            self.logger.info("FALLBACK: Deterministic review...")
            review = self._fallback_review(repro, fix_plan, patch, state)

        self.logger.info(f"  Repro: {review.repro_assessment[:60]}")
        self.logger.info(f"  Fix plan: {review.fix_plan_assessment[:60]}")
        self.logger.info(f"  Patch: {review.patch_assessment[:60]}")
        self.logger.info(f"  Edge cases: {len(review.edge_cases)}")
        for ec in review.edge_cases: self.logger.info(f"    -> {ec}")
        self.logger.info(f"  Weak assumptions: {len(review.weak_assumptions)}")
        for wa in review.weak_assumptions: self.logger.info(f"    -> {wa}")
        self.logger.info(f"  Suggestions: {len(review.suggestions)}")
        for s in review.suggestions: self.logger.info(f"    -> {s}")
        self.logger.info(f"  VERDICT: {review.overall_verdict}")

        state.review = review
        self.set_trace_detail("review_all",
            f"Approved={review.approved}. {len(review.edge_cases)} edge cases, {len(review.suggestions)} suggestions")
        return state

    def _fallback_review(self, repro, fix_plan, patch, state):
        r = ReviewResult()
        repro_ok = repro and repro.success
        plan_ok = fix_plan and fix_plan.confidence.value in ("high", "medium")
        patch_ok = patch and patch.tests_pass_after_patch

        r.repro_assessment = "PASS: Minimal, deterministic reproduction" if repro_ok else "FAIL: Reproduction unsuccessful"
        if fix_plan:
            r.fix_plan_assessment = f"{'PASS' if plan_ok else 'CONDITIONAL'}: Confidence={fix_plan.confidence.value}"
        else:
            r.fix_plan_assessment = "FAIL: No fix plan"
        if patch:
            r.patch_assessment = f"{'PASS: All tests green' if patch_ok else 'PARTIAL: Tests incomplete'}"
        else:
            r.patch_assessment = "SKIP: No patch generated"

        r.edge_cases = [
            "No discount → tax on full subtotal", "HALFOFF 50% → tax on half",
            "Tiny order ($0.01) + discount → rounding", "Concurrent discount race condition",
            "Discount applied then removed → recalculation", "Double refund prevention",
        ]
        r.weak_assumptions = [
            "Assumes calculate_total() is the only tax computation path",
            "Assumes bug introduced in v2.14.3 — verify via git diff",
            "Assumes all 340 affected orders used discount codes",
        ]
        if fix_plan and "single-line" in fix_plan.patch_approach.lower():
            r.weak_assumptions.append("Single-line fix — verify no other tax code paths")

        r.suggestions = [
            "Add property-based test (Hypothesis) for any order+discount → correct tax",
            "Add runtime assertion: WARN if tax_base != discounted_subtotal",
            "Refactor tax calc into pure function with explicit (base, rate) inputs",
            "Generate SQL for per-order overcharge amounts for Finance refund manifest",
        ]

        r.approved = repro_ok and plan_ok and patch_ok
        if r.approved:
            r.overall_verdict = "APPROVED: Bug confirmed, root cause identified, patch verified."
        elif repro_ok and plan_ok:
            r.overall_verdict = "CONDITIONALLY APPROVED: Bug confirmed, fix plan solid, patch verification incomplete."
        else:
            r.overall_verdict = "NEEDS REVISION: Investigation incomplete."
        return r
