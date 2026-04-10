"""BugHive v2 — Configuration Loader."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class InputsConfig:
    bug_report: str = "inputs/bug_report.md"
    log_file: str = "inputs/app.log"
    repo_path: str = "sample_repo"

@dataclass
class OutputsConfig:
    dir: str = "outputs"
    report_file: str = "bughive_report.json"
    repro_script: str = "repro_test.py"
    patch_file: str = "fix.patch"
    trace_file: str = "trace.log"

@dataclass
class PipelineConfig:
    agents: list[str] = field(default_factory=lambda: [
        "triage", "log_analyst", "repo_navigator", "reproducer",
        "dependency_analyst", "fix_planner", "patch_generator", "reviewer",
    ])
    max_retries: int = 2
    agent_timeout: int = 120
    fail_fast: bool = False

@dataclass
class LLMConfig:
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    max_tokens: int = 4096
    temperature: float = 0.0
    api_key: str = ""  # Loaded from env var, NEVER hardcoded

@dataclass
class LoggingConfig:
    level: str = "INFO"
    console: bool = True
    file: bool = True
    file_path: str = "outputs/trace.log"

@dataclass
class ToolsConfig:
    script_timeout: int = 30
    grep_max_results: int = 50
    grep_context_lines: int = 3

@dataclass
class BugHiveConfig:
    project_name: str = "BugHive"
    version: str = "2.0.0"
    inputs: InputsConfig = field(default_factory=InputsConfig)
    outputs: OutputsConfig = field(default_factory=OutputsConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    project_root: str = ""


def load_config(config_path: str | None = None, project_root: str | None = None) -> BugHiveConfig:
    if project_root is None:
        project_root = os.getcwd()
    config = BugHiveConfig(project_root=project_root)
    if config_path is None:
        config_path = os.path.join(project_root, "config.yaml")

    if os.path.exists(config_path):
        raw_text = Path(config_path).read_text()
        if HAS_YAML:
            raw = yaml.safe_load(raw_text) or {}
        else:
            raw = _simple_yaml_parse(raw_text)

        proj = raw.get("project", {})
        if isinstance(proj, dict):
            config.project_name = proj.get("name", config.project_name)
            config.version = proj.get("version", config.version)
        inp = raw.get("inputs", {})
        if isinstance(inp, dict):
            config.inputs.bug_report = inp.get("bug_report", config.inputs.bug_report)
            config.inputs.log_file = inp.get("log_file", config.inputs.log_file)
            config.inputs.repo_path = inp.get("repo_path", config.inputs.repo_path)
        out = raw.get("outputs", {})
        if isinstance(out, dict):
            for k in ("dir", "report_file", "repro_script", "patch_file", "trace_file"):
                if k in out:
                    setattr(config.outputs, k, out[k])
        pipe = raw.get("pipeline", {})
        if isinstance(pipe, dict):
            agents = pipe.get("agents")
            if isinstance(agents, list) and agents:
                config.pipeline.agents = agents
            if "max_retries" in pipe:
                config.pipeline.max_retries = int(pipe["max_retries"])
            if "fail_fast" in pipe:
                config.pipeline.fail_fast = str(pipe["fail_fast"]).lower() == "true"
        llm = raw.get("llm", {})
        if isinstance(llm, dict):
            config.llm.model = llm.get("model", config.llm.model)
            if "max_tokens" in llm:
                config.llm.max_tokens = int(llm["max_tokens"])
            if "temperature" in llm:
                config.llm.temperature = float(llm["temperature"])
        tools = raw.get("tools", {})
        if isinstance(tools, dict):
            if "script_timeout" in tools:
                config.tools.script_timeout = int(tools["script_timeout"])

    # Load API key from environment — NEVER from config file
    config.llm.api_key = os.environ.get("GROQ_API_KEY", "")
    return config


def _simple_yaml_parse(text: str) -> dict:
    """Minimal YAML parser for flat/one-level configs."""
    result = {}
    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key, val = key.strip(), val.strip().strip("\"'")
            if indent == 0:
                if val:
                    result[key] = val
                else:
                    result[key] = {}
                    section = key
            elif section is not None:
                sec = result.get(section, {})
                if isinstance(sec, dict):
                    sec[key] = val
                    result[section] = sec
        elif stripped.startswith("- ") and section:
            sec = result.get(section, {})
            if isinstance(sec, dict):
                for k in reversed(list(sec.keys())):
                    if isinstance(sec[k], list):
                        sec[k].append(stripped[2:].strip().strip("\"'"))
                        break
                    elif sec[k] == "":
                        sec[k] = [stripped[2:].strip().strip("\"'")]
                        break
                result[section] = sec
    return result
