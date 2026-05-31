"""
Perception System

Handles manual and automatic perception triggers.
Manages the perception history and file reading from vault.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .vault import get_vault_path, read_file
from ..log import log_event
from .decay import get_decay_system


@dataclass
class PerceptionInput:
    """
    Represents something the Agent has perceived.
    
    Attributes:
        file_path: Path to the perceived file (relative to vault)
        content: The content that was perceived
        trigger_type: What triggered this perception
            - "manual": User manually triggered perception
            - "event": Triggered by an event
            - "timer": Triggered by a timer
            - "curiosity": Triggered by agent curiosity
        perceived_at: Timestamp when perception occurred
        user_mentioned: Whether this was triggered by user conversation
    """
    
    file_path: str
    content: str
    trigger_type: str = "manual"
    perceived_at: datetime = field(default_factory=datetime.now)
    user_mentioned: bool = True
    
    def __post_init__(self) -> None:
        """Validate perception fields."""
        valid_triggers = ("manual", "event", "timer", "curiosity")
        if self.trigger_type not in valid_triggers:
            self.trigger_type = "manual"


class PerceptionSystem:
    """
    Manages perception of files from the vault.
    
    This system handles:
    - Manual perception of specific files
    - Batch perception of multiple files
    - Perception history tracking
    - Filtering out agent/ directory to avoid self-perception loops
    - Awareness modes: active (full processing) and passive (event detection only)
    """
    
    def __init__(self) -> None:
        """Initialize the perception system with empty history."""
        self._perception_history: list[PerceptionInput] = []
        self._max_history: int = 100
        self._awareness_mode: bool = True  # True = active, False = passive
    
    def set_awareness_mode(self, awake: bool) -> None:
        """
        Set awareness mode.
        
        Args:
            awake: True = active processing, False = passive only
        """
        previous_mode = "active" if self._awareness_mode else "passive"
        self._awareness_mode = awake
        new_mode = "active" if awake else "passive"
        
        log_event(
            "awareness_mode_change",
            f"Awareness mode changed: {previous_mode} -> {new_mode}",
            {"awake": awake, "mode": new_mode}
        )
    
    @property
    def is_active_mode(self) -> bool:
        """
        Check if in active processing mode.
        
        Returns:
            bool: True if active (awake), False if passive (sleeping)
        """
        return self._awareness_mode
    
    def process_passive_event(self, event: dict) -> None:
        """
        Process a file event in passive mode.
        
        In passive mode, events are detected but NOT actively processed.
        Just log the event for future reference.
        
        Args:
            event: Event data with keys like 'path', 'type', 'timestamp'
        """
        if self._awareness_mode:
            return
        
        log_event(
            "passive_event",
            f"Passive awareness: detected {event.get('type', 'unknown')} event",
            {
                "path": event.get("path", "unknown"),
                "event_type": event.get("type", "unknown"),
                "timestamp": event.get("timestamp", ""),
                "mode": "passive",
            }
        )
    
    def perceive_file(self, path: str, trigger: str = "manual") -> PerceptionInput:
        """
        Manually trigger perception of a specific file.
        
        Args:
            path: Relative path from vault root (e.g., "notes/ideas.md")
            trigger: Type of perception trigger
            
        Returns:
            PerceptionInput: The perceived input
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is in agent/ directory (self-perception)
        """
        if not self._awareness_mode:
            log_event(
                "perception_blocked",
                f"Perception blocked - in passive mode: {path}",
                {"file_path": path, "mode": "passive"}
            )
            raise ValueError(
                f"Cannot perceive files in passive mode: {path}. "
                "Wake the agent to enable active perception."
            )
        
        vault_path = get_vault_path()
        file_full_path = vault_path / path
        
        if not file_full_path.exists():
            raise FileNotFoundError(f"File not found: {file_full_path}")
        
        if self._is_agent_file(path):
            raise ValueError(
                f"Cannot perceive agent/ directory files: {path}. "
                "This prevents self-perception loops."
            )
        
        content = file_full_path.read_text(encoding="utf-8")
        
        perception = PerceptionInput(
            file_path=path,
            content=content,
            trigger_type=trigger,
            perceived_at=datetime.now(),
            user_mentioned=(trigger == "manual")
        )
        
        self._add_to_history(perception)

        # Record in decay system
        decay = get_decay_system()
        decay.on_fragment_read(path)

        log_event(
            "perception",
            f"Perceived file: {path}",
            {
                "file_path": path,
                "trigger_type": trigger,
                "content_length": len(content),
                "perceived_at": perception.perceived_at.isoformat(),
            }
        )
        
        return perception
    
    def perceive_files(self, paths: list[str], trigger: str = "manual") -> list[PerceptionInput]:
        """
        Manually trigger perception of multiple files.
        
        Args:
            paths: List of relative paths from vault root
            trigger: Type of perception trigger
            
        Returns:
            list[PerceptionInput]: List of perceived inputs
        """
        perceptions: list[PerceptionInput] = []
        
        for path in paths:
            try:
                perception = self.perceive_file(path, trigger)
                perceptions.append(perception)
            except (FileNotFoundError, ValueError) as e:
                log_event(
                    "perception_error",
                    f"Failed to perceive {path}: {e}",
                    {"file_path": path, "error": str(e)}
                )
                print(f"警告: 无法感知文件 {path}: {e}")
        
        return perceptions
    
    def perceive_all_user_files(self) -> list[PerceptionInput]:
        """
        Perceive all user files in the vault (excluding agent/ directory).
        
        Returns:
            list[PerceptionInput]: List of all perceived files
        """
        vault_path = get_vault_path()
        user_files: list[Path] = []
        
        for path in vault_path.rglob("*.md"):
            if self._is_agent_file(str(path.relative_to(vault_path))):
                continue
            user_files.append(path)
        
        perceptions: list[PerceptionInput] = []
        
        for file_path in sorted(user_files):
            relative_path = str(file_path.relative_to(vault_path))
            try:
                perception = self.perceive_file(relative_path, "manual")
                perceptions.append(perception)
            except (FileNotFoundError, ValueError) as e:
                print(f"警告: 无法感知文件 {relative_path}: {e}")
        
        log_event(
            "perception_batch",
            f"Perceived {len(perceptions)} user files",
            {
                "total_files": len(user_files),
                "perceived_count": len(perceptions),
            }
        )
        
        return perceptions
    
    def get_recent_perceptions(self, limit: int = 10) -> list[PerceptionInput]:
        """
        Get the recent perception history.
        
        Args:
            limit: Maximum number of perceptions to return
            
        Returns:
            list[PerceptionInput]: Recent perceptions, most recent first
        """
        sorted_history = sorted(
            self._perception_history,
            key=lambda p: p.perceived_at,
            reverse=True
        )
        return sorted_history[:limit]
    
    def _is_agent_file(self, path: str) -> bool:
        """
        Check if a path belongs to the agent/ directory.
        
        Args:
            path: Relative path to check
            
        Returns:
            bool: True if path is in agent/ directory
        """
        path_obj = Path(path)
        return any(part == "agent" for part in path_obj.parts)
    
    def _add_to_history(self, perception: PerceptionInput) -> None:
        """
        Add a perception to history, maintaining max size.
        
        Args:
            perception: Perception to add
        """
        self._perception_history.append(perception)
        
        if len(self._perception_history) > self._max_history:
            self._perception_history = self._perception_history[-self._max_history:]


__all__ = ["PerceptionInput", "PerceptionSystem"]
