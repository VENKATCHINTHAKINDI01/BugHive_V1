"""
BugHive v2 — Data Models.
All shared data structures for inter-agent communication.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TriageResult:
    title: str = ""
    summary: str = ""
    expected_behavior: str = ""
    actual_behavior: str = ""
    environment: dict[str, str] = field(default_factory=dict)
    symptoms: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    severity: Severity = Severity.MEDIUM
    affected_components: list[str] = field(default_factory=list)
    reproduction_hints: list[str] = field(default_factory=list)

@dataclass
class LogEvidence:
    key_errors: list[str] = field(default_factory=list)
    stack_traces: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    correlated_deploys: list[str] = field(default_factory=list)
    red_herrings: list[str] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    error_frequency: dict[str, int] = field(default_factory=dict)
    support_tickets: list[str] = field(default_factory=list)

@dataclass
class RepoMap:
    files_found: list[str] = field(default_factory=list)
    suspect_files: list[str] = field(default_factory=list)
    suspect_functions: list[dict[str, Any]] = field(default_factory=list)
    code_snippets: list[dict[str, str]] = field(default_factory=list)
    class_hierarchy: dict[str, list[str]] = field(default_factory=dict)
    imports_map: dict[str, list[str]] = field(default_factory=dict)
    call_graph: list[dict[str, str]] = field(default_factory=list)

@dataclass
class ReproResult:
    script_path: str = ""
    script_content: str = ""
    run_command: str = ""
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    success: bool = False
    explanation: str = ""

@dataclass
class DependencyInfo:
    direct_dependents: list[str] = field(default_factory=list)
    indirect_dependents: list[str] = field(default_factory=list)
    upstream_modules: list[str] = field(default_factory=list)
    test_coverage: list[str] = field(default_factory=list)
    blast_radius: str = ""
    risk_assessment: str = ""

@dataclass
class FixPlan:
    root_cause: str = ""
    confidence: Confidence = Confidence.MEDIUM
    affected_files: list[str] = field(default_factory=list)
    patch_approach: str = ""
    risks: list[str] = field(default_factory=list)
    validation_plan: list[str] = field(default_factory=list)
    regression_checks: list[str] = field(default_factory=list)

@dataclass
class PatchResult:
    patch_diff: str = ""
    patch_file_path: str = ""
    new_tests_content: str = ""
    new_tests_path: str = ""
    patch_applied: bool = False
    tests_pass_after_patch: bool = False
    test_output: str = ""

@dataclass
class ReviewResult:
    repro_assessment: str = ""
    fix_plan_assessment: str = ""
    patch_assessment: str = ""
    edge_cases: list[str] = field(default_factory=list)
    weak_assumptions: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    approved: bool = False
    overall_verdict: str = ""

@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    duration_ms: int = 0

@dataclass
class AgentTrace:
    agent_name: str
    status: AgentStatus = AgentStatus.PENDING
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0
    action: str = ""
    detail: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    error: str = ""
    llm_calls: int = 0

@dataclass
class PipelineState:
    bug_report_path: str = ""
    log_path: str = ""
    repo_path: str = ""
    bug_report_content: str = ""
    log_content: str = ""

    triage: TriageResult | None = None
    log_evidence: LogEvidence | None = None
    repo_map: RepoMap | None = None
    repro: ReproResult | None = None
    dependency_info: DependencyInfo | None = None
    fix_plan: FixPlan | None = None
    patch: PatchResult | None = None
    review: ReviewResult | None = None

    traces: list[AgentTrace] = field(default_factory=list)
    pipeline_started_at: str = ""
    pipeline_finished_at: str = ""

    def add_trace(self, trace: AgentTrace) -> None:
        self.traces.append(trace)
