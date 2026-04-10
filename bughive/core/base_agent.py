"""
BugHive v2 — Base Agent with LLM integration.

All agents inherit from BaseAgent which provides:
    - LLM client access (self.llm)
    - Structured logging and tracing
    - Common run() wrapper with timing and error handling
    - Tool call recording
"""
from __future__ import annotations
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from bughive.core.logger import get_logger
from bughive.core.models import AgentStatus, AgentTrace, PipelineState, ToolCall
from bughive.core.llm_client import LLMClient

if TYPE_CHECKING:
    from bughive.core.config import BugHiveConfig


class BaseAgent(ABC):

    def __init__(self, config: BugHiveConfig):
        self.config = config
        self.logger = get_logger(self.name)
        self.llm = LLMClient(config)
        self._trace: AgentTrace | None = None
        self._tool_calls: list[ToolCall] = []

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def description(self) -> str: return ""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The system prompt that defines this agent's role for the LLM."""
        ...

    @abstractmethod
    def _execute(self, state: PipelineState) -> PipelineState:
        """Core agent logic — implemented by each agent."""
        ...

    def run(self, state: PipelineState) -> PipelineState:
        self._tool_calls = []
        self._trace = AgentTrace(
            agent_name=self.name, status=AgentStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._print_header()
        start = time.time()
        try:
            state = self._execute(state)
            elapsed = int((time.time() - start) * 1000)
            self._trace.status = AgentStatus.SUCCESS
            self._trace.finished_at = datetime.now(timezone.utc).isoformat()
            self._trace.duration_ms = elapsed
            self._trace.tool_calls = self._tool_calls
            self._trace.llm_calls = self.llm.call_count
            self.logger.info(f"Completed in {elapsed}ms ({self.llm.call_count} LLM calls)")
            self._print_footer(True)
        except Exception as e:
            elapsed = int((time.time() - start) * 1000)
            self._trace.status = AgentStatus.FAILED
            self._trace.finished_at = datetime.now(timezone.utc).isoformat()
            self._trace.duration_ms = elapsed
            self._trace.error = str(e)
            self._trace.tool_calls = self._tool_calls
            self.logger.error(f"Failed after {elapsed}ms: {e}")
            self._print_footer(False)
        state.add_trace(self._trace)
        return state

    def ask_llm(self, user_message: str, max_tokens: int | None = None) -> str:
        """Convenience: send a message using this agent's system prompt."""
        return self.llm.chat(self.system_prompt, user_message, max_tokens=max_tokens)

    def ask_llm_json(self, user_message: str, max_tokens: int | None = None) -> dict:
        """Convenience: send a message and get JSON back."""
        return self.llm.chat_json(self.system_prompt, user_message, max_tokens=max_tokens)

    def record_tool_call(self, tool_name, arguments=None, result_summary="", duration_ms=0):
        call = ToolCall(tool_name=tool_name, arguments=arguments or {},
                        result_summary=result_summary, duration_ms=duration_ms)
        self._tool_calls.append(call)

    def set_trace_detail(self, action: str, detail: str):
        if self._trace:
            self._trace.action = action
            self._trace.detail = detail

    def _print_header(self):
        mode = "LLM" if self.llm.is_available else "FALLBACK"
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info(f"  Agent: {self.name} [{mode} mode]")
        if self.description:
            self.logger.info(f"  Task:  {self.description}")
        self.logger.info("=" * 60)

    def _print_footer(self, success):
        icon = "✅" if success else "❌"
        self.logger.info(f"  {icon} {self.name}: {'Complete' if success else 'FAILED'}")
        self.logger.info("")
