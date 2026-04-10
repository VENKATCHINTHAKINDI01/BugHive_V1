"""Search tools."""
import re, subprocess
from pathlib import Path

def grep_search(pattern, filepath, context_lines=3, max_results=50):
    results = []
    try:
        cmd = ["grep", "-n", f"-C{context_lines}", f"-m{max_results}", "-i", "-E", pattern, filepath]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if proc.returncode == 0 and proc.stdout.strip():
            for block in proc.stdout.strip().split("\n--\n"):
                results.append({"match_block": block.strip(), "file": filepath})
            return results[:max_results]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    try:
        lines = Path(filepath).read_text(errors="replace").splitlines()
        compiled = re.compile(pattern, re.IGNORECASE)
        for i, line in enumerate(lines):
            if compiled.search(line):
                s, e = max(0, i - context_lines), min(len(lines), i + context_lines + 1)
                results.append({"match_block": "\n".join(f"{j+1}: {lines[j]}" for j in range(s, e)), "file": filepath, "line": i + 1})
                if len(results) >= max_results: break
    except Exception as ex:
        results.append({"error": str(ex), "file": filepath})
    return results

def search_code_for_pattern(repo_path, pattern, file_glob="*.py", context_lines=3):
    results = []
    for fpath in sorted(Path(repo_path).rglob(file_glob)):
        if any(s in str(fpath) for s in ["__pycache__", ".git", ".venv"]): continue
        results.extend(grep_search(pattern, str(fpath), context_lines=context_lines))
    return results
