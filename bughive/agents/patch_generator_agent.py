"""BugHive v2 — Patch Generator Agent (LLM-backed)."""
from __future__ import annotations
import os, shutil
from bughive.core.base_agent import BaseAgent
from bughive.core.models import PipelineState, PatchResult
from bughive.tools.file_ops import write_file, read_file
from bughive.tools.diff_generator import generate_unified_diff
from bughive.tools.runner import run_pytest

FALLBACK_TESTS = '''"""BugHive — Generated regression tests for tax fix."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from decimal import Decimal
from src.order_processor import OrderProcessor

class TestTaxOnDiscountedOrders:
    def _order_with_discount(self, price, qty, code):
        p = OrderProcessor()
        p.create_order("T1", [{"name": "Item", "price": price, "quantity": qty}], "C1")
        p.apply_discount("T1", code)
        return p.calculate_total("T1")

    def test_save20_tax(self):
        t = self._order_with_discount(100.0, 2, "SAVE20")
        assert t["tax"] == "12.80", f"Expected 12.80, got {t['tax']}"

    def test_save10_tax(self):
        t = self._order_with_discount(100.0, 1, "SAVE10")
        assert t["tax"] == "7.20"

    def test_vip30_tax(self):
        t = self._order_with_discount(150.0, 1, "VIP30")
        assert t["tax"] == "8.40"

    def test_halfoff_tax(self):
        t = self._order_with_discount(100.0, 2, "HALFOFF")
        assert t["tax"] == "8.00"

    def test_no_discount_unchanged(self):
        p = OrderProcessor()
        p.create_order("T2", [{"name": "Item", "price": 100.0, "quantity": 1}], "C1")
        t = p.calculate_total("T2")
        assert t["tax"] == "8.00"

    def test_small_order_rounding(self):
        t = self._order_with_discount(1.0, 1, "SAVE20")
        assert t["discounted_subtotal"] == "0.80"
        assert t["tax"] == "0.06"
'''

