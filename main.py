#!/usr/bin/env python3
"""BugHive v2 — CLI Entry Point."""
import argparse, os, sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from bughive.core.config import load_config
from bughive.core.logger import setup_logging
from bughive.orchestrator import Orchestrator

def main():
    parser = argparse.ArgumentParser(description="BugHive v2 — Multi-Agent Bug Investigation System")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--report", default=None, help="Path to bug report")
    parser.add_argument("--logs", default=None, help="Path to log file")
    parser.add_argument("--repo", default=None, help="Path to repository")
    args = parser.parse_args()

    config = load_config(config_path=args.config, project_root=PROJECT_ROOT)
    setup_logging(config)

    report = args.report or os.path.join(PROJECT_ROOT, config.inputs.bug_report)
    logs = args.logs or os.path.join(PROJECT_ROOT, config.inputs.log_file)
    repo = args.repo or os.path.join(PROJECT_ROOT, config.inputs.repo_path)
    for p in [report, logs]:
        if not os.path.isabs(p): p = os.path.join(PROJECT_ROOT, p)
    if not os.path.isabs(report): report = os.path.join(PROJECT_ROOT, report)
    if not os.path.isabs(logs): logs = os.path.join(PROJECT_ROOT, logs)
    if not os.path.isabs(repo): repo = os.path.join(PROJECT_ROOT, repo)

    if not os.path.exists(report): print(f"Error: {report} not found"); sys.exit(1)
    if not os.path.exists(logs): print(f"Error: {logs} not found"); sys.exit(1)
    if not os.path.isdir(repo): print(f"Warning: {repo} not found — report-only mode"); repo = None

    Orchestrator(config).run_pipeline(report, logs, repo)

if __name__ == "__main__":
    main()
