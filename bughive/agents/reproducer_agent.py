"""BugHive v2 — Reproducer Agent (LLM-backed)."""
from __future__ import annotations
import os
from bughive.core.base_agent import BaseAgent
from bughive.core.models import PipelineState, ReproResult
from bughive.tools.runner import run_script
from bughive.tools.file_ops import write_file

# Fallback repro template — used when LLM is unavailable
FALLBACK_REPRO = '''#!/usr/bin/env python3
"""BugHive — Minimal Reproduction Script (fallback-generated)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "{repo_rel}"))
from src.order_processor import OrderProcessor
from decimal import Decimal

def main():
    proc = OrderProcessor()
    proc.create_order("REPRO-001", [{{"name": "Item", "price": 100.00, "quantity": 2}}], "CUST-REPRO")
    proc.apply_discount("REPRO-001", "SAVE20")
    totals = proc.calculate_total("REPRO-001")
    print("=" * 50)
    print("BugHive Reproduction Result")
    print("=" * 50)
    print(f"  Subtotal:            ${{totals['subtotal']}}")
    print(f"  Discount (20%):      -${{totals['discount_amount']}}")
    print(f"  Discounted Subtotal: ${{totals['discounted_subtotal']}}")
    print(f"  Tax (8%):            ${{totals['tax']}}")
    print(f"  Total:               ${{totals['total']}}")
    print()
    expected_tax = (Decimal("160.00") * Decimal("0.08")).quantize(Decimal("0.01"))
    actual_tax = Decimal(totals["tax"])
    print(f"  Expected tax: ${{expected_tax}}")
    print(f"  Actual tax:   ${{actual_tax}}")
    if actual_tax != expected_tax:
        print(f"  BUG CONFIRMED: Overcharge of ${{actual_tax - expected_tax}}")
        sys.exit(1)
    else:
        print(f"  Tax correct — bug not reproduced")
        sys.exit(0)

if __name__ == "__main__":
    main()
'''

class ReproducerAgent(BaseAgent):
    @property
    def name(self): return "ReproductionAgent"
    @property
    def description(self): return "Generate and execute minimal reproduction script"
    @property
    def system_prompt(self):
        return """You are a QA engineer creating a minimal reproduction script for a bug.
Given the bug triage, log evidence, and source code, write a Python script that:
1. Imports and uses the actual buggy module
2. Sets up minimal test data that triggers the bug
3. Asserts the expected vs actual behavior
4. Prints clear output showing the discrepancy
5. Exits with code 1 if bug is confirmed, 0 if not

The script must be standalone, runnable with `python3 script.py`.
It must add the repo to sys.path using: sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "REPO_REL_PATH"))

Return ONLY the Python script code. No markdown, no backticks, no explanation. Just the raw Python."""

    def _execute(self, state: PipelineState) -> PipelineState:
        result = ReproResult()
        output_dir = os.path.abspath(os.path.join(self.config.project_root, self.config.outputs.dir))
        os.makedirs(output_dir, exist_ok=True)
        repro_path = os.path.join(output_dir, self.config.outputs.repro_script)

        # Compute relative path from outputs/ to sample_repo/
        if state.repo_path and os.path.isdir(state.repo_path):
            repo_rel = os.path.relpath(os.path.abspath(state.repo_path), output_dir)
        else:
            repo_rel = "../sample_repo"

        if self.llm.is_available:
            self.logger.info("Using LLM to generate reproduction script...")
            context_parts = [f"REPO RELATIVE PATH (from script location): {repo_rel}"]
            if state.triage:
                context_parts.append(f"BUG SUMMARY: {state.triage.summary}")
                context_parts.append(f"EXPECTED: {state.triage.expected_behavior}")
                context_parts.append(f"ACTUAL: {state.triage.actual_behavior}")
                context_parts.append(f"HYPOTHESES: {state.triage.hypotheses}")
            if state.log_evidence:
                context_parts.append(f"KEY ERRORS FROM LOGS: {state.log_evidence.key_errors}")
            if state.repo_map and state.repo_map.code_snippets:
                for snippet in state.repo_map.code_snippets:
                    context_parts.append(f"SOURCE CODE ({snippet['function']}):\n{snippet['source']}")

            script_content = self.ask_llm("\n\n".join(context_parts))
            # Clean markdown fences if LLM added them
            if script_content.strip().startswith("```"):
                lines = script_content.strip().split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                script_content = "\n".join(lines)
            self.record_tool_call("llm_chat", {"task": "generate_repro"}, f"{len(script_content)} chars")
        else:
            self.logger.info("FALLBACK: Using template-based repro script...")
            script_content = FALLBACK_REPRO.format(repo_rel=repo_rel)

        # Write and execute
        write_file(repro_path, script_content)
        result.script_path = repro_path
        result.script_content = script_content
        result.run_command = f"python3 {repro_path}"
        self.record_tool_call("write_file", {"path": repro_path}, f"Wrote repro script")

        self.logger.info(f"Executing: {repro_path}")
        run_result = run_script(repro_path, timeout=self.config.tools.script_timeout)
        self.record_tool_call("run_script", {"path": repro_path}, f"Exit code: {run_result['exit_code']}")

        result.exit_code = run_result["exit_code"]
        result.stdout = run_result["stdout"]
        result.stderr = run_result["stderr"]

        self.logger.info("--- Repro Output ---")
        for line in result.stdout.splitlines(): self.logger.info(f"  | {line}")
        if result.stderr.strip():
            for line in result.stderr.splitlines(): self.logger.warning(f"  | {line}")

        if result.exit_code == 1:
            result.success = True
            result.explanation = "Bug successfully reproduced. Script exited with code 1 confirming the bug."
            self.logger.info("BUG REPRODUCED (exit code 1)")
        elif result.exit_code == 0:
            result.success = False
            result.explanation = "Bug NOT reproduced — script exited 0."
            self.logger.warning("Bug NOT reproduced (exit code 0)")
        else:
            result.success = False
            result.explanation = f"Script error (exit {result.exit_code}): {result.stderr[:200]}"
            self.logger.error(f"Script error: {result.stderr[:200]}")

        state.repro = result
        self.set_trace_detail("generate_and_run_repro", result.explanation)
        return state
