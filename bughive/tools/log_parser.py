"""Log parser tools."""
import re

LOG_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\s+\[(\w+)\]\s+([\w.]+)\s+-\s+(.*)$")
STACK_TRACE_RE = re.compile(r"(Traceback \(most recent call last\):.*?)(?=\n\d{4}-|\n\[|\Z)", re.DOTALL)

def parse_log_line(line):
    m = LOG_LINE_RE.match(line)
    return {"timestamp": m.group(1), "level": m.group(2), "logger": m.group(3), "message": m.group(4)} if m else None

def extract_log_entries(log_text, level=None, logger_filter=None, message_filter=None):
    entries = []
    msg_re = re.compile(message_filter, re.IGNORECASE) if message_filter else None
    for line in log_text.splitlines():
        entry = parse_log_line(line)
        if not entry: continue
        if level and entry["level"].upper() != level.upper(): continue
        if logger_filter and logger_filter.lower() not in entry["logger"].lower(): continue
        if msg_re and not msg_re.search(entry["message"]): continue
        entries.append(entry)
    return entries

def extract_stack_traces(log_text):
    return [m.group(1).strip() for m in STACK_TRACE_RE.finditer(log_text)]

def extract_error_signatures(log_text):
    pat = re.compile(r"^(\w+(?:\.\w+)*(?:Error|Exception))\s*:\s*(.+)$", re.MULTILINE)
    counts = {}
    for m in pat.finditer(log_text):
        key = f"{m.group(1)}: {m.group(2).strip()}"
        if key not in counts: counts[key] = {"exception_type": m.group(1), "message": m.group(2).strip(), "count": 0}
        counts[key]["count"] += 1
    return list(counts.values())