class PatchGeneratorAgent(BaseAgent):
    @property
    def name(self): return "PatchGeneratorAgent"
    @property
    def description(self): return "Generate code patch, new tests, and verify the fix"
    @property
    def system_prompt(self):
        return """You are a senior engineer writing a code patch and regression tests.
Given the root cause analysis and source code, generate:
1. The exact text to find in the source file (old_code)
2. The replacement text (new_code)
3. A complete pytest test file that verifies the fix

Return a JSON object:
{
  "old_code": "exact text to replace in source",
  "new_code": "replacement text",
  "test_file_content": "complete Python test file content"
}
The test file should import from the repo, test multiple discount scenarios, and include edge cases.
Return ONLY valid JSON."""

    def _execute(self, state: PipelineState) -> PipelineState:
        patch = PatchResult()
        output_dir = os.path.abspath(os.path.join(self.config.project_root, self.config.outputs.dir))
        os.makedirs(output_dir, exist_ok=True)

        # Find source file
        source_file = None
        if state.repo_map:
            for f in state.repo_map.suspect_files:
                if os.path.exists(f) and "test" not in os.path.basename(f).lower():
                    source_file = f; break
        if not source_file and state.repo_path:
            candidate = os.path.join(state.repo_path, "src", "order_processor.py")
            if os.path.exists(candidate): source_file = candidate

        old_code = "        tax = (subtotal * self.TAX_RATE).quantize("
        new_code = "        tax = (discounted_subtotal * self.TAX_RATE).quantize("
        old_comment = "        # BUG IS HERE: tax is calculated on `subtotal` instead of `discounted_subtotal`"
        new_comment = "        # FIX: tax calculated on discounted subtotal"
        tests_content = FALLBACK_TESTS

        if self.llm.is_available and source_file:
            self.logger.info("Using LLM to generate patch and tests...")
            source = read_file(source_file)
            context = (
                f"ROOT CAUSE: {state.fix_plan.root_cause if state.fix_plan else 'Unknown'}\n\n"
                f"SOURCE FILE ({source_file}):\n{source}\n\n"
                f"PATCH APPROACH: {state.fix_plan.patch_approach if state.fix_plan else 'Fix tax calculation'}"
            )
            try:
                data = self.ask_llm_json(f"Generate patch and tests:\n\n{context}")
                self.record_tool_call("llm_chat", {"task": "generate_patch"}, f"Got {len(data)} keys")
                if data.get("old_code"): old_code = data["old_code"]
                if data.get("new_code"): new_code = data["new_code"]
                if data.get("test_file_content"):
                    tc = data["test_file_content"]
                    if tc.strip().startswith("```"):
                        lines = tc.strip().split("\n")
                        tc = "\n".join(l for l in lines if not l.strip().startswith("```"))
                    tests_content = tc
            except Exception as e:
                self.logger.warning(f"LLM patch generation failed, using fallback: {e}")
        else:
            self.logger.info("FALLBACK: Using template patch and tests...")

        # Generate unified diff
        if source_file and os.path.exists(source_file):
            original = read_file(source_file)
            modified = original
            if old_comment in modified: modified = modified.replace(old_comment, new_comment, 1)
            if old_code in modified: modified = modified.replace(old_code, new_code, 1)
            diff = generate_unified_diff(original, modified,
                f"a/{os.path.basename(source_file)}", f"b/{os.path.basename(source_file)}")
            patch.patch_diff = diff
            self.record_tool_call("generate_unified_diff", {"file": source_file}, f"{len(diff)} chars")

            patch_path = os.path.join(output_dir, self.config.outputs.patch_file)
            write_file(patch_path, diff)
            patch.patch_file_path = patch_path
            self.logger.info(f"Patch written: {patch_path}")
            for line in diff.splitlines(): self.logger.info(f"  {line}")

        # Write tests
        tests_path = os.path.join(output_dir, "test_tax_fix_regression.py")
        write_file(tests_path, tests_content)
        patch.new_tests_content = tests_content
        patch.new_tests_path = tests_path
        self.record_tool_call("write_file", {"path": tests_path}, f"{tests_content.count('def test_')} tests")

        # Apply patch and verify
        if source_file:
            self.logger.info("Applying patch to copy and running tests...")
            patched_repo = os.path.join(output_dir, "_patched_repo")
            if os.path.exists(patched_repo): shutil.rmtree(patched_repo)
            shutil.copytree(os.path.dirname(os.path.dirname(source_file)), patched_repo)

            patched_file = os.path.join(patched_repo, "src", "order_processor.py")
            content = read_file(patched_file)
            if old_comment in content: content = content.replace(old_comment, new_comment, 1)
            if old_code in content: content = content.replace(old_code, new_code, 1)
            write_file(patched_file, content)
            patch.patch_applied = True

            write_file(os.path.join(patched_repo, "tests", "test_tax_fix_regression.py"), tests_content)

            test_result = run_pytest(os.path.join(patched_repo, "tests"), cwd=patched_repo,
                                     timeout=self.config.tools.script_timeout)
            self.record_tool_call("run_pytest", {"path": "patched_repo/tests"},
                f"passed={test_result.get('passed',0)} failed={test_result.get('failed',0)}")

            patch.tests_pass_after_patch = test_result["exit_code"] == 0
            patch.test_output = test_result["stdout"]

            self.logger.info("--- Test Results (patched) ---")
            for line in test_result["stdout"].splitlines()[-10:]: self.logger.info(f"  | {line}")
            self.logger.info(f"Tests pass: {patch.tests_pass_after_patch}")

            shutil.rmtree(patched_repo, ignore_errors=True)

        state.patch = patch
        self.set_trace_detail("generate_patch",
            f"Diff: {len(patch.patch_diff)} chars, {tests_content.count('def test_')} tests, "
            f"pass_after_patch={patch.tests_pass_after_patch}")
        return state
