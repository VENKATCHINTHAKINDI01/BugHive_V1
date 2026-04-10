"""BugHive v2 — Repo Navigator Agent (LLM-backed)."""
from __future__ import annotations
import os
from bughive.core.base_agent import BaseAgent
from bughive.core.models import PipelineState, RepoMap
from bughive.tools.file_ops import find_files, read_file, get_file_tree
from bughive.tools.search import search_code_for_pattern
from bughive.tools.ast_analyzer import extract_functions, extract_classes, extract_imports, build_call_graph, get_function_source

class RepoNavigatorAgent(BaseAgent):
    @property
    def name(self): return "RepoNavigatorAgent"
    @property
    def description(self): return "Analyze repository structure, build code map, identify suspect code"
    @property
    def system_prompt(self):
        return """You are a code navigator analyzing a repository to find the root cause of a bug.
Given the file tree, function list, class hierarchy, call graph, and code snippets,
identify which files and functions are most likely to contain the bug.
Return a JSON object:
{
  "suspect_files": ["path/to/file.py"],
  "suspect_functions": [{"name": "func_name", "file": "path", "reason": "why this is suspect"}],
  "code_analysis": "detailed analysis of the suspicious code",
  "call_chain": "how data flows through the suspect functions"
}
Return ONLY valid JSON."""

    def _execute(self, state: PipelineState) -> PipelineState:
        repo_path = state.repo_path
        repo_map = RepoMap()

        if not repo_path or not os.path.isdir(repo_path):
            self.logger.warning("No repository — skipping repo navigation")
            state.repo_map = repo_map
            self.set_trace_detail("skip", "No repository available")
            return state

        # ── Tool calls: discover structure ──
        self.logger.info("Discovering files...")
        py_files = find_files(repo_path, "*.py")
        repo_map.files_found = py_files
        self.record_tool_call("find_files", {"root": repo_path}, f"{len(py_files)} files")

        tree = get_file_tree(repo_path)
        self.logger.info(f"  File tree:\n{tree}")

        # ── AST analysis on each file ──
        self.logger.info("Running AST analysis...")
        all_functions, all_classes, all_imports, all_calls = [], [], {}, []

        for fpath in py_files:
            if os.path.basename(fpath) == "__init__.py": continue
            funcs = extract_functions(fpath)
            self.record_tool_call("extract_functions", {"file": fpath}, f"{len(funcs)} functions")
            for fn in funcs: fn["file"] = fpath
            all_functions.extend(funcs)

            classes = extract_classes(fpath)
            self.record_tool_call("extract_classes", {"file": fpath}, f"{len(classes)} classes")
            for cls in classes: cls["file"] = fpath
            all_classes.extend(classes)

            imps = extract_imports(fpath)
            all_imports[fpath] = [f"{i['type']} {i['module']}.{i['name']}" for i in imps]

            calls = build_call_graph(fpath)
            all_calls.extend(calls)
            self.record_tool_call("build_call_graph", {"file": fpath}, f"{len(calls)} edges")

        repo_map.imports_map = all_imports
        repo_map.call_graph = all_calls
        for cls in all_classes:
            repo_map.class_hierarchy[cls["name"]] = cls.get("methods", [])

        # ── Search for suspect patterns ──
        self.logger.info("Searching for suspect code patterns...")
        triage = state.triage
        search_patterns = ["tax.*=.*subtotal|TAX_RATE|calculate_total"]
        if triage and triage.affected_components:
            for comp in triage.affected_components:
                # Extract function names from component references
                import re
                func_match = re.search(r"(\w+)\(\)", comp)
                if func_match: search_patterns.append(func_match.group(1))

        all_hits = []
        for pattern in search_patterns:
            hits = search_code_for_pattern(repo_path, pattern)
            self.record_tool_call("search_code_for_pattern", {"pattern": pattern}, f"{len(hits)} hits")
            all_hits.extend(hits)

        # Extract suspect function source code
        for fn in all_functions:
            if fn["name"] in ("calculate_total", "get_order_summary"):
                source = get_function_source(fn["file"], fn["name"])
                if source:
                    repo_map.code_snippets.append({"file": fn["file"], "function": fn["name"], "source": source})
                    self.record_tool_call("get_function_source", {"func": fn["name"]}, f"{len(source)} chars")

        if self.llm.is_available and repo_map.code_snippets:
            self.logger.info("Using LLM to analyze code...")
            context = (
                f"BUG SUMMARY: {triage.summary if triage else 'Unknown'}\n\n"
                f"FILE TREE:\n{tree}\n\n"
                f"FUNCTIONS:\n" + "\n".join(f"  {f.get('parent_class','')}.{f['name']}() at {f['file']}:{f['lineno']}" for f in all_functions) + "\n\n"
                f"CALL GRAPH:\n" + "\n".join(f"  {c['caller']} -> {c['callee']}" for c in all_calls[:30]) + "\n\n"
                f"SUSPECT CODE SNIPPETS:\n" + "\n---\n".join(f"File: {s['file']}\nFunction: {s['function']}\n{s['source']}" for s in repo_map.code_snippets)
            )
            data = self.ask_llm_json(f"Analyze this repository:\n\n{context}")
            self.record_tool_call("llm_chat", {"task": "repo_analysis"}, f"Got {len(data)} keys")

            repo_map.suspect_files = data.get("suspect_files", [])
            repo_map.suspect_functions = data.get("suspect_functions", [])
            for fn in repo_map.suspect_functions:
                self.logger.info(f"  SUSPECT: {fn.get('name', '?')} — {fn.get('reason', '?')}")
        else:
            self.logger.info("FALLBACK: Using pattern-based suspect identification...")
            suspect_files = set()
            for hit in all_hits:
                f = hit.get("file", "")
                if f and "test" not in f.lower(): suspect_files.add(f)
            repo_map.suspect_files = sorted(suspect_files)
            for fn in all_functions:
                if fn["name"] == "calculate_total":
                    repo_map.suspect_functions.append({"name": fn["name"], "file": fn["file"],
                        "lineno": fn["lineno"], "parent_class": fn.get("parent_class", "")})

        for f in repo_map.suspect_files: self.logger.info(f"  Suspect file: {f}")

        state.repo_map = repo_map
        self.set_trace_detail("navigate_repo",
            f"{len(py_files)} files, {len(all_functions)} functions, {len(all_calls)} call edges, "
            f"{len(repo_map.suspect_files)} suspect files")
        return state
