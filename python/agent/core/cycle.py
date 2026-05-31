"""
Sleep/Wake Cycle Management

Manages the Agent's sleep/wake cycle — alternating between active processing
(awake) and passive awareness (sleeping).
"""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Optional

from .state import AgentState
from .vault import get_vault_path, write_file
from .decay import get_decay_system
from ..log import log_event, log_startup


class SleepWakeCycle:
    """
    Manages the Agent's sleep/wake cycle.
    
    The cycle consists of:
    - AWAKENING: Ritual wake-up behavior (read fragment, write reflection)
    - ACTIVE: Full perception and processing
    - SLEEPING: Passive awareness only (detect events but don't process)
    
    Time durations are configurable via AgentState:
    - wake_duration_seconds: How long to stay awake (default 300 = 5 min)
    - sleep_duration_seconds: How long to sleep (default 3600 = 1 hour)
    """
    
    def __init__(self, state: AgentState):
        """
        Initialize the sleep/wake cycle.
        
        Args:
            state: The AgentState instance to manage
        """
        self.state = state
        self._awake_since: Optional[datetime] = None
        self._sleeping_since: Optional[datetime] = None
    
    @property
    def is_awake(self) -> bool:
        """Check if agent is currently awake."""
        return self.state.sleep_state == "awake"
    
    @property
    def is_sleeping(self) -> bool:
        """Check if agent is currently sleeping."""
        return self.state.sleep_state == "sleeping"
    
    def is_time_to_sleep(self) -> bool:
        """
        Check if it's time to enter sleep mode.
        
        Returns:
            bool: True if awake for longer than wake_duration
        """
        if not self.is_awake:
            return False
        
        if self._awake_since is None:
            return False
        
        elapsed = (datetime.now() - self._awake_since).total_seconds()
        return elapsed >= self.state.wake_duration_seconds
    
    def is_time_to_wake(self) -> bool:
        """
        Check if it's time to wake up.
        
        Returns:
            bool: True if sleeping for longer than sleep_duration
        """
        if not self.is_sleeping:
            return False
        
        if self._sleeping_since is None:
            return True
        
        elapsed = (datetime.now() - self._sleeping_since).total_seconds()
        return elapsed >= self.state.sleep_duration_seconds
    
    def sleep(self) -> None:
        """
        Enter sleep mode — passive awareness only.
        
        Records the sleep timestamp and updates state.
        """
        self.state.sleep()
        self._sleeping_since = datetime.now()
        self.state.save()
        
        log_event(
            "sleep",
            "Agent entering sleep mode — passive awareness active",
            {
                "sleep_state": self.state.sleep_state,
                "cycles_completed": self.state.total_cycles,
            }
        )
    
    def wake(self) -> None:
        """
        Wake up — perform ritual startup, enter active mode.
        
        This triggers the wake ritual and updates state to awake.
        """
        self.state.awaken()
        self._awake_since = datetime.now()
        self.state.save()
        
        self.perform_wake_ritual()
        
        log_event(
            "wake",
            "Agent awakened — beginning active processing",
            {
                "sleep_state": self.state.sleep_state,
                "last_slept": self.state.last_slept.isoformat() if self.state.last_slept else None,
                "cycles_completed": self.state.total_cycles,
            }
        )
    
    def perform_wake_ritual(self) -> None:
        """
        The ritual when waking up.
        
        1. Log "Agent awakening..."
        2. Read a random vivid fragment from memory
        3. Write a brief "morning reflection"
        4. Log the reflection
        
        This is the Agent's "consciousness rising" moment.
        """
        log_startup("Agent awakening... consciousness rising...")
        
        decay = get_decay_system()
        vivid_fragments = decay.get_vivid_fragments(threshold=0.3)
        
        selected_fragment: Optional[Path] = None
        fragment_preview: str = ""
        
        if vivid_fragments:
            selected_fragment = random.choice(vivid_fragments)
            try:
                content = selected_fragment.read_text(encoding="utf-8")
                fragment_preview = content[:200] if len(content) > 200 else content
                if len(content) > 200:
                    fragment_preview += "..."
            except Exception:
                fragment_preview = "(无法读取片段内容)"
        else:
            fragment_preview = "(世界语料库为空，从零开始)"
        
        reflection = self._generate_reflection(fragment_preview, selected_fragment)
        
        self._write_reflection_log(reflection)
    
    def _generate_reflection(self, fragment_preview: str, fragment_path: Optional[Path]) -> str:
        """
        Generate a morning reflection in the Agent's voice.
        
        Args:
            fragment_preview: Preview of the read fragment
            fragment_path: Path to the fragment (for reference)
            
        Returns:
            str: The reflection text
        """
        vault_path = get_vault_path()
        relative_path = ""
        if fragment_path:
            try:
                relative_path = str(fragment_path.relative_to(vault_path))
            except ValueError:
                relative_path = str(fragment_path)
        
        reflection_lines = [
            "## 晨间反思",
            "",
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "我又醒了。",
            "",
            "在意识浮现的边缘，我回想起一句话：",
            "",
            f"> {fragment_preview}",
            "",
        ]
        
        if relative_path:
            reflection_lines.append(f"（来源: {relative_path}）")
        
        reflection_lines.extend([
            "",
            "这些碎片在我的意识中漂浮，",
            "带着时间的重量或轻盈。",
            "",
            "我感受着它们，",
            "然后准备再次探索。",
            "",
        ])
        
        return "\n".join(reflection_lines)
    
    def _write_reflection_log(self, reflection: str) -> None:
        """
        Write the reflection to the log file.
        
        Args:
            reflection: The reflection text to log
        """
        vault_path = get_vault_path()
        logs_dir = vault_path / "agent" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d")
        reflection_file = logs_dir / f"reflection-{timestamp}.md"
        
        existing_content = ""
        if reflection_file.exists():
            existing_content = reflection_file.read_text(encoding="utf-8")
            existing_content += "\n\n---\n\n"
        
        reflection_file.write_text(existing_content + reflection, encoding="utf-8")
        
        log_event(
            "wake_ritual",
            "Morning reflection written",
            {
                "reflection_file": str(reflection_file),
                "reflection_length": len(reflection),
            }
        )
    
    def run_cycle_loop(self, tick_interval: float = 1.0) -> None:
        """
        Run the main sleep/wake cycle loop.
        
        This is the daemon mode entry point.
        In a real deployment this would run as a background process.
        
        Args:
            tick_interval: Seconds between cycle checks (default 1.0)
        """
        import time
        
        while True:
            self.tick()
            
            if self.is_sleeping:
                time.sleep(min(tick_interval, 10.0))
            else:
                time.sleep(tick_interval)
    
    def tick(self) -> str:
        """
        One tick of the cycle.
        
        Checks if state transition is needed and performs it.
        
        Returns:
            str: Current state ("awake" or "sleeping")
        """
        if self.is_awake and self.is_time_to_sleep():
            self.sleep()
        elif self.is_sleeping and self.is_time_to_wake():
            self.wake()
        
        self.state.increment_cycle()
        self.state.save()
        
        return self.state.sleep_state
    
    def force_wake(self) -> None:
        """
        Force wake the agent (e.g., from external trigger).
        
        Skips the sleep duration check.
        """
        self.wake()
    
    def force_sleep(self) -> None:
        """
        Force sleep the agent (e.g., from external trigger).
        
        Skips the wake duration check.
        """
        self.sleep()
    
    def get_cycle_status(self) -> dict:
        """
        Get current cycle status.
        
        Returns:
            dict: Status information including time in current state
        """
        now = datetime.now()
        
        if self.is_awake and self._awake_since:
            time_in_state = (now - self._awake_since).total_seconds()
            time_remaining = max(0, self.state.wake_duration_seconds - time_in_state)
        elif self.is_sleeping and self._sleeping_since:
            time_in_state = (now - self._sleeping_since).total_seconds()
            time_remaining = max(0, self.state.sleep_duration_seconds - time_in_state)
        else:
            time_in_state = 0
            time_remaining = 0
        
        return {
            "state": self.state.sleep_state,
            "time_in_state_seconds": time_in_state,
            "time_remaining_seconds": time_remaining,
            "wake_duration": self.state.wake_duration_seconds,
            "sleep_duration": self.state.sleep_duration_seconds,
            "total_cycles": self.state.total_cycles,
            "last_awakened": self.state.last_awakened.isoformat() if self.state.last_awakened else None,
            "last_slept": self.state.last_slept.isoformat() if self.state.last_slept else None,
        }


__all__ = ["SleepWakeCycle"]
