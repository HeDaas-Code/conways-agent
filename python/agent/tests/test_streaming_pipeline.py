"""
Tests for StreamingPipeline - Two-stage streaming response

RED phase: Tests verify the expected streaming behavior per Issue #37:
1. process_message() is async generator yielding thinking chunks then response
2. Thinking chunks fixed at 256 chars (last may be shorter)
3. thinking_start message with total_chars
4. thinking messages with chunk, index, is_last
5. thinking_done marker
6. response message
7. error message
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncGenerator


def create_mock_stream(thinking: str, response: str):
    """
    Create a mock LLM stream that yields thinking then response.
    """
    async def gen():
        chunk_size = 50
        for i in range(0, len(thinking), chunk_size):
            yield {"type": "thinking", "content": thinking[i:i+chunk_size]}
        yield {"type": "thinking_done"}
        yield {"type": "response", "content": response}
    return gen()


class TestStreamingPipelineInterface:
    """Test that StreamingPipeline exists and has correct interface."""

    def test_pipeline_module_exists(self):
        """StreamingPipeline module should be importable."""
        from agent.core.streaming_pipeline import StreamingPipeline
        assert StreamingPipeline is not None

    def test_process_message_is_async_generator_method(self):
        """process_message should be an async generator method."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        result = pipeline.process_message("test")
        assert hasattr(result, '__aiter__')
        assert hasattr(result, '__anext__')

    @pytest.mark.asyncio
    async def test_process_message_returns_async_generator(self):
        """process_message should return an async generator."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        result = pipeline.process_message("test")
        assert hasattr(result, '__aiter__')
        assert hasattr(result, '__anext__')


class TestThinkingStartMessage:
    """Test thinking_start message format."""

    @pytest.mark.asyncio
    async def test_first_message_is_thinking_start(self):
        """First message should be thinking_start with total_chars."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "A" * 100, "Hello"
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        assert len(messages) > 0
        assert messages[0].type == "thinking_start"
        assert "total_chars" in messages[0].payload
        assert messages[0].payload["total_chars"] == 100

    @pytest.mark.asyncio
    async def test_thinking_start_total_chars_exact_256(self):
        """total_chars should match actual thinking length."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "B" * 256, "Response"
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_start = messages[0]
        assert thinking_start.type == "thinking_start"
        assert thinking_start.payload["total_chars"] == 256


class TestThinkingChunks:
    """Test thinking chunk messages."""

    @pytest.mark.asyncio
    async def test_thinking_chunks_have_correct_fields(self):
        """Thinking messages should have chunk, index, is_last."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "X" * 100, "Hi"
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_messages = [m for m in messages if m.type == "thinking"]

        for msg in thinking_messages:
            assert "chunk" in msg.payload
            assert "index" in msg.payload
            assert "is_last" in msg.payload
            assert isinstance(msg.payload["index"], int)
            assert isinstance(msg.payload["is_last"], bool)

    @pytest.mark.asyncio
    async def test_thinking_chunk_size_256(self):
        """Thinking chunks should be 256 chars except last."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "A" * 600, "Hi"  # 600 chars = 2x256 + 88
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_messages = [m for m in messages if m.type == "thinking"]
        assert len(thinking_messages) == 3  # 256 + 256 + 88

        assert len(thinking_messages[0].payload["chunk"]) == 256
        assert len(thinking_messages[1].payload["chunk"]) == 256
        assert len(thinking_messages[2].payload["chunk"]) == 88

    @pytest.mark.asyncio
    async def test_thinking_chunk_index_sequential(self):
        """Thinking chunk indices should be 0, 1, 2, ..."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "B" * 600, "Hi"  # 3 chunks
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_messages = [m for m in messages if m.type == "thinking"]
        indices = [m.payload["index"] for m in thinking_messages]
        assert indices == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_is_last_true_only_for_last_chunk(self):
        """Only the last thinking chunk should have is_last=True."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "C" * 600, "Hi"  # 3 chunks
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_messages = [m for m in messages if m.type == "thinking"]

        for i, msg in enumerate(thinking_messages[:-1]):
            assert msg.payload["is_last"] == False, f"Chunk {i} should not be last"
        assert thinking_messages[-1].payload["is_last"] == True

    @pytest.mark.asyncio
    async def test_thinking_total_exactly_256_multiple(self):
        """When thinking is exact multiple of 256, no short last chunk."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "D" * 512, "Hi"  # Exactly 512 = 2 * 256
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_messages = [m for m in messages if m.type == "thinking"]

        assert len(thinking_messages) == 2
        assert len(thinking_messages[0].payload["chunk"]) == 256
        assert len(thinking_messages[1].payload["chunk"]) == 256
        assert thinking_messages[1].payload["is_last"] == True


