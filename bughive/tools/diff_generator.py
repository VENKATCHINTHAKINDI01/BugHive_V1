"""Diff generator tools."""
import difflib
from pathlib import Path

def generate_unified_diff(original, modified, original_path="a/file.py", modified_path="b/file.py", context_lines=3):
    return "".join(difflib.unified_diff(original.splitlines(keepends=True), modified.splitlines(keepends=True),
                                         fromfile=original_path, tofile=modified_path, n=context_lines))

def generate_patch_file(original_filepath, old_text, new_text, output_path):
    original = Path(original_filepath).read_text()
    modified = original.replace(old_text, new_text, 1)
    diff = generate_unified_diff(original, modified, f"a/{Path(original_filepath).name}", f"b/{Path(original_filepath).name}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(diff)
    return diff
