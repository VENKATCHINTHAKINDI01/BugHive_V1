"""Script and test runner tools."""
import subprocess, re

def run_script(script_path, cwd=None, timeout=30):
    try:
        proc = subprocess.run(["python3", script_path], capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "timed_out": False}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": f"TIMEOUT: {timeout}s", "timed_out": True}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "timed_out": False}

def run_pytest(test_path, cwd=None, timeout=30, extra_args=None):
    cmd = ["python3", "-m", "pytest", test_path, "-v", "--tb=short"]
    if extra_args: cmd.extend(extra_args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        passed = failed = errors = 0
        for line in proc.stdout.splitlines():
            p, f, e = re.search(r"(\d+) passed", line), re.search(r"(\d+) failed", line), re.search(r"(\d+) error", line)
            if p: passed = int(p.group(1))
            if f: failed = int(f.group(1))
            if e: errors = int(e.group(1))
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "passed": passed, "failed": failed, "errors": errors, "timed_out": False}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "TIMEOUT", "passed": 0, "failed": 0, "errors": 0, "timed_out": True}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "passed": 0, "failed": 0, "errors": 0, "timed_out": False}
