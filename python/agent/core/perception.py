"""
Perception System

Handles manual and automatic perception triggers.
Manages the perception history and file reading from vault.

Attention Window Integration:
- Files must be admitted to the attention window before perception
- Only files in the attention window can be perceived
- Priority is calculated based on various factors
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .attention import AttentionWindow
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
    - Attention window: only a bounded subset is perceived at any moment
    
    Priority Calculation:
    - Base priority: 0.5 for all new files
    - File recency: Recently modified files get +0.2 bonus
    - Curiosity push: Files from curiosity system get +0.15 bonus
    - User relevance: Files recently interacted with get +0.1 bonus
    - Existing interest: Partially processed files get +0.05 bonus
    """
    
    def __init__(self, attention_window_size: int = 3):
        """
        Initialize the perception system with empty history.
        
        Args:
            attention_window_size: Maximum number of files in attention window
        """
        self._perception_history: list[PerceptionInput] = []
        self._max_history: int = 100
        self._awareness_mode: bool = True  # True = active, False = passive
        self.attention = AttentionWindow(max_slots=attention_window_size)
        self._recently_interacted: list[tuple[str, datetime]] = []  # (path, timestamp)
    
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
    
    def perceive_file(self, path: str, trigger: str = "manual") -> Optional[PerceptionInput]:
        """
        Manually trigger perception of a specific file.
        
        The file must be admitted to the attention window first.
        If the attention window is full, the file is queued and None is returned.
        
        Args:
            path: Relative path from vault root (e.g., "notes/ideas.md")
            trigger: Type of perception trigger
            
        Returns:
            PerceptionInput: The perceived input, or None if not admitted to attention window
            
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
        
        # Calculate priority based on various factors
        priority = self._calculate_priority(path, trigger)
        
        # Request attention - if not admitted, return None
        admitted = self.attention.request_attention(path, priority)
        if not admitted:
            log_event(
                "perception_queued",
                f"File queued for attention: {path}",
                {"file_path": path, "priority": priority}
            )
            return None
        
        # Track user interaction for future priority calculation
        if trigger == "manual":
            self._add_user_interaction(path)
        
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
                "priority": priority,
                "perceived_at": perception.perceived_at.isoformat(),
            }
        )
        
        return perception
    
    def perceive_file_unchecked(self, path: str, trigger: str = "manual") -> PerceptionInput:
        """
        Perceive a file without attention window checks.
        
        Use this only when you know the file is already in the attention window.
        
        Args:
            path: Relative path from vault root
            trigger: Type of perception trigger
            
        Returns:
            PerceptionInput: The perceived input
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is in agent/ directory (self-perception)
        """
        if not self._awareness_mode:
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
        return perception
    
    def release_perception(self, path: str) -> None:
        """
        Release attention after processing is complete.
        
        This frees up the attention slot for other files.
        
        Args:
            path: Path to release
        """
        self.attention.release_attention(path)
        log_event(
            "perception_released",
            f"Released attention for: {path}",
            {"file_path": path}
        )
    
    def _calculate_priority(self, path: str, trigger: str) -> float:
        """
        Calculate priority for a file based on various factors.
        
        Priority factors:
        - Base priority: 0.5
        - File recency: Recently modified files get +0.2
        - Curiosity push: Curiosity-triggered files get +0.15
        - User relevance: Recently interacted files get +0.1
        - Existing interest: Partially processed files get +0.05
        
        Args:
            path: File path
            trigger: Perception trigger type
            
        Returns:
            float: Priority value (0.0-1.0)
        """
        priority = 0.5  # Base priority
        
        # Check file recency
        try:
            vault_path = get_vault_path()
            file_path = vault_path / path
            if file_path.exists():
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                # Recently modified (within 1 hour): +0.2
                if (datetime.now() - mtime) < timedelta(hours=1):
                    priority += 0.2
                # Recently modified (within 24 hours): +0.1
                elif (datetime.now() - mtime) < timedelta(hours=24):
                    priority += 0.1
        except Exception:
            pass
        
        # Curiosity push: +0.15
        if trigger == "curiosity":
            priority += 0.15
        
        # User relevance: recently interacted files get +0.1
        if trigger == "manual":
            priority += 0.1
        if self._is_recently_interacted(path):
            priority += 0.1
        
        # Check if already in attention (existing interest): +0.05
        if self.attention.is_in_attention(path):
            priority += 0.05
        
        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, priority))
    
    def _is_recently_interacted(self, path: str) -> bool:
        """Check if file was recently interacted with by user."""
        cutoff = datetime.now() - timedelta(hours=1)
        for file_path, timestamp in self._recently_interacted:
            if file_path == path and timestamp > cutoff:
                return True
        return False
    
    def _add_user_interaction(self, path: str) -> None:
        """Record a user interaction with a file."""
        self._recently_interacted.append((path, datetime.now()))
        # Keep only recent interactions
        if len(self._recently_interacted) > 50:
            self._recently_interacted = self._recently_interacted[-50:]
    
    def perceive_files(self, paths: list[str], trigger: str = "manual") -> list[PerceptionInput]:
        """
        Manually trigger perception of multiple files.
        
        Args:
            paths: List of relative paths from vault root
            trigger: Type of perception trigger
            
        Returns:
            list[PerceptionInput]: List of perceived inputs (excluding queued ones)
        """
        perceptions: list[PerceptionInput] = []
        
        for path in paths:
            try:
                perception = self.perceive_file(path, trigger)
                if perception is not None:
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
        
        Files that cannot be admitted to attention window are queued.
        
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
                if perception is not None:
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
