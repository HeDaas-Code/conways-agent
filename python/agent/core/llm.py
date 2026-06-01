"""
LLM Integration Module

Provides LLM client integration. Supports two backends:
- Native Anthropic SDK (for MiniMax M-series via Anthropic-compatible API)
- LiteLLM (for all other providers)

Detection: models with "anthropic/" prefix use native SDK, others use LiteLLM.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import litellm

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


@dataclass
class LLMResponse:
    """Response from an LLM completion request."""

    content: str
    model: str
    usage: dict
    thinking: str = ""


class LLMClient:
    """
    Client for LLM completions.

    Supports any model provider via LiteLLM, with native Anthropic SDK
    acceleration for MiniMax M-series models (anthropic/MiniMax-M2.7 etc.).
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize the LLM client.

        Args:
            model: Model identifier. Defaults to LITELLM_MODEL env var.
        """
        self.model = model or os.getenv("LITELLM_MODEL", "anthropic/MiniMax-M2.7")
        self._anthropic_client: Optional[anthropic.Anthropic] = None

    def _get_anthropic_client(self) -> anthropic.Anthropic:
        """Get or create a cached Anthropic client."""
        if self._anthropic_client is None:
            base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
            api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("LITELLM_API_KEY")
            self._anthropic_client = anthropic.Anthropic(
                base_url=base_url,
                api_key=api_key,
            )
        return self._anthropic_client

    def _is_anthropic_model(self) -> bool:
        """Check if current model should use native Anthropic SDK."""
        return self.model.startswith("anthropic/")

    def complete(self, messages: list[dict], **kwargs) -> LLMResponse:
        """
        Send a completion request to the LLM.

        Args:
            messages: List of message dicts with "role" and "content" keys
            **kwargs: Additional arguments passed to the backend

        Returns:
            LLMResponse: The response content and metadata

        Raises:
            Exception: On API errors
        """
        if self._is_anthropic_model() and HAS_ANTHROPIC:
            return self._complete_anthropic(messages, **kwargs)
        return self._complete_litellm(messages, **kwargs)

    def _complete_anthropic(
        self, messages: list[dict], **kwargs
    ) -> LLMResponse:
        """Use native Anthropic SDK (MiniMax M-series path)."""
        client = self._get_anthropic_client()

        system: Optional[str] = None
        anthropic_messages: list[dict] = []

        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        max_tokens = kwargs.pop("max_tokens", 1024)
        temperature = kwargs.pop("temperature", None)
        thinking = kwargs.pop("thinking", None)

        resp = client.messages.create(
            model=self.model.replace("anthropic/", ""),
            system=system,
            messages=anthropic_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )

        content = ""
        thinking = ""
        for block in resp.content:
            if hasattr(block, "text") and block.text:
                content = block.text
            elif hasattr(block, "thinking") and block.thinking:
                thinking = block.thinking

        return LLMResponse(
            content=content.strip() if content else content,
            thinking=thinking,
            model=self.model,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )

    def _complete_litellm(
        self, messages: list[dict], **kwargs
    ) -> LLMResponse:
        """Use LiteLLM for all other models."""
        litellm.drop_params = True
        response = litellm.completion(
            model=self.model,
            messages=messages,
            **kwargs
        )
        content = response["choices"][0]["message"]["content"]
        return LLMResponse(
            content=content.strip() if content else content,
            model=self.model,
            usage=response.get("usage", {}),
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
            **kwargs: Additional arguments passed to the backend

        Returns:
            str: The response content
        """
        return self.complete([
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ], **kwargs).content


__all__ = ["LLMClient", "LLMResponse"]
