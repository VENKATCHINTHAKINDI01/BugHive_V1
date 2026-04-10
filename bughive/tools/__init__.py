"""BugHive v2 — Tool Registry."""
from bughive.tools.search import grep_search, search_code_for_pattern
from bughive.tools.log_parser import extract_stack_traces, extract_log_entries, extract_error_signatures
from bughive.tools.file_ops import find_files, read_file, write_file, get_file_tree
from bughive.tools.runner import run_script, run_pytest
from bughive.tools.ast_analyzer import extract_functions, extract_classes, extract_imports, build_call_graph, get_function_source
from bughive.tools.diff_generator import generate_unified_diff, generate_patch_file
