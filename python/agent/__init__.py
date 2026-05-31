"""
Conway's Agent - Python Brain Layer

A human-like autonomous cognitive entity for Obsidian.
"""

from .core import (
    initialize_agent,
    get_current_state,
    startup_message,
    AgentState,
    PerceptionInput,
    PerceptionSystem,
    ProcessingPipeline,
    FitResult,
    ProcessingResult,
    WorldFragment,
)
from .log import (
    log_event,
    log_startup,
    log_shutdown,
    log_cycle,
    log_error,
    get_recent_logs,
)
from .knowledge import OBSIDIAN_SYNTAX, get_syntax_prompt

__version__ = "0.1.0"

__all__ = [
    "__version__",
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
    "log_event",
    "log_startup",
    "log_shutdown",
    "log_cycle",
    "log_error",
    "get_recent_logs",
    "OBSIDIAN_SYNTAX",
    "get_syntax_prompt",
]
