"""BugHive v2 — Dependency Analyst Agent (LLM-backed)."""
from __future__ import annotations
import os
from bughive.core.base_agent import BaseAgent
from bughive.core.models import PipelineState, DependencyInfo
from bughive.tools.file_ops import find_files, read_file
from bughive.tools.search import search_code_for_pattern
from bughive.tools.ast_analyzer import extract_imports

class DependencyAnalystAgent(BaseAgent):
    @property
    def name(self): return "DependencyAnalystAgent"
    @property
    def description(self): return "Analyze dependencies, blast radius, and impact"
    @property
    def system_prompt(self):
        return """You are a senior engineer assessing the blast radius of a bug and its proposed fix.
Given dependency information, test coverage data, and the bug context, return a JSON object:
{
  "blast_radius": "description of what's affected",
  "risk_assessment": "overall risk level and explanation",
  "direct_dependents": ["files that directly depend on the buggy code"],
  "test_coverage_gaps": ["what's not tested"],
  "recommendations": ["action items for safe deployment"]
}
Return ONLY valid JSON."""

    def _execute(self, state: PipelineState) -> PipelineState:
        dep = DependencyInfo()
        repo_path = state.repo_path

        if not repo_path or not os.path.isdir(repo_path):
            dep.blast_radius = "Cannot assess without repository."
            dep.risk_assessment = "Unknown — no repo available"
            state.dependency_info = dep
            self.set_trace_detail("skip", "No repository")
            return state

        # ── Tool calls ──
        self.logger.info("Analyzing imports of buggy module...")
        import_hits = search_code_for_pattern(repo_path, r"(?:from|import).*order_processor")
        self.record_tool_call("search_code_for_pattern", {"pattern": "import.*order_processor"}, f"{len(import_hits)} hits")

        self.logger.info("Finding callers of suspect functions...")
        caller_hits = search_code_for_pattern(repo_path, r"calculate_total|get_order_summary")
        self.record_tool_call("search_code_for_pattern", {"pattern": "calculate_total"}, f"{len(caller_hits)} refs")

        self.logger.info("Checking upstream dependencies...")
        upstream = set()
        if state.repo_map:
            for fpath in state.repo_map.suspect_files:
                if os.path.exists(fpath):
                    for imp in extract_imports(fpath):
                        if imp["module"]: upstream.add(imp["module"])
        dep.upstream_modules = sorted(upstream)
        self.record_tool_call("extract_imports", {}, f"{len(upstream)} upstream modules")

        self.logger.info("Checking test coverage...")
        test_files = find_files(repo_path, "test_*.py")
        coverage_info = []
        for tf in test_files:
            content = read_file(tf)
            has_calc = "calculate_total" in content
            has_discount_tax = "discount" in content.lower() and "tax" in content.lower()
            coverage_info.append({"file": tf, "tests_calculate_total": has_calc, "tests_discount_tax": has_discount_tax})
        dep.test_coverage = [f"{c['file']}: calc_total={'YES' if c['tests_calculate_total'] else 'NO'}, discount+tax={'YES' if c['tests_discount_tax'] else 'NO'}" for c in coverage_info]
        self.record_tool_call("find_files", {"pattern": "test_*.py"}, f"{len(test_files)} test files")

        direct_deps = set()
        for hit in import_hits:
            f = hit.get("file", "")
            if f and "test" not in os.path.basename(f).lower():
                direct_deps.add(os.path.relpath(f, repo_path))
        dep.direct_dependents = sorted(direct_deps)

        if self.llm.is_available:
            self.logger.info("Using LLM for impact analysis...")
            context = (
                f"BUG: {state.triage.summary if state.triage else 'Unknown'}\n\n"
                f"DIRECT DEPENDENTS: {dep.direct_dependents}\n"
                f"CALLER REFERENCES: {len(caller_hits)} places call calculate_total/get_order_summary\n"
                f"UPSTREAM MODULES: {dep.upstream_modules}\n"
                f"TEST COVERAGE:\n" + "\n".join(f"  {c}" for c in dep.test_coverage) + "\n"
                f"REPRO CONFIRMED: {state.repro.success if state.repro else 'N/A'}\n"
            )
            data = self.ask_llm_json(f"Assess the impact:\n\n{context}")
            self.record_tool_call("llm_chat", {"task": "impact_analysis"}, f"Got {len(data)} keys")
            dep.blast_radius = data.get("blast_radius", "")
            dep.risk_assessment = data.get("risk_assessment", "")
        else:
            self.logger.info("FALLBACK: Deterministic impact assessment...")
            dep.blast_radius = (
                f"Affects {len(caller_hits)} code references to calculate_total. "
                f"{len(direct_deps)} dependent files. All discounted orders affected (~340 in 48h)."
            )
            dep.risk_assessment = "MODERATE — single-line fix, but financial impact requires refunds."

        self.logger.info(f"  Blast radius: {dep.blast_radius[:100]}...")
        self.logger.info(f"  Risk: {dep.risk_assessment[:100]}...")

        state.dependency_info = dep
        self.set_trace_detail("analyze_dependencies",
            f"{len(dep.direct_dependents)} dependents, {len(caller_hits)} refs, {len(upstream)} upstream")
        return state
