<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/LLM-Llama%203.3%2070B-orange?logo=meta&logoColor=white" alt="Llama">
  <img src="https://img.shields.io/badge/Inference-Groq%20LPU-green" alt="Groq">
  <img src="https://img.shields.io/badge/UI-Streamlit-red?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Agents-8-purple" alt="Agents">
  <img src="https://img.shields.io/badge/Tools-8-teal" alt="Tools">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

# 🐝 BugHive

**Multi-Agent Bug Investigation System**

BugHive is an automated debugging system that orchestrates **8 specialized AI agents** to investigate bug reports end-to-end. Given a bug report, application logs, and source code, BugHive triages the issue, analyzes logs for evidence, navigates the codebase using AST analysis, generates and executes a minimal reproduction script, assesses blast radius, proposes a root-cause hypothesis with a fix plan, generates a verified code patch with regression tests, and critically reviews the entire investigation.

Each agent is backed by **Llama 3.3 70B** (via Groq's LPU inference engine) for reasoning, with deterministic fallback logic when no API key is available. Agents invoke **real programmatic tools** (grep, subprocess, Python AST, diff generator) — not simulated tool usage.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Agent Roles](#agent-roles)
- [Tool Registry](#tool-registry)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Input Mode](#input-mode)
- [Outputs](#outputs)
- [Structured Report Schema](#structured-report-schema)
- [Traceability](#traceability)
- [Project Structure](#project-structure)
- [How It Works Step by Step](#how-it-works-step-by-step)
- [Design Decisions](#design-decisions)
- [Demo](#demo)

---

## Features

- **8 Specialized Agents** — Each with a defined role, system prompt, and tool access
- **LLM-Backed Reasoning** — Agents use Llama 3.3 70B via Groq for intelligent analysis
- **Deterministic Fallback** — Works without an API key using regex/pattern-based logic
- **Real Tool Execution** — grep search, AST parsing, subprocess runner, diff generator, pytest
- **Minimal Reproduction** — Generates and executes a standalone script that confirms the bug
- **Verified Patch** — Produces a unified diff, applies it to a copy, runs all tests to verify
- **Structured JSON Report** — 16-section investigation report with full traceability
- **Streamlit Dashboard** — Production-grade web UI with live pipeline execution and visual dashboard
- **Config-Driven Pipeline** — YAML configuration for agent order, model, retries, timeouts
- **State Machine Orchestrator** — Explicit agent handoffs with retry logic and fail-fast option
- **Complete Tracing** — Every tool call and LLM invocation logged with duration and results

---

## Architecture

```
                         ┌──────────────────────────┐
                         │       ORCHESTRATOR       │
                         │   (State Machine with    │
                         │    Retry Logic)          │
                         └────────────┬─────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
   ┌───────────┐             ┌──────────────┐            ┌──────────────┐
   │ 1. Triage │             │ 2. Log       │            │ 3. Repo      │
   │   Agent   │             │   Analyst    │            │   Navigator★ │
   └─────┬─────┘             └──────┬───────┘            └──────┬───────┘
         │                          │                           │
         └──────────┬───────────────┘                           │
                    ▼                                           ▼
          ┌──────────────┐                           ┌──────────────┐
          │ 4. Reproducer│                           │ 5. Dependency│
          │    Agent     │                           │   Analyst  ★ │
          └──────┬───────┘                           └──────┬───────┘
                 │                                          │
                 └──────────────┬────────────────────────────┘
                                ▼
                     ┌──────────────┐
                     │ 6. Fix       │
                     │   Planner    │
                     └──────┬───────┘
                            ▼
                     ┌──────────────┐
                     │ 7. Patch     │
                     │   Generator★ │
                     └──────┬───────┘
                            ▼
                     ┌──────────────┐
                     │ 8. Reviewer  │
                     │   / Critic   │
                     └──────┬───────┘
                            ▼
                     ┌──────────────┐
                     │   OUTPUTS    │
                     │  JSON Report │
                     │  Repro Script│
                     │  Patch Diff  │
                     │  New Tests   │
                     │  Trace Log   │
                     └──────────────┘

   ★ = Additional agents beyond the minimum required

   Each agent: System Prompt → LLM Reasoning → Tool Calls → Structured Output
```

### Data Flow

```
Bug Report (MD) ──┐
Log File (TXT) ───┤──→ Orchestrator ──→ Agent 1 ──→ Agent 2 ──→ ... ──→ Agent 8 ──→ JSON Report
Repository (DIR) ──┘         │                                                           │
                             │              Shared PipelineState Object                  │
                             └───────────────────────────────────────────────────────────┘
```

All agents read from and write to a shared `PipelineState` dataclass. The orchestrator manages handoffs sequentially. Each agent adds its results to the state and appends its execution trace.

---

## Agent Roles

| # | Agent | Role | LLM Task | Key Tools Used |
|---|-------|------|----------|----------------|
| 1 | **Triage Agent** | Parse bug report, extract symptoms, rank hypotheses | Analyze report, identify severity and failure surface | Regex parsing |
| 2 | **Log Analyst Agent** | Search logs for evidence, filter red herrings | Correlate errors with bug, identify anomalies | `grep_search`, `extract_stack_traces`, `extract_log_entries` |
| 3 | **Repo Navigator Agent** ★ | Map codebase, build call graph, find suspect code | Analyze AST data, identify buggy functions | `find_files`, `extract_functions`, `build_call_graph`, `get_function_source` |
| 4 | **Reproducer Agent** | Generate and execute minimal reproduction script | Write a standalone script that triggers the bug | `write_file`, `run_script` |
| 5 | **Dependency Analyst Agent** ★ | Assess blast radius, import graph, test coverage gaps | Evaluate impact of bug and proposed fix | `search_code_for_pattern`, `extract_imports`, `find_files` |
| 6 | **Fix Planner Agent** | Propose root cause hypothesis and patch strategy | Synthesize all evidence into a fix plan | References all prior agent outputs |
| 7 | **Patch Generator Agent** ★ | Generate code diff, write regression tests, verify fix | Produce patch and test code | `generate_unified_diff`, `write_file`, `run_pytest` |
| 8 | **Reviewer / Critic Agent** | Challenge assumptions, verify safety, flag edge cases | Skeptically review entire investigation | Reviews all prior agent outputs |

All agents inherit from `BaseAgent` which provides: LLM client access, structured logging, automatic tracing with timing, tool call recording, and error handling.

---

## Tool Registry

| Tool | Module | Description |
|------|--------|-------------|
| `grep_search` | `tools/search.py` | Regex search over files with context lines |
| `search_code_for_pattern` | `tools/search.py` | Search all Python files in a repository |
| `extract_stack_traces` | `tools/log_parser.py` | Extract stack trace blocks from log text |
| `extract_log_entries` | `tools/log_parser.py` | Parse structured log lines with filtering |
| `extract_error_signatures` | `tools/log_parser.py` | Find unique exception types and frequency |
| `find_files` | `tools/file_ops.py` | Recursive file discovery with glob patterns |
| `read_file` / `write_file` | `tools/file_ops.py` | File I/O with directory creation |
| `get_file_tree` | `tools/file_ops.py` | Text representation of directory structure |
| `run_script` | `tools/runner.py` | Execute Python scripts with timeout and capture |
| `run_pytest` | `tools/runner.py` | Run pytest with structured result parsing |
| `extract_functions` | `tools/ast_analyzer.py` | Extract function definitions via Python AST |
| `extract_classes` | `tools/ast_analyzer.py` | Extract class definitions with methods |
| `extract_imports` | `tools/ast_analyzer.py` | Extract all import statements |
| `build_call_graph` | `tools/ast_analyzer.py` | Build function-level call graph |
| `get_function_source` | `tools/ast_analyzer.py` | Extract source code of a specific function |
| `generate_unified_diff` | `tools/diff_generator.py` | Generate unified diff between two strings |
| `generate_patch_file` | `tools/diff_generator.py` | Generate and write a .patch file |

---

## Prerequisites

- **Python 3.10+** (tested on 3.11, 3.12, 3.13)
- **pip** (Python package manager)
- **Groq API Key** (free at [console.groq.com/keys](https://console.groq.com/keys)) — required for LLM mode, optional for fallback mode

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/bughive.git
cd bughive
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv henv
source henv/bin/activate        # macOS/Linux
# henv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `streamlit` — Web UI dashboard
- `pytest` — Test execution (used by Patch Generator agent)

### 4. Set up your Groq API key

```bash
export GROQ_API_KEY=gsk_your_key_here      # macOS/Linux
# set GROQ_API_KEY=gsk_your_key_here       # Windows CMD
# $env:GROQ_API_KEY="gsk_your_key_here"    # Windows PowerShell
```

> **Important:** No space after the `=` sign. The system works without an API key in fallback mode.

---

## Configuration

All settings are in `config.yaml`:

```yaml
llm:
  provider: "groq"
  model: "llama-3.3-70b-versatile"
  max_tokens: 4096
  temperature: 0.0
  # API key from GROQ_API_KEY env var — NEVER hardcoded

pipeline:
  agents:
    - "triage"
    - "log_analyst"
    - "repo_navigator"
    - "reproducer"
    - "dependency_analyst"
    - "fix_planner"
    - "patch_generator"
    - "reviewer"
  max_retries: 2
  fail_fast: false
```

---

## Usage

### CLI Mode (Recommended for Demo)

```bash
# Run with default sample inputs
python main.py

# Run with custom inputs
python main.py --report path/to/bug.md --logs path/to/app.log --repo path/to/repo

# Run without a repository (report + logs only)
python main.py --report bug.md --logs server.log
```

### Streamlit UI (Interactive Dashboard)

```bash
streamlit run app.py
# Opens at http://localhost:8501
```

**UI Pages:**

| Page | Description |
|------|-------------|
| **🚀 Run Investigation** | Upload inputs, configure API key, run pipeline with live progress |
| **📊 Dashboard** | 6-tab visual overview (Summary, Evidence, Reproduction, Fix, Review, Traces) |
| **📄 Report Viewer** | Browse and download all output artifacts with syntax highlighting |

---

## Input Mode

This project uses **Option A: Provided Mini-Repo**.

### Included Sample

| File | Description |
|------|-------------|
| `inputs/bug_report.md` | Tax overcharge bug on discounted orders |
| `inputs/app.log` | Server logs with errors + red herrings (SMTP, DB, Redis) |
| `sample_repo/src/order_processor.py` | Order processing module with intentional bug |
| `sample_repo/tests/test_order_processor.py` | Existing tests that miss the bug |

### The Bug

`OrderProcessor.calculate_total()` computes tax on the **original subtotal** instead of the **discounted subtotal**, overcharging customers by $3.20 on a $200 order with 20% discount.

---

## Outputs

| File | Description |
|------|-------------|
| `outputs/bughive_report.json` | Complete structured investigation report (16 sections) |
| `outputs/repro_test.py` | Runnable reproduction script (exit 1 = bug confirmed) |
| `outputs/fix.patch` | Unified diff patch file |
| `outputs/test_tax_fix_regression.py` | 6 generated regression tests |
| `outputs/trace.log` | Full agent trace log with timestamps |

### Run the Repro Script

```bash
python outputs/repro_test.py
# Exit code 1 → Bug confirmed
# Exit code 0 → Bug fixed
```

---

## Structured Report Schema

The `bughive_report.json` contains 16 sections:

| Section | Contents |
|---------|----------|
| `bughive_version` | System version |
| `generated_at` | ISO timestamp |
| `mode` | "llm" or "fallback" |
| `pipeline` | Start/end timestamps, agents executed |
| `bug_summary` | Title, summary, symptoms, severity, hypotheses, components |
| `evidence` | Key errors, stack traces, anomalies, red herrings, deploy correlation, frequency |
| `repo_analysis` | Files, suspect files, suspect functions, call graph, class hierarchy |
| `reproduction` | Script path, command, exit code, bug confirmed, stdout, explanation |
| `dependency_analysis` | Dependents, upstream modules, blast radius, risk, test coverage |
| `root_cause` | Technical description, confidence level |
| `patch_plan` | Affected files, approach, risks |
| `patch` | Diff, patch file path, tests file path, tests pass (bool) |
| `validation_plan` | Tests to add, regression checks |
| `review` | Assessments, edge cases, assumptions, suggestions, approved, verdict |
| `open_questions` | Unresolved items |
| `agent_traces` | Per-agent: status, action, detail, duration, LLM calls, tool calls, errors |

---

## Traceability

Traces are available in three locations:

| Location | Format | How to Access |
|----------|--------|---------------|
| **Console** | Color-coded ANSI | Watch `python main.py` output — each agent logs its steps |
| **`outputs/trace.log`** | Plain-text timestamped | Open the file — search for `[bughive.AgentName]` |
| **`bughive_report.json`** | Structured JSON | Open the file → `"agent_traces"` array at the bottom |

Each trace entry includes: agent name, status (success/failed), action, detail, duration_ms, llm_calls count, tool_calls array (tool name + result), and error message if any.

---

## Project Structure

```
BugHive/
├── main.py                              # CLI entry point
├── app.py                               # Streamlit web UI (749 lines)
├── config.yaml                          # All configuration
├── requirements.txt                     # Dependencies
├── README.md                            # This file
├── .env.example                         # Environment variable template
├── .gitignore
│
├── bughive/                             # Main package (2,068 lines)
│   ├── __init__.py                      # Package version
│   ├── orchestrator.py                  # State-machine pipeline coordinator
│   │
│   ├── core/                            # Foundation layer
│   │   ├── models.py                    # Dataclass models (PipelineState, etc.)
│   │   ├── config.py                    # YAML config loader
│   │   ├── logger.py                    # Console + file logging
│   │   ├── llm_client.py               # Groq API client (stdlib, no SDK)
│   │   └── base_agent.py               # Abstract BaseAgent with LLM + tracing
│   │
│   ├── agents/                          # 8 LLM-backed agents
│   │   ├── __init__.py                  # Agent registry
│   │   ├── triage_agent.py
│   │   ├── log_analyst_agent.py
│   │   ├── repo_navigator_agent.py      ★ NEW
│   │   ├── reproducer_agent.py
│   │   ├── dependency_analyst_agent.py  ★ NEW
│   │   ├── fix_planner_agent.py
│   │   ├── patch_generator_agent.py     ★ NEW
│   │   └── reviewer_agent.py
│   │
│   └── tools/                           # 8 programmatic tools
│       ├── search.py                    # grep_search, search_code_for_pattern
│       ├── log_parser.py                # extract_stack_traces, extract_log_entries
│       ├── file_ops.py                  # find_files, read_file, write_file
│       ├── runner.py                    # run_script, run_pytest
│       ├── ast_analyzer.py              # AST: functions, classes, imports, call graph
│       └── diff_generator.py            # generate_unified_diff, generate_patch_file
│
├── inputs/                              # Sample inputs
│   ├── bug_report.md
│   └── app.log
│
├── sample_repo/                         # Buggy application (Option A)
│   ├── src/
│   │   └── order_processor.py           # Contains the intentional bug
│   └── tests/
│       └── test_order_processor.py      # Existing tests (miss the bug)
│
└── outputs/                             # Generated after running
    ├── bughive_report.json
    ├── repro_test.py
    ├── fix.patch
    ├── test_tax_fix_regression.py
    └── trace.log
```

---

## How It Works Step by Step

1. **Load Inputs** — Orchestrator reads config, loads bug report and logs into memory, validates repo path.

2. **Triage Agent** — Parses the bug report. Extracts title, severity, symptoms, expected/actual behavior, environment, affected components. Generates ranked hypotheses. Writes to `state.triage`.

3. **Log Analyst Agent** — Calls `extract_stack_traces()` and `grep_search()` on the log file. Identifies tax-related warnings, deploy correlation, customer complaints. Separates real evidence from red herrings (SMTP errors, DB warnings, cache misses). Writes to `state.log_evidence`.

4. **Repo Navigator Agent** — Calls `find_files()`, `extract_functions()`, `extract_classes()`, `build_call_graph()` on all Python files. Identifies suspect files and functions via code pattern search. Extracts source code of suspect functions. Writes to `state.repo_map`.

5. **Reproducer Agent** — Using findings from previous agents, generates a minimal Python script that imports the buggy module, creates test data, and asserts expected vs actual behavior. Executes via `run_script()`. Exit code 1 = bug confirmed. Writes to `state.repro`.

6. **Dependency Analyst Agent** — Searches for files importing the buggy module, finds all callers of the suspect function, checks test coverage of affected code, and computes blast radius. Writes to `state.dependency_info`.

7. **Fix Planner Agent** — Synthesizes all evidence (reproduction + logs + code + dependencies) into a root-cause hypothesis with confidence level, patch approach, risks, validation plan, and regression checks. Writes to `state.fix_plan`.

8. **Patch Generator Agent** — Generates unified diff for the fix and 6 regression tests. Copies the repo, applies the patch, runs all tests (existing + new) via `run_pytest()`. Reports pass/fail. Writes to `state.patch`.

9. **Reviewer / Critic Agent** — Reviews everything: reproduction quality, fix plan safety, patch correctness. Flags edge cases, weak assumptions, improvement suggestions. Issues final verdict: APPROVED / CONDITIONALLY APPROVED / NEEDS REVISION. Writes to `state.review`.

10. **Output Generation** — Orchestrator serializes all results into `outputs/bughive_report.json` (16 sections). Prints summary to console.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Custom framework** (not LangGraph/CrewAI) | Full control over handoffs, state, tracing. No opaque abstractions. |
| **Groq + Llama 3.3 70B** | Open-source model, free tier, fastest inference (300+ tok/s). No vendor lock-in. |
| **stdlib HTTP client** (no SDK) | Zero dependency for API calls. Uses `http.client` with OpenAI-compatible endpoint. |
| **Deterministic fallback** | System works without API key for demos/CI. Fallback uses regex/patterns. |
| **BaseAgent inheritance** | DRY — logging, tracing, timing, LLM access handled once. Agents only implement `_execute()`. |
| **Real tool execution** | Agents call `subprocess.run()`, `ast.parse()`, `grep`. Not simulated. |
| **Config-driven YAML** | Agent order, model, retries configurable without code changes. |
| **env var for API key** | Never hardcoded. 12-factor app principles. |
| **Streamlit for UI** | Industry standard for Python apps. No frontend code. Auto-reloads. |
| **Structured JSON output** | Machine-readable with defined schema. Enables downstream automation. |

---

## Demo

### 1. Run the system end-to-end (CLI)

```bash
export GROQ_API_KEY=gsk_your_key_here
python main.py
```

### 2. The minimal repro failing

```bash
python outputs/repro_test.py
```

Output:
```
BugHive Reproduction Result
  Subtotal:            $200.00
  Discount (20%):      -$40.00
  Discounted Subtotal: $160.00
  Tax (8%):            $16.00     ← Should be $12.80
  Total:               $176.00
  BUG CONFIRMED: Overcharge of $3.20
```

### 3. The structured output

```bash
cat outputs/bughive_report.json | python -m json.tool | head -30
```

### 4. The Streamlit dashboard

```bash
streamlit run app.py
```

---

<p align="center">
  Built with Python · Powered by Llama 3.3 70B on Groq LPU
</p>