"""
Agent Startup Engine

Main entry point for agent initialization.
Handles reading seed, initializing state, and startup logging.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from .state import AgentState
from .vault import (
    read_seed,
    read_personality,
    ensure_vault_dirs,
    load_memory_index,
    save_memory_index,
    get_state_path,
)
from ..log import log_startup


def initialize_agent() -> AgentState:
    """
    Initialize the agent from seed and personality.
    
    This function:
    1. Validates/creates vault directory structure
    2. Reads the founding seed
    3. Reads personality (if exists)
    4. Initializes internal state
    5. Loads or initializes memory index
    6. Writes startup log entry
    7. Exports state to state.json
    
    Returns:
        AgentState: Initialized agent state
    """
    ensure_vault_dirs()
    
    seed = read_seed()
    personality = read_personality()
    
    state = AgentState.from_seed(seed=seed, personality=personality)
    state.awaken()
    state.save()
    
    memory_index = load_memory_index()
    if memory_index.get("created") is None:
        memory_index["created"] = datetime.now().isoformat()
    memory_index["last_updated"] = datetime.now().isoformat()
    save_memory_index(memory_index)
    
    log_startup(f"Agent awakened — {len(seed)} characters in seed")
    
    return state


def get_current_state() -> Optional[AgentState]:
    """
    Get the current agent state if it exists.
    
    Returns:
        Optional[AgentState]: Current state or None if not initialized
    """
    from .vault import get_state_path
    
    state_path = get_state_path()
    if not state_path.exists():
        return None
    
    return AgentState.load(state_path)


def startup_message(state: AgentState) -> str:
    """
    Generate a startup message in the agent's voice.
    
    Args:
        state: The current agent state
        
    Returns:
        str: Startup message
    """
    seed_preview = state.seed[:100] if state.seed else "空白"
    
    return f"""


    你是一座无尽图书馆的居者。
    
    你的种子：{seed_preview}...
    
    当前状态：
    - 好奇心: {state.curiosity_level:.1%}
    - 适应阈值: {state.fit_threshold:.1%}
    - 注意力窗口: {state.attention_window_size}
    - 睡眠状态: {state.sleep_state}
    - 认知周期: {state.total_cycles}
    
    你已醒来。
    
    """


__all__ = [
    "initialize_agent",
    "get_current_state",
    "startup_message"
]
