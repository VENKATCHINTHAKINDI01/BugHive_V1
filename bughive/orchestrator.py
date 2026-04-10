"""BugHive v2 — Orchestrator with retry logic and structured output."""
from __future__ import annotations
import json, os, time
from datetime import datetime, timezone
from bughive.core.config import BugHiveConfig
from bughive.core.logger import get_logger
from bughive.core.models import PipelineState, AgentStatus
from bughive.agents import AGENT_REGISTRY

BANNER = r"""
  ____              _   _ _
 | __ ) _   _  __ _| | | (_)_   _____
 |  _ \| | | |/ _` | |_| | \ \ / / _ \
 | |_) | |_| | (_| |  _  | |\ V /  __/
 |____/ \__,_|\__, |_| |_|_| \_/ \___|
              |___/
  Multi-Agent Bug Investigation System v2.0
"""

class Orchestrator:
    def __init__(self, config: BugHiveConfig):
        self.config = config
        self.logger = get_logger("Orchestrator")
        self.agents = []
        for key in config.pipeline.agents:
            if key in AGENT_REGISTRY:
                self.agents.append(AGENT_REGISTRY[key](config))
            else:
                self.logger.warning(f"Unknown agent: {key}")

    def run_pipeline(self, bug_report_path, log_path, repo_path=None):
        print(BANNER)
        mode = "LLM" if self.config.llm.api_key else "FALLBACK (no API key)"
        self.logger.info("=" * 60)
        self.logger.info(f"  PIPELINE START — Mode: {mode}")
        self.logger.info("=" * 60)
        self.logger.info(f"  Report: {bug_report_path}")
        self.logger.info(f"  Logs:   {log_path}")
        self.logger.info(f"  Repo:   {repo_path or '(none)'}")
        self.logger.info(f"  Agents: {[a.name for a in self.agents]}")
        self.logger.info("=" * 60)

        state = PipelineState(
            bug_report_path=bug_report_path, log_path=log_path, repo_path=repo_path or "",
            pipeline_started_at=datetime.now(timezone.utc).isoformat(),
        )
        with open(bug_report_path) as f: state.bug_report_content = f.read()
        with open(log_path) as f: state.log_content = f.read()

        start = time.time()
        for i, agent in enumerate(self.agents, 1):
            self.logger.info(""); self.logger.info("━" * 60)
            self.logger.info(f"  Step {i}/{len(self.agents)}: {agent.name}")
            self.logger.info("━" * 60)

            retries, success = 0, False
            while retries <= self.config.pipeline.max_retries:
                try:
                    state = agent.run(state)
                    last = state.traces[-1] if state.traces else None
                    if last and last.status == AgentStatus.FAILED:
                        retries += 1
                        if retries <= self.config.pipeline.max_retries:
                            self.logger.warning(f"  Retry {retries}/{self.config.pipeline.max_retries}")
                        continue
                    success = True; break
                except Exception as e:
                    retries += 1; self.logger.error(f"  Exception: {e}")
                    if retries > self.config.pipeline.max_retries: break
            if not success and self.config.pipeline.fail_fast:
                self.logger.error("  fail_fast — stopping"); break

        elapsed = int((time.time() - start) * 1000)
        state.pipeline_finished_at = datetime.now(timezone.utc).isoformat()
        output_path = self._generate_output(state)
        self._print_summary(state, output_path, elapsed)
        return state, output_path

    def _generate_output(self, state):
        d = os.path.join(self.config.project_root, self.config.outputs.dir)
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, self.config.outputs.report_file)
        report = {
            "bughive_version": self.config.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "llm" if self.config.llm.api_key else "fallback",
            "pipeline": {"started": state.pipeline_started_at, "finished": state.pipeline_finished_at,
                         "agents": [t.agent_name for t in state.traces]},
            "bug_summary": {"title": state.triage.title if state.triage else "", "summary": state.triage.summary if state.triage else "",
                "symptoms": state.triage.symptoms if state.triage else [], "severity": state.triage.severity.value if state.triage else "",
                "hypotheses": state.triage.hypotheses if state.triage else [],
                "affected_components": state.triage.affected_components if state.triage else []},
            "evidence": {"key_errors": state.log_evidence.key_errors if state.log_evidence else [],
                "stack_traces": state.log_evidence.stack_traces if state.log_evidence else [],
                "anomalies": state.log_evidence.anomalies if state.log_evidence else [],
                "red_herrings": state.log_evidence.red_herrings if state.log_evidence else [],
                "deploy_correlation": state.log_evidence.correlated_deploys if state.log_evidence else [],
                "error_frequency": state.log_evidence.error_frequency if state.log_evidence else {}},
            "repo_analysis": {"files": state.repo_map.files_found if state.repo_map else [],
                "suspect_files": state.repo_map.suspect_files if state.repo_map else [],
                "suspect_functions": state.repo_map.suspect_functions if state.repo_map else [],
                "call_graph_sample": (state.repo_map.call_graph[:20] if state.repo_map else []),
                "class_hierarchy": state.repo_map.class_hierarchy if state.repo_map else {}},
            "reproduction": {"path": state.repro.script_path if state.repro else "", "command": state.repro.run_command if state.repro else "",
                "exit_code": state.repro.exit_code if state.repro else -1, "bug_confirmed": state.repro.success if state.repro else False,
                "stdout": state.repro.stdout if state.repro else "", "explanation": state.repro.explanation if state.repro else ""},
            "dependency_analysis": {"dependents": state.dependency_info.direct_dependents if state.dependency_info else [],
                "upstream": state.dependency_info.upstream_modules if state.dependency_info else [],
                "blast_radius": state.dependency_info.blast_radius if state.dependency_info else "",
                "risk": state.dependency_info.risk_assessment if state.dependency_info else "",
                "test_coverage": state.dependency_info.test_coverage if state.dependency_info else []},
            "root_cause": {"description": state.fix_plan.root_cause if state.fix_plan else "",
                "confidence": state.fix_plan.confidence.value if state.fix_plan else ""},
            "patch_plan": {"files": state.fix_plan.affected_files if state.fix_plan else [],
                "approach": state.fix_plan.patch_approach if state.fix_plan else "",
                "risks": state.fix_plan.risks if state.fix_plan else []},
            "patch": {"diff": state.patch.patch_diff if state.patch else "",
                "patch_file": state.patch.patch_file_path if state.patch else "",
                "tests_file": state.patch.new_tests_path if state.patch else "",
                "tests_pass": state.patch.tests_pass_after_patch if state.patch else False},
            "validation_plan": {"tests": state.fix_plan.validation_plan if state.fix_plan else [],
                "regression": state.fix_plan.regression_checks if state.fix_plan else []},
            "review": {"repro": state.review.repro_assessment if state.review else "",
                "fix_plan": state.review.fix_plan_assessment if state.review else "",
                "patch": state.review.patch_assessment if state.review else "",
                "edge_cases": state.review.edge_cases if state.review else [],
                "weak_assumptions": state.review.weak_assumptions if state.review else [],
                "suggestions": state.review.suggestions if state.review else [],
                "approved": state.review.approved if state.review else False,
                "verdict": state.review.overall_verdict if state.review else ""},
            "open_questions": ["Exact git diff v2.14.2..v2.14.3", "Complete list of 340 affected order IDs",
                "External tax service/webhook existence", "Batch recalculation job status",
                "Payment gateway refund procedure"],
            "agent_traces": [{"agent": t.agent_name, "status": t.status.value, "action": t.action,
                "detail": t.detail, "duration_ms": t.duration_ms, "llm_calls": t.llm_calls,
                "tool_calls": [{"tool": tc.tool_name, "result": tc.result_summary} for tc in t.tool_calls],
                "error": t.error} for t in state.traces],
        }
        with open(path, "w") as f: json.dump(report, f, indent=2, default=str)
        self.logger.info(f"Report: {path}")
        return path

    def _print_summary(self, state, output_path, elapsed_ms):
        self.logger.info(""); self.logger.info("=" * 60)
        self.logger.info("  BugHive Investigation Complete")
        self.logger.info("=" * 60)
        if state.repro: self.logger.info(f"  Bug Confirmed:  {'Yes' if state.repro.success else 'No'}")
        if state.fix_plan: self.logger.info(f"  Root Cause:     {state.fix_plan.confidence.value} confidence")
        if state.patch: self.logger.info(f"  Patch Tests:    {'Pass' if state.patch.tests_pass_after_patch else 'Incomplete'}")
        if state.review: self.logger.info(f"  Review:         {'APPROVED' if state.review.approved else state.review.overall_verdict[:40]}")
        self.logger.info(f"  Report:         {output_path}")
        self.logger.info(f"  Duration:       {elapsed_ms}ms")
        self.logger.info("")
        self.logger.info("  Agent Traces:")
        for t in state.traces:
            icon = "+" if t.status == AgentStatus.SUCCESS else "!"
            llm_tag = f" ({t.llm_calls} LLM)" if t.llm_calls else ""
            self.logger.info(f"    [{icon}] {t.agent_name}{llm_tag}: {(t.detail or '')[:55]}")
        self.logger.info("=" * 60)
