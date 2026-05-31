"""
Core Package

Provides core agent functionality including:
- Startup engine
- State management
- Vault access
- Perception system
- Processing pipeline
- World fragments
- LLM integration
- Consistency constraint engine
"""

from .startup import initialize_agent, get_current_state, startup_message
from .state import AgentState
from .perception import PerceptionInput, PerceptionSystem
from .pipeline import ProcessingPipeline, FitResult, ProcessingResult
from .world_fragment import WorldFragment
from .llm import LLMClient, LLMResponse
from .consistency import ConsistencyEngine, ConsistencyCheck, Conflict, ConflictResolution

__all__ = [
    "initialize_agent",
    "get_current_state",
    "startup_message",
    "AgentState",
    "PerceptionInput",
    "PerceptionSystem",
    "ProcessingPipeline",
    "FitResult",
    "ProcessingResult",
    "WorldFragment",
    "LLMClient",
    "LLMResponse",
    "ConsistencyEngine",
    "ConsistencyCheck",
    "Conflict",
    "ConflictResolution",
]
