"""
LLM Integration Module

Provides LLM client integration using LiteLLM for the Agent's cognitive processes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import litellm


@dataclass
class LLMResponse:
    """Response from an LLM completion request."""

    content: str
    model: str
    usage: dict


class LLMClient:
    """
    Client for LLM completions using LiteLLM.

    Supports any model provider that LiteLLM supports (OpenAI, Anthropic,
    local models, proxy services, etc.).
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize the LLM client.

        Args:
            model: Model identifier. Defaults to LITELLM_MODEL env var,
                   then "minimax-cn/gemini-2.5-flash".
        """
        self.model = model or os.getenv("LITELLM_MODEL", "minimax-cn/gemini-2.5-flash")

    def complete(self, messages: list[dict], **kwargs) -> LLMResponse:
        """
        Send a completion request to the LLM.

        Args:
            messages: List of message dicts with "role" and "content" keys
            **kwargs: Additional arguments passed to litellm.completion

        Returns:
            LLMResponse: The response content and metadata

        Raises:
            litellm.APIError: On API errors
        """
        response = litellm.completion(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return LLMResponse(
            content=response["choices"][0]["message"]["content"],
            model=self.model,
            usage=response.get("usage", {})
        )

    def complete_str(
        self,
        system: str,
        user: str,
        **kwargs
    ) -> str:
        """
        Convenience method: system prompt + user prompt -> string response.

        Args:
            system: System prompt content
            user: User prompt content
            **kwargs: Additional arguments passed to litellm.completion

        Returns:
            str: The response content
        """
        return self.complete([
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ], **kwargs).content


__all__ = ["LLMClient", "LLMResponse"]
