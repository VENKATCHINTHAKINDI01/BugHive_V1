"""File operations tools."""
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", ".pytest_cache"}

def find_files(root_dir, pattern="*.py", exclude_dirs=None):
    if exclude_dirs is None: exclude_dirs = SKIP_DIRS
    return [str(f) for f in sorted(Path(root_dir).rglob(pattern)) if not any(p in exclude_dirs for p in f.parts)]

def read_file(filepath, max_lines=None):
    p = Path(filepath)
    if not p.exists(): raise FileNotFoundError(f"Not found: {filepath}")
    text = p.read_text(errors="replace")
    return "\n".join(text.splitlines()[:max_lines]) if max_lines else text

def write_file(filepath, content):
    p = Path(filepath); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
    return str(p.resolve())

def get_file_tree(root_dir, max_depth=3):
    lines = [Path(root_dir).name + "/"]
    def walk(d, prefix, depth):
        if depth > max_depth: return
        entries = sorted(d.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        entries = [e for e in entries if e.name not in SKIP_DIRS and not e.name.startswith(".")]
        for i, entry in enumerate(entries):
            last = i == len(entries) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{entry.name}")
            if entry.is_dir(): walk(entry, prefix + ("    " if last else "│   "), depth + 1)
    walk(Path(root_dir), "", 1)
    return "\n".join(lines)
