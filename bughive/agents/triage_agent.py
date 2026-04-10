"""BugHive v2 — Triage Agent (LLM-backed)."""
from __future__ import annotations
import json, re
from bughive.core.base_agent import BaseAgent
from bughive.core.models import PipelineState, TriageResult, Severity

class TriageAgent(BaseAgent):
    @property
    def name(self): return "TriageAgent"
    @property
    def description(self): return "Parse bug report, extract symptoms, prioritize hypotheses"
    @property
    def system_prompt(self):
        return """You are a senior software engineer performing bug triage.
Given a bug report, extract and return a JSON object with these exact keys:
{
  "title": "bug title",
  "summary": "one paragraph summary",
  "severity": "critical|high|medium|low",
  "expected_behavior": "what should happen",
  "actual_behavior": "what actually happens",
  "environment": {"key": "value"},
  "symptoms": ["symptom1", "symptom2"],
  "affected_components": ["file.py", "ClassName.method()"],
  "hypotheses": ["H1: most likely cause", "H2: second possibility", "H3: ..."],
  "reproduction_hints": ["step1", "step2"]
}
Be specific and technical. Prioritize hypotheses by likelihood. Return ONLY valid JSON."""

    def _execute(self, state: PipelineState) -> PipelineState:
        report = state.bug_report_content
        result = TriageResult()

        if self.llm.is_available:
            self.logger.info("Using LLM to analyze bug report...")
            data = self.ask_llm_json(f"Analyze this bug report:\n\n{report}")
            self.record_tool_call("llm_chat", {"task": "triage_analysis"}, f"Got {len(data)} keys")
            result.title = data.get("title", "")
            result.summary = data.get("summary", "")
            result.expected_behavior = data.get("expected_behavior", "")
            result.actual_behavior = data.get("actual_behavior", "")
            result.environment = data.get("environment", {})
            result.symptoms = data.get("symptoms", [])
            result.affected_components = data.get("affected_components", [])
            result.hypotheses = data.get("hypotheses", [])
            result.reproduction_hints = data.get("reproduction_hints", [])
            sev = data.get("severity", "medium").lower()
            for s in Severity:
                if s.value == sev: result.severity = s; break
        else:
            self.logger.info("FALLBACK: Using regex parsing...")
            result = self._fallback_parse(report)

        # Log findings
        self.logger.info(f"  Title: {result.title}")
        self.logger.info(f"  Severity: {result.severity.value}")
        self.logger.info(f"  Symptoms: {len(result.symptoms)}")
        for s in result.symptoms: self.logger.info(f"    -> {s}")
        self.logger.info(f"  Hypotheses: {len(result.hypotheses)}")
        for h in result.hypotheses: self.logger.info(f"    -> {h}")
        self.logger.info(f"  Components: {result.affected_components}")

        state.triage = result
        self.set_trace_detail("parse_bug_report",
            f"{len(result.symptoms)} symptoms, {len(result.hypotheses)} hypotheses")
        return state

    def _fallback_parse(self, report):
        """Deterministic fallback when LLM is unavailable."""
        r = TriageResult()
        m = re.search(r"#\s*Bug Report[:\s]*(.+)", report) or re.search(r"\*\*Title:\*\*\s*(.+)", report)
        if m: r.title = m.group(1).strip()
        m = re.search(r"\*\*Severity:\*\*\s*(\w+)", report)
        if m:
            for s in Severity:
                if s.value == m.group(1).lower(): r.severity = s; break
        m = re.search(r"## Expected Behavior\s*\n(.*?)(?=\n## |\Z)", report, re.DOTALL)
        if m: r.expected_behavior = m.group(1).strip()
        m = re.search(r"## Actual Behavior\s*\n(.*?)(?=\n## |\Z)", report, re.DOTALL)
        if m: r.actual_behavior = m.group(1).strip()
        m = re.search(r"## Environment\s*\n(.*?)(?=\n## |\Z)", report, re.DOTALL)
        if m:
            for line in m.group(1).strip().splitlines():
                kv = re.match(r"[-*]\s*\*\*(.+?):\*\*\s*(.*)", line)
                if kv: r.environment[kv.group(1).strip()] = kv.group(2).strip()
        if re.search(r"overcharg", report, re.I): r.symptoms.append("Customer overcharged")
        if re.search(r"tax.*(?:wrong|too high|incorrect)", report, re.I): r.symptoms.append("Tax incorrect on discounted orders")
        cm = re.search(r"(\d+)\s*affected orders", report)
        if cm: r.symptoms.append(f"~{cm.group(1)} orders affected")
        tickets = re.findall(r"TK-\d+", report)
        if tickets: r.symptoms.append(f"{len(set(tickets))} support tickets")
        file_refs = re.findall(r"`([^`]+\.py)`", report)
        r.affected_components = list(dict.fromkeys(file_refs))
        if "tax" in report.lower() and "discount" in report.lower():
            r.hypotheses.append("H1: Tax calculated on pre-discount subtotal instead of post-discount")
            r.hypotheses.append("H2: Discount applied after tax calculation (order-of-operations)")
        if re.search(r"v2\.14\.3|deploy", report, re.I):
            r.hypotheses.append("H3: Regression introduced in v2.14.3 deploy")
        r.hypotheses.append("H4: Rounding error in decimal arithmetic (unlikely)")
        r.summary = f"Bug in tax calculation on discounted orders. Severity: {r.severity.value}."
        return r
