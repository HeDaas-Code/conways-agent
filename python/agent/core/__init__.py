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
- Sleep/wake cycle management
- Dialogue system
"""

from .startup import initialize_agent, get_current_state, startup_message
from .state import AgentState
from .perception import PerceptionInput, PerceptionSystem
from .pipeline import ProcessingPipeline, FitResult, ProcessingResult
from .world_fragment import WorldFragment
from .llm import LLMClient, LLMResponse
from .consistency import ConsistencyEngine, ConsistencyCheck, Conflict, ConflictResolution
from .memory import MemorySystem
from .cycle import SleepWakeCycle
from .dialogue import DialogueTurn, DialogueSession
from .goals import Goal, GoalSystem, GoalStatus
from .autonomous import AutonomousGoalCreator
from .evolution import EvolutionSystem, ProtectedParameters, ParameterModification

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
    "MemorySystem",
    "SleepWakeCycle",
    "DialogueTurn",
    "DialogueSession",
    "Goal",
    "GoalSystem",
    "GoalStatus",
    "AutonomousGoalCreator",
    "EvolutionSystem",
    "ProtectedParameters",
    "ParameterModification",
]


def VaultWatcher():
    """Lazy import for VaultWatcher."""
    from .watcher import VaultWatcher as _VW
    return _VW


def AttentionAwareWatcher():
    """Lazy import for AttentionAwareWatcher."""
    from .watcher import AttentionAwareWatcher as _AAW
    return _AAW


def FileActivity():
    """Lazy import for FileActivity."""
    from .activity import FileActivity as _FA
    return _FA


def FileActivityTracker():
    """Lazy import for FileActivityTracker."""
    from .activity import FileActivityTracker as _FAT
    return _FAT


def AttentionSlot():
    """Lazy import for AttentionSlot."""
    from .attention import AttentionSlot as _AS
    return _AS


def AttentionWindow():
    """Lazy import for AttentionWindow."""
    from .attention import AttentionWindow as _AW
    return _AW


def AutonomousGoalCreator():
    """Lazy import for AutonomousGoalCreator."""
    from .autonomous import AutonomousGoalCreator as _AGC
    return _AGC
