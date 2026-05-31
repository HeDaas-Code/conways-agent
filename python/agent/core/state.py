"""
Agent State Management

Defines the AgentState class for managing agent internal state.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Import mode from mode_machine to avoid circular import
# The mode field stores the current operational mode


@dataclass
class AgentState:
    """
    Represents the internal state of the agent.
    
    Attributes:
        seed: The founding seed content
        personality: Current personality traits and biases
        curiosity_level: Agent curiosity level (0.0-1.0)
        fit_threshold: Fitness threshold for decision making
        attention_window_size: Number of items in attention window
        sleep_state: Current sleep state ("awake" or "sleeping")
        last_awakened: Timestamp of last awakening
        last_slept: Timestamp of last sleep
        wake_duration_seconds: How long to stay awake (default 300 = 5 min)
        sleep_duration_seconds: How long to sleep (default 3600 = 1 hour)
        total_cycles: Total number of cognitive cycles
        mode: Current operational mode (idle/interaction/self)
    """
    
    seed: str = ""
    personality: dict = field(default_factory=lambda: {
        "name": "Agent",
        "traits": {
            "curious": 0.5,
            "careful": 0.5,
            "creative": 0.5,
            "methodical": 0.5
        },
        "biases": [],
        "blind_spots": [],
        "description": "Default personality"
    })
    curiosity_level: float = 0.5
    fit_threshold: float = 0.5
    attention_window_size: int = 3
    sleep_state: str = "awake"
    last_awakened: Optional[datetime] = None
    last_slept: Optional[datetime] = None
    wake_duration_seconds: int = 300
    sleep_duration_seconds: int = 3600
    total_cycles: int = 0
    mode: str = "idle"  # Current operational mode: idle, interaction, self
    
    def __post_init__(self) -> None:
        """Validate state values after initialization."""
        self.curiosity_level = max(0.0, min(1.0, self.curiosity_level))
        self.fit_threshold = max(0.0, min(1.0, self.fit_threshold))
        self.attention_window_size = max(1, self.attention_window_size)
        self.wake_duration_seconds = max(1, self.wake_duration_seconds)
        self.sleep_duration_seconds = max(1, self.sleep_duration_seconds)
        
        if self.sleep_state not in ("awake", "sleeping"):
            self.sleep_state = "awake"
    
    @classmethod
    def load(cls, state_path: Optional[Path] = None) -> AgentState:
        """
        Load state from a JSON file.
        
        Args:
            state_path: Path to state.json, defaults to agent/state.json
            
        Returns:
            AgentState: Loaded state instance
            
        Raises:
            FileNotFoundError: If state file doesn't exist
            ValueError: If state file is invalid
        """
        if state_path is None:
            from agent.core.vault import get_state_path
            state_path = get_state_path()
        
        if not state_path.exists():
            raise FileNotFoundError(f"State file not found: {state_path}")
        
        content = state_path.read_text(encoding="utf-8")
        data = json.loads(content)
        
        if "last_awakened" in data and data["last_awakened"]:
            data["last_awakened"] = datetime.fromisoformat(data["last_awakened"])
        
        if "last_slept" in data and data["last_slept"]:
            data["last_slept"] = datetime.fromisoformat(data["last_slept"])
        
        if "wake_duration_seconds" not in data:
            data["wake_duration_seconds"] = 300
        if "sleep_duration_seconds" not in data:
            data["sleep_duration_seconds"] = 3600
        
        return cls(**data)
    
    def save(self, state_path: Optional[Path] = None) -> None:
        """
        Save state to a JSON file.
        
        Args:
            state_path: Path to state.json, defaults to agent/state.json
        """
        if state_path is None:
            from agent.core.vault import get_state_path
            state_path = get_state_path()
        
        state_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = asdict(self)
        if data["last_awakened"]:
            data["last_awakened"] = data["last_awakened"].isoformat()
        if data["last_slept"]:
            data["last_slept"] = data["last_slept"].isoformat()
        
        state_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def update(self, **kwargs) -> None:
        """
        Update specific state fields.
        
        Args:
            **kwargs: Fields to update
        """
        valid_fields = {
            "seed", "personality", "curiosity_level", 
            "fit_threshold", "attention_window_size", 
            "sleep_state", "total_cycles", 
            "last_awakened", "last_slept",
            "wake_duration_seconds", "sleep_duration_seconds"
        }
        
        for key, value in kwargs.items():
            if key in valid_fields:
                setattr(self, key, value)
        
        self.__post_init__()
    
    def awaken(self) -> None:
        """Mark the agent as awake and record timestamp."""
        self.sleep_state = "awake"
        self.last_awakened = datetime.now()
    
    def sleep(self) -> None:
        """Mark the agent as sleeping and record timestamp."""
        self.sleep_state = "sleeping"
        self.last_slept = datetime.now()
    
    def increment_cycle(self) -> None:
        """Increment the total cycle counter."""
        self.total_cycles += 1
    
    def to_dict(self) -> dict:
        """
        Convert state to dictionary.
        
        Returns:
            dict: State as dictionary
        """
        data = asdict(self)
        if data["last_awakened"]:
            data["last_awakened"] = data["last_awakened"].isoformat()
        if data["last_slept"]:
            data["last_slept"] = data["last_slept"].isoformat()
        return data
    
    @classmethod
    def from_seed(cls, seed: str, personality: Optional[dict] = None) -> AgentState:
        """
        Create a new state from seed and personality.
        
        Args:
            seed: The founding seed content
            personality: Optional personality dict
            
        Returns:
            AgentState: New state instance
        """
        return cls(
            seed=seed,
            personality=personality or cls().personality,
            curiosity_level=0.5,
            fit_threshold=0.5,
            attention_window_size=3,
            sleep_state="awake",
            last_awakened=datetime.now(),
            last_slept=None,
            wake_duration_seconds=300,
            sleep_duration_seconds=3600,
            total_cycles=0
        )


__all__ = ["AgentState"]
