"""BugHive v2 — Logging Setup."""
from __future__ import annotations
import logging, os, sys
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bughive.core.config import BugHiveConfig

class Colors:
    RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
    RED="\033[31m"; GREEN="\033[32m"; YELLOW="\033[33m"
    BLUE="\033[34m"; MAGENTA="\033[35m"; CYAN="\033[36m"; WHITE="\033[37m"
    AGENT_COLORS = {
        "TriageAgent": "\033[36m", "LogAnalystAgent": "\033[33m",
        "RepoNavigatorAgent": "\033[34m", "ReproductionAgent": "\033[35m",
        "DependencyAnalystAgent": "\033[34m", "FixPlannerAgent": "\033[32m",
        "PatchGeneratorAgent": "\033[32m", "ReviewerCriticAgent": "\033[31m",
        "Orchestrator": "\033[37m", "LLMClient": "\033[36m",
    }
    @classmethod
    def for_agent(cls, name): return cls.AGENT_COLORS.get(name, cls.WHITE)

class ConsoleFormatter(logging.Formatter):
    LEVEL_COLORS = {logging.DEBUG: Colors.DIM, logging.INFO: Colors.GREEN,
                    logging.WARNING: Colors.YELLOW, logging.ERROR: Colors.RED}
    def format(self, record):
        ts = self.formatTime(record, "%H:%M:%S")
        lc = self.LEVEL_COLORS.get(record.levelno, "")
        ac = Colors.for_agent(record.name.replace("bughive.", ""))
        name = record.name.replace("bughive.", "")
        return (f"{Colors.DIM}{ts}{Colors.RESET} {lc}{record.levelname:<5}{Colors.RESET} "
                f"{ac}{Colors.BOLD}{name:<26}{Colors.RESET} {record.getMessage()}")

class FileFormatter(logging.Formatter):
    def format(self, record):
        ts = self.formatTime(record, "%Y-%m-%dT%H:%M:%S")
        return f"{ts} [{record.name:<40}] {record.levelname:<5} {record.getMessage()}"

def setup_logging(config: BugHiveConfig) -> logging.Logger:
    root = logging.getLogger("bughive")
    root.setLevel(getattr(logging, config.logging.level.upper(), logging.INFO))
    root.handlers.clear()
    if config.logging.console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(ConsoleFormatter())
        root.addHandler(ch)
    if config.logging.file:
        log_dir = os.path.join(config.project_root, os.path.dirname(config.logging.file_path))
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(config.project_root, config.logging.file_path), mode="w")
        fh.setFormatter(FileFormatter())
        root.addHandler(fh)
    return root

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"bughive.{name}")
