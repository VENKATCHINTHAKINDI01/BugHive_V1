"""
BugHive v2 — LLM Client (Groq + Llama 3.3 70B).

Lightweight Groq API client using Python stdlib (no SDK dependency).
Groq uses an OpenAI-compatible API at api.groq.com/openai/v1/chat/completions.
Falls back to deterministic mode if GROQ_API_KEY is not set.

Usage:
    client = LLMClient(config)
    response = client.chat(system_prompt, user_message)
"""
from __future__ import annotations

import json
import http.client
import ssl
from typing import TYPE_CHECKING

from bughive.core.logger import get_logger

if TYPE_CHECKING:
    from bughive.core.config import BugHiveConfig


class LLMClient:
    """
    Thin wrapper around the Groq Chat Completions API (OpenAI-compatible).
    Uses http.client (stdlib) — no external dependencies needed.
    Powered by Llama 3.3 70B Versatile via Groq's LPU inference engine.
    """

    API_HOST = "api.groq.com"
    API_PATH = "/openai/v1/chat/completions"

    def __init__(self, config: BugHiveConfig):
        self.config = config
        self.logger = get_logger("LLMClient")
        self.api_key = config.llm.api_key
        self.model = config.llm.model
        self.max_tokens = config.llm.max_tokens
        self.temperature = config.llm.temperature
        self._call_count = 0

        if not self.api_key:
            self.logger.warning(
                "GROQ_API_KEY not set — running in FALLBACK mode "
                "(agents will use deterministic logic instead of LLM reasoning)"
            )
        else:
            self.logger.info(f"Groq LLM initialized: model={self.model}")

    @property
    def is_available(self) -> bool:
        """Check if LLM is available (API key is set)."""
        return bool(self.api_key)

    @property
    def call_count(self) -> int:
        return self._call_count

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """
        Send a message to Llama 3.3 70B via Groq and get a text response.

        Args:
            system_prompt: The system/role prompt defining agent behavior.
            user_message: The user message content with context data.
            max_tokens: Override max tokens for this call.
            temperature: Override temperature for this call.

        Returns:
            The assistant's text response.

        Raises:
            LLMError: If the API call fails.
        """
        if not self.api_key:
            raise LLMError("No API key — use is_available check before calling")

        # Groq uses OpenAI-compatible format
        payload = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }

        # Groq uses Bearer token auth (OpenAI-compatible)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        self.logger.info(f"Groq LLM call #{self._call_count + 1}: {len(user_message)} chars → {self.model}")

        try:
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(self.API_HOST, context=context, timeout=120)
            body = json.dumps(payload).encode("utf-8")
            conn.request("POST", self.API_PATH, body=body, headers=headers)
            response = conn.getresponse()
            raw = response.read().decode("utf-8")
            conn.close()

            if response.status != 200:
                raise LLMError(f"Groq API returned {response.status}: {raw[:500]}")

            data = json.loads(raw)
            self._call_count += 1

            # OpenAI-compatible response format:
            # {"choices": [{"message": {"content": "..."}}]}
            choices = data.get("choices", [])
            if not choices:
                raise LLMError("Groq API returned empty choices")

            result = choices[0].get("message", {}).get("content", "")

            # Log usage if available
            usage = data.get("usage", {})
            if usage:
                self.logger.info(
                    f"Groq response: {len(result)} chars "
                    f"(tokens: {usage.get('prompt_tokens', '?')} in, "
                    f"{usage.get('completion_tokens', '?')} out, "
                    f"{usage.get('total_tokens', '?')} total)"
                )
            else:
                self.logger.info(f"Groq response: {len(result)} chars")

            return result

        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Groq API call failed: {e}") from e

    def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int | None = None,
    ) -> dict:
        """
        Send a message and parse the response as JSON.
        Instructs the model to return only valid JSON.
        """
        json_system = (
            system_prompt + "\n\n"
            "CRITICAL: Respond with ONLY valid JSON. No markdown fences, no backticks, "
            "no explanation before or after the JSON. Just the raw JSON object."
        )

        # Use Groq's JSON mode for more reliable structured output
        raw = self.chat(json_system, user_message, max_tokens=max_tokens)

        # Strip markdown fences if model added them anyway
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM JSON: {e}")
            self.logger.error(f"Raw response (first 500 chars): {raw[:500]}")
            raise LLMError(f"Invalid JSON from Groq/Llama: {e}") from e


class LLMError(Exception):
    """Raised when an LLM call fails."""
    pass