class TestThinkingDone:
    """Test thinking_done message."""

    @pytest.mark.asyncio
    async def test_thinking_done_sent_after_all_chunks(self):
        """thinking_done should follow all thinking chunks."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "E" * 100, "Hi"
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_done = None
        for msg in reversed(messages):
            if msg.type == "thinking_done":
                thinking_done = msg
                break

        assert thinking_done is not None
        assert thinking_done.payload == {}

    @pytest.mark.asyncio
    async def test_thinking_done_before_response(self):
        """thinking_done should come before any response message."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "F" * 100, "Hello"
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_done_idx = None
        response_idx = None
        for i, msg in enumerate(messages):
            if msg.type == "thinking_done" and thinking_done_idx is None:
                thinking_done_idx = i
            if msg.type == "response" and response_idx is None:
                response_idx = i

        assert thinking_done_idx is not None
        assert response_idx is not None
        assert thinking_done_idx < response_idx


class TestResponse:
    """Test response message."""

    @pytest.mark.asyncio
    async def test_response_message_format(self):
        """Response should have type='response' and text in payload."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "G" * 50, "This is the response"
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        responses = [m for m in messages if m.type == "response"]
        assert len(responses) > 0
        assert "text" in responses[0].payload
        assert responses[0].payload["text"] == "This is the response"

    @pytest.mark.asyncio
    async def test_response_comes_after_thinking_done(self):
        """All thinking messages should come before first response."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "H" * 100, "Response text"
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        first_response_idx = None
        for i, msg in enumerate(messages):
            if msg.type == "response":
                first_response_idx = i
                break

        assert first_response_idx is not None
        for msg in messages[:first_response_idx]:
            assert msg.type in ("thinking_start", "thinking", "thinking_done")


class TestEmptyThinking:
    """Test edge case: empty thinking."""

    @pytest.mark.asyncio
    async def test_empty_thinking(self):
        """When thinking is empty, should skip thinking chunks."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "", "Direct response"
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_start = messages[0]
        assert thinking_start.type == "thinking_start"
        assert thinking_start.payload["total_chars"] == 0

        thinking_messages = [m for m in messages if m.type == "thinking"]
        assert len(thinking_messages) == 0

        thinking_done = [m for m in messages if m.type == "thinking_done"]
        assert len(thinking_done) == 1

        responses = [m for m in messages if m.type == "response"]
        assert len(responses) == 1


class TestErrorHandling:
    """Test error message handling."""

    @pytest.mark.asyncio
    async def test_error_message_format(self):
        """Error should have type='error' and message in payload."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()

        async def error_stream():
            raise Exception("Test error")
            yield  # make it a generator

        pipeline._create_llm_stream = MagicMock(return_value=error_stream())

        messages = [msg async for msg in pipeline.process_message("test")]

        errors = [m for m in messages if m.type == "error"]
        assert len(errors) > 0
        assert "message" in errors[0].payload
        assert "Test error" in errors[0].payload["message"]

    @pytest.mark.asyncio
    async def test_error_after_thinking_done(self):
        """If thinking succeeded but response failed, thinking_done should still be sent."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()

        async def partial_error_stream():
            yield {"type": "thinking", "content": "Some thinking"}
            yield {"type": "thinking_done"}
            raise Exception("Response failed")

        pipeline._create_llm_stream = MagicMock(return_value=partial_error_stream())

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_done = [m for m in messages if m.type == "thinking_done"]
        assert len(thinking_done) == 1

        errors = [m for m in messages if m.type == "error"]
        assert len(errors) == 1


class TestMessageOrder:
    """Test complete message ordering."""

    @pytest.mark.asyncio
    async def test_complete_message_sequence(self):
        """Complete sequence: thinking_start, [thinking chunks], thinking_done, [responses]."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()
        pipeline._create_llm_stream = MagicMock(return_value=create_mock_stream(
            "I" * 300, "Final"  # 300 = 256 + 44
        ))

        messages = [msg async for msg in pipeline.process_message("test")]

        assert messages[0].type == "thinking_start"

        thinking_done_idx = None
        for i, msg in enumerate(messages):
            if msg.type == "thinking_done":
                thinking_done_idx = i
                break

        for msg in messages[1:thinking_done_idx]:
            assert msg.type in ("thinking", "thinking_start"), f"Unexpected {msg.type}"

        for msg in messages[thinking_done_idx + 1:]:
            assert msg.type == "response", f"Unexpected {msg.type}"

    @pytest.mark.asyncio
    async def test_no_response_if_thinking_incomplete(self):
        """If thinking is incomplete due to error, no response should be sent."""
        from agent.core.streaming_pipeline import StreamingPipeline

        pipeline = StreamingPipeline()

        async def incomplete_stream():
            yield {"type": "thinking", "content": "Partial"}
            # No thinking_done, no response

        pipeline._create_llm_stream = MagicMock(return_value=incomplete_stream())

        messages = [msg async for msg in pipeline.process_message("test")]

        thinking_msgs = [m for m in messages if m.type == "thinking"]
        thinking_done = [m for m in messages if m.type == "thinking_done"]
        responses = [m for m in messages if m.type == "response"]

        assert len(thinking_msgs) == 1
        assert len(thinking_done) == 0
        assert len(responses) == 0
