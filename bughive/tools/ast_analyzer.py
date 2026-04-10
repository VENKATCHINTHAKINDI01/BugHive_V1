"""AST analysis tools."""
import ast
from pathlib import Path

def extract_functions(filepath):
    source = Path(filepath).read_text(errors="replace")
    try: tree = ast.parse(source, filename=filepath)
    except SyntaxError: return []
    return [{"name": n.name, "lineno": n.lineno, "end_lineno": getattr(n, "end_lineno", n.lineno),
             "args": [a.arg for a in n.args.args if a.arg != "self"],
             "docstring": (ast.get_docstring(n) or "")[:200], "parent_class": _get_parent_class(tree, n)}
            for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

def extract_classes(filepath):
    source = Path(filepath).read_text(errors="replace")
    try: tree = ast.parse(source, filename=filepath)
    except SyntaxError: return []
    return [{"name": n.name, "lineno": n.lineno, "bases": [b.id if isinstance(b, ast.Name) else "" for b in n.bases],
             "methods": [m.name for m in n.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]}
            for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

def extract_imports(filepath):
    source = Path(filepath).read_text(errors="replace")
    try: tree = ast.parse(source, filename=filepath)
    except SyntaxError: return []
    imports = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names: imports.append({"module": a.name, "name": a.name, "type": "import"})
        elif isinstance(n, ast.ImportFrom):
            for a in n.names: imports.append({"module": n.module or "", "name": a.name, "type": "from"})
    return imports

def build_call_graph(filepath):
    source = Path(filepath).read_text(errors="replace")
    try: tree = ast.parse(source, filename=filepath)
    except SyntaxError: return []
    calls = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            caller = n.name; pc = _get_parent_class(tree, n)
            if pc: caller = f"{pc}.{n.name}"
            for child in ast.walk(n):
                if isinstance(child, ast.Call):
                    callee = _get_call_name(child)
                    if callee: calls.append({"caller": caller, "callee": callee, "lineno": child.lineno})
    return calls

def get_function_source(filepath, function_name):
    lines = Path(filepath).read_text(errors="replace").splitlines()
    try: tree = ast.parse("\n".join(lines), filename=filepath)
    except SyntaxError: return None
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function_name:
            return "\n".join(lines[n.lineno - 1:getattr(n, "end_lineno", len(lines))])
    return None

def _get_parent_class(tree, func_node):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef):
            for item in n.body:
                if item is func_node: return n.name
    return ""

def _get_call_name(call_node):
    f = call_node.func
    if isinstance(f, ast.Name): return f.id
    if isinstance(f, ast.Attribute):
        if isinstance(f.value, ast.Name): return f"{f.value.id}.{f.attr}"
        return f.attr
    return ""
