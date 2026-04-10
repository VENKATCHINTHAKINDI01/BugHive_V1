"""BugHive v2 — Log Analyst Agent (LLM-backed)."""
from __future__ import annotations
import re
from bughive.core.base_agent import BaseAgent
from bughive.core.models import PipelineState, LogEvidence
from bughive.tools.log_parser import extract_stack_traces, extract_log_entries, extract_error_signatures
from bughive.tools.search import grep_search

class LogAnalystAgent(BaseAgent):
    @property
    def name(self): return "LogAnalystAgent"
    @property
    def description(self): return "Analyze logs for evidence, anomalies, and deploy correlation"
    @property
    def system_prompt(self):
        return """You are a log analysis expert investigating a software bug.
Given log data and a bug summary, analyze the logs and return a JSON object:
{
  "key_errors": ["error finding 1", "error finding 2"],
  "anomalies": ["anomaly 1", "anomaly 2"],
  "red_herrings": ["unrelated error 1", "unrelated noise 2"],
  "deploy_correlation": ["deploy info relevant to the bug"],
  "support_tickets": ["ticket summaries"],
  "error_frequency": {"metric_name": count},
  "timeline_summary": "chronological summary of events"
}
Focus on errors relevant to the reported bug. Identify and separate red herrings (unrelated errors).
Return ONLY valid JSON."""

    def _execute(self, state: PipelineState) -> PipelineState:
        log_text = state.log_content
        log_path = state.log_path
        evidence = LogEvidence()

        # ── Tool calls (always run — these feed both LLM and fallback) ──
        self.logger.info("Extracting stack traces...")
        traces = extract_stack_traces(log_text)
        evidence.stack_traces = traces
        self.record_tool_call("extract_stack_traces", {}, f"{len(traces)} traces")

        self.logger.info("Extracting error signatures...")
        err_sigs = extract_error_signatures(log_text)
        self.record_tool_call("extract_error_signatures", {}, f"{len(err_sigs)} signatures")

        self.logger.info("Searching for tax-related entries...")
        tax_matches = grep_search(r"[Tt]ax.*(calculation|base)", log_path, context_lines=1)
        self.record_tool_call("grep_search", {"pattern": "tax.*(calculation|base)"}, f"{len(tax_matches)} matches")

        self.logger.info("Searching for deploy info...")
        deploy_matches = grep_search(r"deploy|changelog|v2\.14", log_path)
        self.record_tool_call("grep_search", {"pattern": "deploy|changelog"}, f"{len(deploy_matches)} matches")

        warn_entries = extract_log_entries(log_text, level="WARN")
        error_entries = extract_log_entries(log_text, level="ERROR")
        self.record_tool_call("extract_log_entries", {"level": "WARN"}, f"{len(warn_entries)} entries")
        self.record_tool_call("extract_log_entries", {"level": "ERROR"}, f"{len(error_entries)} entries")

        if self.llm.is_available:
            self.logger.info("Using LLM to analyze log evidence...")
            triage_summary = state.triage.summary if state.triage else "Unknown bug"
            tool_data = (
                f"BUG SUMMARY: {triage_summary}\n\n"
                f"STACK TRACES ({len(traces)}):\n" + "\n---\n".join(traces[:5]) + "\n\n"
                f"ERROR SIGNATURES:\n" + "\n".join(f"  {s['exception_type']}: {s['message']} (x{s['count']})" for s in err_sigs) + "\n\n"
                f"TAX-RELATED LOG ENTRIES:\n" + "\n".join(m.get("match_block", "")[:200] for m in tax_matches[:10]) + "\n\n"
                f"DEPLOY INFO:\n" + "\n".join(m.get("match_block", "")[:200] for m in deploy_matches[:5]) + "\n\n"
                f"WARN ENTRIES (sample):\n" + "\n".join(f"  [{e['logger']}] {e['message'][:100]}" for e in warn_entries[:15]) + "\n\n"
                f"ERROR ENTRIES (sample):\n" + "\n".join(f"  [{e['logger']}] {e['message'][:100]}" for e in error_entries[:10])
            )
            data = self.ask_llm_json(f"Analyze these log findings:\n\n{tool_data}")
            self.record_tool_call("llm_chat", {"task": "log_analysis"}, f"Got {len(data)} keys")

            evidence.key_errors = data.get("key_errors", [])
            evidence.anomalies = data.get("anomalies", [])
            evidence.red_herrings = data.get("red_herrings", [])
            evidence.support_tickets = data.get("support_tickets", [])
            evidence.error_frequency = data.get("error_frequency", {})
            for d in data.get("deploy_correlation", []):
                evidence.correlated_deploys.append(d)
        else:
            self.logger.info("FALLBACK: Using deterministic log analysis...")
            self._fallback_analyze(evidence, log_text, log_path, tax_matches, deploy_matches, warn_entries, error_entries)

        # Log findings
        for e in evidence.key_errors: self.logger.info(f"  KEY ERROR: {e}")
        for a in evidence.anomalies: self.logger.info(f"  Anomaly: {a}")
        for r in evidence.red_herrings: self.logger.info(f"  Red herring: {r}")
        self.logger.info(f"  Frequency: {evidence.error_frequency}")

        state.log_evidence = evidence
        self.set_trace_detail("analyze_logs",
            f"{len(evidence.key_errors)} key errors, {len(evidence.anomalies)} anomalies, "
            f"{len(evidence.red_herrings)} red herrings filtered")
        return state

    def _fallback_analyze(self, evidence, log_text, log_path, tax_matches, deploy_matches, warn_entries, error_entries):
        for m in tax_matches:
            block = m.get("match_block", "")
            base_m = re.search(r"tax_base=([\d.]+)", block)
            sub_m = re.search(r"subtotal=([\d.]+)", block)
            if base_m and sub_m and base_m.group(1) == sub_m.group(1):
                evidence.key_errors.append(f"Tax base ({base_m.group(1)}) equals original subtotal — discount NOT applied before tax")

        for m in deploy_matches:
            block = m.get("match_block", "")
            if "changelog" in block.lower() or "v2.14" in block:
                evidence.correlated_deploys.append(block.strip()[:200])

        tax_warnings = [e for e in warn_entries if "tax" in e["message"].lower()]
        evidence.anomalies.append(f"{len(tax_warnings)} WARN-level tax entries show tax_base = pre-discount subtotal")
        support = [e for e in warn_entries if "support.ticket" in e["logger"]]
        if support:
            evidence.anomalies.append(f"{len(support)} customer tickets about incorrect tax")
            evidence.support_tickets = [e["message"] for e in support]

        if any("smtp" in e["message"].lower() or "email" in e["logger"] for e in error_entries):
            evidence.red_herrings.append("SMTP/email failures — unrelated to calculation")
        if any("db.pool" in e["logger"] for e in warn_entries):
            evidence.red_herrings.append("Database pool warnings — unrelated to tax calculation")
        if any("cache" in e["logger"] for e in warn_entries):
            evidence.red_herrings.append("Redis cache misses — unrelated")
        if any("ratelimit" in e["logger"] for e in warn_entries):
            evidence.red_herrings.append("Rate limiting warnings — unrelated")

        evidence.error_frequency = {
            "tax_warnings": len(tax_warnings), "customer_complaints": len(support),
            "total_orders": len(extract_log_entries(log_text, logger_filter="orders.processor", message_filter="total calculated")),
        }
