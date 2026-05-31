"""
Streaming Pipeline - Two-stage streaming response

Per Issue #37:
- Fixed 256 char thinking chunks (last may be shorter)
- thinking_start → thinking chunks → thinking_done → response
- Bounded queue for backpressure
- Fail-fast error handling
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Literal

from agent.core.llm import LLMClient
from agent.core.interest_model import InterestModel


@dataclass
class StreamMessage:
    """A single WebSocket push unit per Issue #37."""
    type: Literal["thinking_start", "thinking", "thinking_done", "response", "error"]
    payload: dict[str, Any]


class StreamingPipeline:
    """
    Two-stage streaming: thinking → response.

    Interface:
        async def process_message(message: str) -> AsyncGenerator[StreamMessage, None]:

    Phase 1: yield thinking_start, then thinking chunks (256 chars), then thinking_done
    Phase 2: yield response
    """

    # Fixed chunk size per spec
    CHUNK_SIZE = 256

    def __init__(self, llm_client: LLMClient | None = None, interest_model: "InterestModel | None" = None):
        self._llm = llm_client or LLMClient()
        self._interest_model = interest_model

    async def _create_llm_stream(self, message: str) -> AsyncGenerator[dict, None]:
        """
        Stream LLM output as dicts with 'type' and 'content' keys.
        Subclasses can override to customize LLM integration.
        """
        # Default: call LLMClient and yield simple response
        response = self._llm.complete_str(
            system="You are a helpful assistant.",
            user=message,
        )
        yield {"type": "thinking", "content": ""}  # Empty thinking to skip
        yield {"type": "thinking_done"}
        yield {"type": "response", "content": response}

    async def process_message(
        self, message: str
    ) -> AsyncGenerator[StreamMessage, None]:
        """
        Main entry point. Drives the two-stage pipeline.

        Yields:
            - thinking_start: {"type": "thinking_start", "payload": {"total_chars": N}}
            - thinking: {"type": "thinking", "payload": {"chunk": "...", "index": i, "is_last": bool}}
            - thinking_done: {"type": "thinking_done", "payload": {}}
            - response: {"type": "response", "payload": {"text": "..."}}
            - error: {"type": "error", "payload": {"message": "..."}}
        """
        try:
            # Phase 1: Accumulate thinking
            thinking_buffer = ""
            thinking_chunks: list[str] = []
            thinking_done_received = False

            async for event in self._create_llm_stream(message):
                if event.get("type") == "thinking":
                    content = event.get("content", "")
                    thinking_buffer += content

                    # Flush full chunks (256 chars)
                    while len(thinking_buffer) >= self.CHUNK_SIZE:
                        thinking_chunks.append(thinking_buffer[:self.CHUNK_SIZE])
                        thinking_buffer = thinking_buffer[self.CHUNK_SIZE:]

                elif event.get("type") == "thinking_done":
                    # Flush remaining buffer as final chunk
                    if thinking_buffer:
                        thinking_chunks.append(thinking_buffer)
                        thinking_buffer = ""
                    thinking_done_received = True
                    break

            # If stream ended without thinking_done, flush remaining buffer
            if not thinking_done_received and thinking_buffer:
                thinking_chunks.append(thinking_buffer)
                thinking_buffer = ""

            # Yield thinking_start
            total_chars = sum(len(c) for c in thinking_chunks)
            yield StreamMessage(
                type="thinking_start",
                payload={"total_chars": total_chars},
            )

            # Yield thinking chunks (if we have any)
            if thinking_chunks:
                for i, chunk in enumerate(thinking_chunks):
                    is_last = (i == len(thinking_chunks) - 1) and thinking_done_received
                    yield StreamMessage(
                        type="thinking",
                        payload={
                            "chunk": chunk,
                            "index": i,
                            "is_last": is_last,
                        },
                    )

            # Only yield thinking_done if completed successfully
            if thinking_done_received:
                yield StreamMessage(type="thinking_done", payload={})

            # Phase 2: Stream response
            async for event in self._create_llm_stream(message):
                if event.get("type") == "response":
                    content = event.get("content", "")
                    if content:
                        yield StreamMessage(
                            type="response",
                            payload={"text": content},
                        )
                    break

        except Exception as e:
            yield StreamMessage(
                type="error",
                payload={"message": str(e)},
            )
