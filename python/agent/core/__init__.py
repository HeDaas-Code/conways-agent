"""
Core Package

Provides core agent functionality including:
- Startup engine
- State management
- Vault access
"""

from .startup import initialize_agent, get_current_state, startup_message
from .state import AgentState

__all__ = [
    "initialize_agent",
    "get_current_state",
    "startup_message",
    "AgentState",
]
