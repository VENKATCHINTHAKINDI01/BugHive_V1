"""
BugHive v2 — Streamlit Dashboard.

Industry-grade UI for the Multi-Agent Bug Investigation System.
Run: streamlit run app.py
"""

import streamlit as st
import json
import os
import sys
import time
import threading
import queue
from pathlib import Path
from datetime import datetime, timezone

# Ensure project is importable
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# ============================================================
# Page Config
# ============================================================
st.set_page_config(
    page_title="BugHive — Multi-Agent Bug Investigation",
    page_icon="🐝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Custom CSS
# ============================================================
st.markdown("""
<style>
    /* Global */
    .block-container { padding-top: 2rem; }

    /* Header */
    .bughive-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .bughive-header h1 { color: #f5c542; margin: 0; font-size: 2rem; }
    .bughive-header p { color: #a0aec0; margin: 0.3rem 0 0 0; font-size: 0.95rem; }

    /* Status cards */
    .status-card {
        padding: 1rem 1.2rem;
        border-radius: 10px;
        border-left: 4px solid;
        margin-bottom: 0.8rem;
    }
    .status-pass { background: #f0fdf4; border-color: #22c55e; }
    .status-fail { background: #fef2f2; border-color: #ef4444; }
    .status-warn { background: #fffbeb; border-color: #f59e0b; }
    .status-info { background: #eff6ff; border-color: #3b82f6; }

    /* Agent badge */
    .agent-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 0.4rem;
    }
    .badge-triage { background: #e0f2fe; color: #0369a1; }
    .badge-log { background: #fef3c7; color: #92400e; }
    .badge-repo { background: #ede9fe; color: #6d28d9; }
    .badge-repro { background: #fce7f3; color: #9d174d; }
    .badge-dep { background: #e0e7ff; color: #3730a3; }
    .badge-fix { background: #d1fae5; color: #065f46; }
    .badge-patch { background: #ccfbf1; color: #115e59; }
    .badge-review { background: #fee2e2; color: #991b1b; }

    /* Metric override */
    [data-testid="stMetric"] {
        background: #f8fafc;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 20px;
        border-radius: 8px 8px 0 0;
    }

    /* Code blocks */
    .stCodeBlock { border-radius: 8px; }

    /* Expander */
    .streamlit-expanderHeader { font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Helper Functions
# ============================================================

def load_report(path):
    """Load the JSON report if it exists."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def render_status_card(label, status, detail=""):
    """Render a colored status card."""
    css_class = {
        "pass": "status-pass", "fail": "status-fail",
        "warn": "status-warn", "info": "status-info",
    }.get(status.lower(), "status-info")
    icon = {"pass": "✅", "fail": "❌", "warn": "⚠️", "info": "ℹ️"}.get(status.lower(), "ℹ️")
    st.markdown(f"""
    <div class="status-card {css_class}">
        <strong>{icon} {label}</strong>
        {f'<br><span style="color:#64748b;font-size:0.85rem">{detail}</span>' if detail else ''}
    </div>
    """, unsafe_allow_html=True)


def render_agent_badge(agent_name):
    """Return HTML for an agent badge."""
    badges = {
        "TriageAgent": ("badge-triage", "🔍 Triage"),
        "LogAnalystAgent": ("badge-log", "📋 Log Analyst"),
        "RepoNavigatorAgent": ("badge-repo", "🗂️ Repo Navigator"),
        "ReproductionAgent": ("badge-repro", "🧪 Reproducer"),
        "DependencyAnalystAgent": ("badge-dep", "🔗 Dependencies"),
        "FixPlannerAgent": ("badge-fix", "🔧 Fix Planner"),
        "PatchGeneratorAgent": ("badge-patch", "📝 Patch Gen"),
        "ReviewerCriticAgent": ("badge-review", "🛡️ Reviewer"),
    }
    cls, label = badges.get(agent_name, ("", agent_name))
    return f'<span class="agent-badge {cls}">{label}</span>'


def run_pipeline_with_output(report_path, log_path, repo_path, output_queue):
    """Run the BugHive pipeline in a background thread, capturing output."""
    import io
    import contextlib

    from bughive.core.config import load_config
    from bughive.core.logger import setup_logging
    from bughive.orchestrator import Orchestrator

    config = load_config(project_root=PROJECT_ROOT)
    # Suppress console logging to avoid conflicts with Streamlit
    config.logging.console = False
    config.logging.file = True
    setup_logging(config)

    orchestrator = Orchestrator(config)

    # Capture stdout
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        try:
            state, output_path = orchestrator.run_pipeline(report_path, log_path, repo_path)
            output_queue.put(("success", output_path, state))
        except Exception as e:
            output_queue.put(("error", str(e), None))


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:
    st.markdown("## 🐝 BugHive")
    st.caption("Multi-Agent Bug Investigation System v2.0")
    st.divider()

    # Navigation
    page = st.radio(
        "Navigation",
        ["🚀 Run Investigation", "📊 Dashboard", "📄 Report Viewer"],
        label_visibility="collapsed",
    )

    st.divider()

    # Configuration
    st.markdown("### ⚙️ Configuration")

    groq_key = st.text_input(
        "Groq API Key",
        value=os.environ.get("GROQ_API_KEY", ""),
        type="password",
        help="Get a free key at console.groq.com/keys",
    )
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key

    llm_mode = "🟢 LLM Mode (Groq)" if groq_key else "🟡 Fallback Mode"
    st.info(llm_mode)

    model = st.selectbox(
        "Model",
        ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama-3.1-8b-instant"],
        index=0,
    )

    st.divider()
    st.markdown(
        "**Powered by**  \n"
        "Groq LPU + Llama 3.3 70B  \n"
        "8 Specialized Agents  \n"
        "8 Programmatic Tools"
    )


# ============================================================
# Page: Run Investigation
# ============================================================

if page == "🚀 Run Investigation":

    # Header
    st.markdown("""
    <div class="bughive-header">
        <h1>🐝 BugHive Investigation</h1>
        <p>Upload a bug report and logs to start the multi-agent investigation pipeline</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📝 Bug Report")
        upload_report = st.file_uploader(
            "Upload bug report (.md or .txt)",
            type=["md", "txt"],
            key="report_upload",
        )
        use_sample_report = st.checkbox("Use included sample", value=True, key="sample_report")

    with col2:
        st.markdown("#### 📋 Log File")
        upload_log = st.file_uploader(
            "Upload log file (.log or .txt)",
            type=["log", "txt"],
            key="log_upload",
        )
        use_sample_log = st.checkbox("Use included sample", value=True, key="sample_log")

    st.markdown("#### 📁 Repository Path")
    repo_col1, repo_col2 = st.columns([3, 1])
    with repo_col1:
        repo_input = st.text_input(
            "Path to repository (optional)",
            value=os.path.join(PROJECT_ROOT, "sample_repo"),
            help="Local path to the codebase. Leave as-is for the included sample.",
        )
    with repo_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        use_sample_repo = st.checkbox("Use sample repo", value=True, key="sample_repo")

    st.divider()

    # Resolve inputs
    default_report = os.path.join(PROJECT_ROOT, "inputs", "bug_report.md")
    default_log = os.path.join(PROJECT_ROOT, "inputs", "app.log")
    default_repo = os.path.join(PROJECT_ROOT, "sample_repo")

    if use_sample_report:
        report_path = default_report
    elif upload_report:
        temp_report = os.path.join(PROJECT_ROOT, "outputs", "uploaded_report.md")
        Path(temp_report).write_bytes(upload_report.read())
        report_path = temp_report
    else:
        report_path = default_report

    if use_sample_log:
        log_path = default_log
    elif upload_log:
        temp_log = os.path.join(PROJECT_ROOT, "outputs", "uploaded_log.log")
        Path(temp_log).write_bytes(upload_log.read())
        log_path = temp_log
    else:
        log_path = default_log

    repo_path = default_repo if use_sample_repo else (repo_input if repo_input else None)

    # Preview inputs
    with st.expander("👁️ Preview Inputs", expanded=False):
        preview_tab1, preview_tab2 = st.tabs(["Bug Report", "Logs"])
        with preview_tab1:
            if os.path.exists(report_path):
                st.markdown(Path(report_path).read_text())
        with preview_tab2:
            if os.path.exists(log_path):
                st.code(Path(log_path).read_text()[:3000], language="log")

    # Run button
    st.markdown("")
    run_button = st.button(
        "🐝  Run BugHive Investigation",
        type="primary",
        use_container_width=True,
    )

    if run_button:
        if not os.path.exists(report_path):
            st.error(f"Bug report not found: {report_path}")
        elif not os.path.exists(log_path):
            st.error(f"Log file not found: {log_path}")
        else:
            # Run pipeline with progress
            from bughive.core.config import load_config
            from bughive.core.logger import setup_logging
            from bughive.orchestrator import Orchestrator
            from bughive.core.models import AgentStatus

            config = load_config(project_root=PROJECT_ROOT)
            config.logging.console = False
            if groq_key:
                config.llm.api_key = groq_key
                config.llm.model = model
            setup_logging(config)

            orchestrator = Orchestrator(config)

            agent_names = [a.name for a in orchestrator.agents]
            total_agents = len(agent_names)

            # Create pipeline state
            from bughive.core.models import PipelineState
            state = PipelineState(
                bug_report_path=report_path, log_path=log_path,
                repo_path=repo_path or "",
                pipeline_started_at=datetime.now(timezone.utc).isoformat(),
            )
            with open(report_path) as f:
                state.bug_report_content = f.read()
            with open(log_path) as f:
                state.log_content = f.read()

            progress_bar = st.progress(0, text="Starting investigation...")
            status_container = st.container()

            # Run each agent with live status updates
            start_time = time.time()
            agent_results = []

            for i, agent in enumerate(orchestrator.agents):
                progress = (i) / total_agents
                progress_bar.progress(progress, text=f"Step {i+1}/{total_agents}: {agent.name}...")

                with status_container:
                    st.markdown(f"{render_agent_badge(agent.name)} Running...", unsafe_allow_html=True)

                state = agent.run(state)

                last_trace = state.traces[-1] if state.traces else None
                status = "✅" if last_trace and last_trace.status == AgentStatus.SUCCESS else "❌"
                detail = last_trace.detail if last_trace else ""
                duration = last_trace.duration_ms if last_trace else 0

                agent_results.append({
                    "name": agent.name,
                    "status": status,
                    "detail": detail[:80],
                    "duration_ms": duration,
                    "llm_calls": last_trace.llm_calls if last_trace else 0,
                })

            progress_bar.progress(1.0, text="Investigation complete!")

            elapsed = int((time.time() - start_time) * 1000)
            state.pipeline_finished_at = datetime.now(timezone.utc).isoformat()

            # Generate output
            output_path = orchestrator._generate_output(state)

            # Save state to session for dashboard
            st.session_state["report_path"] = output_path
            st.session_state["agent_results"] = agent_results
            st.session_state["elapsed_ms"] = elapsed
            st.session_state["state"] = state

            # Show results
            st.divider()
            st.markdown("### 🏁 Investigation Complete")

            # Metrics row
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                bug_confirmed = state.repro.success if state.repro else False
                st.metric("Bug Confirmed", "Yes ✅" if bug_confirmed else "No ❌")
            with m2:
                confidence = state.fix_plan.confidence.value if state.fix_plan else "N/A"
                st.metric("Root Cause", confidence.upper())
            with m3:
                tests_pass = state.patch.tests_pass_after_patch if state.patch else False
                st.metric("Patch Tests", "Pass ✅" if tests_pass else "Incomplete ⚠️")
            with m4:
                approved = state.review.approved if state.review else False
                st.metric("Review", "Approved ✅" if approved else "Needs Review ⚠️")

            st.markdown(f"**Duration:** {elapsed}ms | **Mode:** {'LLM' if groq_key else 'Fallback'}")

            # Agent results table
            st.markdown("#### Agent Execution Summary")
            for r in agent_results:
                col_a, col_b, col_c = st.columns([3, 5, 2])
                with col_a:
                    st.markdown(f"{r['status']} **{r['name']}**")
                with col_b:
                    st.caption(r['detail'])
                with col_c:
                    llm_tag = f" | {r['llm_calls']} LLM" if r['llm_calls'] else ""
                    st.caption(f"{r['duration_ms']}ms{llm_tag}")

            st.success(f"📄 Report saved: `{output_path}`")
            st.info("Switch to **📊 Dashboard** or **📄 Report Viewer** to explore results.")


# ============================================================
# Page: Dashboard
# ============================================================

elif page == "📊 Dashboard":

    st.markdown("""
    <div class="bughive-header">
        <h1>🐝 Investigation Dashboard</h1>
        <p>Visual overview of the latest bug investigation results</p>
    </div>
    """, unsafe_allow_html=True)

    # Load latest report
    report_path = st.session_state.get(
        "report_path",
        os.path.join(PROJECT_ROOT, "outputs", "bughive_report.json"),
    )
    report = load_report(report_path)

    if not report:
        st.warning("No investigation report found. Run an investigation first from the **🚀 Run Investigation** page.")
        st.stop()

    # ── Top Metrics ─────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        bug_confirmed = report.get("reproduction", {}).get("bug_confirmed", False)
        st.metric("Bug Status", "Confirmed 🐛" if bug_confirmed else "Unconfirmed")
    with m2:
        severity = report.get("bug_summary", {}).get("severity", "unknown")
        st.metric("Severity", severity.upper())
    with m3:
        confidence = report.get("root_cause", {}).get("confidence", "unknown")
        st.metric("Confidence", confidence.upper())
    with m4:
        tests_pass = report.get("patch", {}).get("tests_pass", False)
        st.metric("Patch Verified", "Yes ✅" if tests_pass else "No ⚠️")
    with m5:
        approved = report.get("review", {}).get("approved", False)
        st.metric("Verdict", "Approved ✅" if approved else "Review ⚠️")

    st.divider()

    # ── Tabs ────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🔍 Bug Summary", "📋 Evidence", "🧪 Reproduction",
        "🔧 Fix & Patch", "🛡️ Review", "📈 Agent Traces",
    ])

    # ── Tab 1: Bug Summary ──────────────────────────────────
    with tab1:
        summary = report.get("bug_summary", {})
        st.markdown(f"### {summary.get('title', 'Bug Report')}")
        st.markdown(summary.get("summary", ""))

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Symptoms")
            for s in summary.get("symptoms", []):
                st.markdown(f"- {s}")

            st.markdown("#### Affected Components")
            for c in summary.get("affected_components", []):
                st.code(c, language="text")

        with col2:
            st.markdown("#### Hypotheses")
            for i, h in enumerate(summary.get("hypotheses", []), 1):
                st.markdown(f"**{i}.** {h}")

    # ── Tab 2: Evidence ─────────────────────────────────────
    with tab2:
        evidence = report.get("evidence", {})

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🔴 Key Errors")
            for e in evidence.get("key_errors", []):
                render_status_card(e, "fail")

            st.markdown("#### 🟡 Anomalies")
            for a in evidence.get("anomalies", []):
                render_status_card(a, "warn")

        with col2:
            st.markdown("#### 🟢 Red Herrings (Filtered)")
            for r in evidence.get("red_herrings", []):
                render_status_card(r, "info", "Determined to be unrelated")

            st.markdown("#### 📦 Deploy Correlation")
            for d in evidence.get("deploy_correlation", []):
                st.code(d[:300], language="log")

        # Error frequency
        freq = evidence.get("error_frequency", {})
        if freq:
            st.markdown("#### Error Frequency")
            freq_cols = st.columns(len(freq))
            for i, (k, v) in enumerate(freq.items()):
                with freq_cols[i]:
                    st.metric(k.replace("_", " ").title(), v)

    # ── Tab 3: Reproduction ─────────────────────────────────
    with tab3:
        repro = report.get("reproduction", {})

        if repro.get("bug_confirmed"):
            render_status_card("Bug Reproduced Successfully", "pass",
                f"Exit code: {repro.get('exit_code', '?')}")
        else:
            render_status_card("Bug Not Reproduced", "fail",
                repro.get("explanation", ""))

        st.markdown("#### Reproduction Output")
        st.code(repro.get("stdout", "No output"), language="text")

        st.markdown("#### Run Command")
        st.code(repro.get("command", repro.get("run_command", "N/A")), language="bash")

        # Show repro script
        repro_path = repro.get("path", repro.get("repro_artifact_path", ""))
        if repro_path and os.path.exists(repro_path):
            with st.expander("📜 Reproduction Script Source"):
                st.code(Path(repro_path).read_text(), language="python")

    # ── Tab 4: Fix & Patch ──────────────────────────────────
    with tab4:
        root_cause = report.get("root_cause", {})
        patch_plan = report.get("patch_plan", {})
        patch = report.get("patch", {})

        st.markdown("#### Root Cause")
        st.markdown(f"**Confidence:** {root_cause.get('confidence', 'N/A').upper()}")
        st.text(root_cause.get("description", ""))

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Patch Approach")
            st.text(patch_plan.get("approach", ""))

            st.markdown("#### Affected Files")
            for f in patch_plan.get("files", patch_plan.get("affected_files", [])):
                st.code(f, language="text")

        with col2:
            st.markdown("#### Risks")
            for r in patch_plan.get("risks", []):
                render_status_card(r, "warn")

        # Patch diff
        if patch.get("diff"):
            st.markdown("#### Patch Diff")
            st.code(patch["diff"], language="diff")

        # Validation plan
        validation = report.get("validation_plan", {})
        if validation.get("tests") or validation.get("regression"):
            st.markdown("#### Validation Plan")
            val_col1, val_col2 = st.columns(2)
            with val_col1:
                st.markdown("**Tests to Add**")
                for t in validation.get("tests", []):
                    st.markdown(f"- {t}")
            with val_col2:
                st.markdown("**Regression Checks**")
                for r in validation.get("regression", []):
                    st.markdown(f"- {r}")

        # Test results
        if patch.get("tests_pass"):
            render_status_card("All tests pass after patch", "pass")
        elif patch.get("diff"):
            render_status_card("Patch test verification incomplete", "warn")

    # ── Tab 5: Review ───────────────────────────────────────
    with tab5:
        review = report.get("review", {})

        # Verdict banner
        verdict = review.get("verdict", "")
        if review.get("approved"):
            st.success(f"✅ **VERDICT:** {verdict}")
        else:
            st.warning(f"⚠️ **VERDICT:** {verdict}")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Assessments")
            render_status_card("Reproduction", "pass" if "PASS" in review.get("repro", "") else "warn",
                review.get("repro", ""))
            render_status_card("Fix Plan", "pass" if "PASS" in review.get("fix_plan", "") else "warn",
                review.get("fix_plan", ""))
            render_status_card("Patch", "pass" if "PASS" in review.get("patch", "") else "warn",
                review.get("patch", ""))

        with col2:
            st.markdown("#### Edge Cases")
            for ec in review.get("edge_cases", []):
                st.markdown(f"🔲 {ec}")

        st.markdown("#### Weak Assumptions")
        for wa in review.get("weak_assumptions", []):
            render_status_card(wa, "warn")

        st.markdown("#### Improvement Suggestions")
        for s in review.get("suggestions", []):
            st.markdown(f"💡 {s}")

    # ── Tab 6: Agent Traces ─────────────────────────────────
    with tab6:
        traces = report.get("agent_traces", [])

        if not traces:
            st.info("No agent traces available.")
        else:
            for trace in traces:
                agent = trace.get("agent", "Unknown")
                status = trace.get("status", "unknown")
                duration = trace.get("duration_ms", 0)
                llm_calls = trace.get("llm_calls", 0)
                icon = "✅" if status == "success" else "❌"

                with st.expander(
                    f"{icon} {agent} — {duration}ms"
                    + (f" | {llm_calls} LLM calls" if llm_calls else ""),
                    expanded=False,
                ):
                    st.markdown(f"**Action:** {trace.get('action', 'N/A')}")
                    st.markdown(f"**Detail:** {trace.get('detail', 'N/A')}")

                    if trace.get("error"):
                        st.error(f"Error: {trace['error']}")

                    tool_calls = trace.get("tool_calls", [])
                    if tool_calls:
                        st.markdown("**Tool Calls:**")
                        for tc in tool_calls:
                            st.markdown(f"- `{tc.get('tool', '?')}` → {tc.get('result', '')}")

        # Open questions
        questions = report.get("open_questions", [])
        if questions:
            st.divider()
            st.markdown("#### Open Questions")
            for q in questions:
                st.markdown(f"❓ {q}")


# ============================================================
# Page: Report Viewer
# ============================================================

elif page == "📄 Report Viewer":

    st.markdown("""
    <div class="bughive-header">
        <h1>🐝 Report Viewer</h1>
        <p>View and download the raw investigation report and artifacts</p>
    </div>
    """, unsafe_allow_html=True)

    report_path = st.session_state.get(
        "report_path",
        os.path.join(PROJECT_ROOT, "outputs", "bughive_report.json"),
    )

    # Output files
    output_dir = os.path.join(PROJECT_ROOT, "outputs")
    if os.path.isdir(output_dir):
        files = sorted(Path(output_dir).glob("*"))
        files = [f for f in files if f.is_file() and not f.name.startswith("_") and not f.name.startswith("uploaded")]

        st.markdown("#### 📁 Output Artifacts")
        for f in files:
            size = f.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} bytes"
            col1, col2, col3 = st.columns([4, 2, 2])
            with col1:
                st.markdown(f"**{f.name}**")
            with col2:
                st.caption(size_str)
            with col3:
                st.download_button(
                    "⬇️ Download",
                    data=f.read_bytes(),
                    file_name=f.name,
                    key=f"dl_{f.name}",
                )

        st.divider()

        # File viewer
        st.markdown("#### 📖 File Viewer")
        selected_file = st.selectbox(
            "Select file to view",
            [f.name for f in files],
            label_visibility="collapsed",
        )

        if selected_file:
            fpath = os.path.join(output_dir, selected_file)
            content = Path(fpath).read_text(errors="replace")

            if selected_file.endswith(".json"):
                try:
                    parsed = json.loads(content)
                    st.json(parsed)
                except json.JSONDecodeError:
                    st.code(content, language="json")
            elif selected_file.endswith(".py"):
                st.code(content, language="python")
            elif selected_file.endswith(".patch") or selected_file.endswith(".diff"):
                st.code(content, language="diff")
            elif selected_file.endswith(".log"):
                st.code(content[:10000], language="log")
            else:
                st.code(content, language="text")
    else:
        st.warning("No output directory found. Run an investigation first.")
