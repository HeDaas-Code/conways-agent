"""
Agent Mode State Machine

Manages agent modes: IDLE ↔ INTERACTION ↔ SELF
- IDLE: Initial state, no WS connection
- INTERACTION: WS connected, user may be present
- SELF: WS disconnected, agent operates autonomously

Handles WS lifecycle events and idle timeout.
Also manages BehaviorPool for autonomous behavior execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from agent.core.behavior_pool import BehaviorPool
from agent.core.behavior_scheduler import BehaviorScheduler, VaultContext


class Mode(Enum):
    """Agent operational modes."""
    IDLE = "idle"
    INTERACTION = "interaction"
    SELF = "self"


class WSConnectionState(Enum):
    """WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"


@dataclass
class ModeMachineState:
    """Full state of the mode machine."""
    mode: Mode = Mode.IDLE
    ws_connected: WSConnectionState = WSConnectionState.DISCONNECTED
    idle_timeout_seconds: int = 60
    last_activity_at: datetime = field(default_factory=datetime.now)
    last_tick_at: datetime = field(default_factory=datetime.now)
    tick_count: int = 0
    pending_actions: list[str] = field(default_factory=list)


# Valid transitions: (current_mode, event) -> new_mode
VALID_TRANSITIONS: dict[tuple[Mode, str], Mode] = {
    # WS lifecycle
    (Mode.IDLE, "ws_connect"): Mode.INTERACTION,
    (Mode.INTERACTION, "ws_disconnect"): Mode.SELF,
    (Mode.SELF, "ws_connect"): Mode.INTERACTION,
    # Timeout-based
    (Mode.INTERACTION, "idle_timeout"): Mode.SELF,
    # Self mode internal
    (Mode.SELF, "interest_threshold_reached"): Mode.SELF,
    # No-op cases
    (Mode.SELF, "ws_disconnect"): Mode.SELF,
}


class ModeMachine:
    """
    Reducer-style mode machine for Agent.

    Events:
        - ws_connect: Plugin connects to backend
        - ws_disconnect: Plugin closes Obsidian
        - idle_timeout: 60s inactivity in INTERACTION mode
        - tick: Time advancement (for timeout tracking)
        - interest_threshold_reached: Interest reached threshold in SELF mode

    States:
        - IDLE: Initial state, no WS connection
        - INTERACTION: WS connected, user may be present
        - SELF: WS disconnected, agent operates autonomously
    """

    def __init__(self) -> None:
        self.state = ModeMachineState()
        self._event_history: list[tuple[str, Mode, Mode]] = []
        self._interest_model: Optional["InterestModel"] = None
        self._behavior_pool: Optional[BehaviorPool] = None
        self._behavior_scheduler: Optional[BehaviorScheduler] = None
        self._vault_path: str = "/tmp/vault"  # Default vault path

    def set_interest_model(self, interest_model: "InterestModel") -> None:
        """
        Set the interest model for integration.

        Args:
            interest_model: The InterestModel instance to integrate
        """
        self._interest_model = interest_model

    def set_behavior_pool(self, vault_path: str = "/tmp/vault") -> BehaviorPool:
        """
        Initialize and set the behavior pool for autonomous behavior execution.

        Args:
            vault_path: Path to the vault directory for behavior outputs

        Returns:
            The created BehaviorPool instance
        """
        self._vault_path = vault_path
        self._behavior_pool = BehaviorPool()
        self._behavior_scheduler = BehaviorScheduler(self._behavior_pool)
        return self._behavior_pool

    def get_behavior_pool(self) -> Optional[BehaviorPool]:
        """Get the behavior pool if initialized."""
        return self._behavior_pool

    def get_behavior_scheduler(self) -> Optional[BehaviorScheduler]:
        """Get the behavior scheduler if initialized."""
        return self._behavior_scheduler

    def dispatch(self, event: str) -> tuple[Mode, list[str]]:
        """
        Process an event and return (new_mode, triggered_actions).

        Args:
            event: Event name (ws_connect | ws_disconnect | idle_timeout |
                    tick | interest_threshold_reached)

        Returns:
            (new_mode, list of triggered action names)
        """
        old_mode = self.state.mode

        key = (self.state.mode, event)
        if key not in VALID_TRANSITIONS:
            # No valid transition — stay in current mode
            self._record(old_mode, old_mode, event, valid=False)
            return self.state.mode, []

        new_mode = VALID_TRANSITIONS[key]
        self.state.mode = new_mode
        self._record(old_mode, new_mode, event, valid=True)

        # Handle side effects
        triggered_actions = self._handle_mode_entry(new_mode, old_mode)

        return new_mode, triggered_actions

    def _record(
        self, old_mode: Mode, new_mode: Mode, event: str, valid: bool
    ) -> None:
        # Only record valid transitions in history
        if valid:
            self._event_history.append((event, old_mode, new_mode))

    def _handle_mode_entry(
        self, new_mode: Mode, old_mode: Mode
    ) -> list[str]:
        """Handle actions triggered by entering a mode."""
        triggered: list[str] = []

        # No actions for no-op transitions
        if old_mode == new_mode:
            return triggered

        if new_mode == Mode.INTERACTION:
            self.state.last_activity_at = datetime.now()

        elif new_mode == Mode.SELF:
            if old_mode == Mode.INTERACTION:
                triggered.append("begin_self_reflection")
            else:
                triggered.append("continue_self_operations")

        return triggered

    def tick(self) -> list[str]:
        """
        Advance time by one minute tick.
        Checks for idle timeout in INTERACTION mode.
        In SELF mode, advances InterestModel tick for accumulation
        and checks for behavior triggers.

        Returns:
            List of triggered actions (empty if no transition)
        """
        self.state.tick_count += 1
        self.state.last_tick_at = datetime.now()

        if self.state.mode == Mode.INTERACTION:
            elapsed = (
                datetime.now() - self.state.last_activity_at
            ).total_seconds()
            if elapsed >= self.state.idle_timeout_seconds:
                return self.dispatch("idle_timeout")

        elif self.state.mode == Mode.SELF:
            # In SELF mode, tick the interest model for accumulation
            if self._interest_model is not None:
                self._interest_model.tick()

            # Check and trigger behaviors
            if self._behavior_pool is not None:
                points = self._interest_model.points if self._interest_model else 0
                self._behavior_pool.check_and_trigger(points)

        return []

    def record_activity(self) -> None:
        """Record user activity, resetting idle timer in INTERACTION mode."""
        self.state.last_activity_at = datetime.now()

    def get_state(self) -> ModeMachineState:
        """Return a copy of the current state."""
        return ModeMachineState(
            mode=self.state.mode,
            ws_connected=self.state.ws_connected,
            idle_timeout_seconds=self.state.idle_timeout_seconds,
            last_activity_at=self.state.last_activity_at,
            last_tick_at=self.state.last_tick_at,
            tick_count=self.state.tick_count,
            pending_actions=self.state.pending_actions.copy(),
        )

    def get_event_history(self) -> list[tuple[str, Mode, Mode]]:
        """Return copy of event transition history."""
        return self._event_history.copy()

    def set_ws_connected(self, connected: bool) -> None:
        """Manually set WS connection state (for TUI simulation)."""
        self.state.ws_connected = (
            WSConnectionState.CONNECTED if connected
            else WSConnectionState.DISCONNECTED
        )

    def get_pending_behaviors(self) -> list[str]:
        """
        Get pending behaviors from the interest model or behavior pool.

        Returns:
            List of pending behavior names, or empty list if no interest model
        """
        if self._interest_model is not None:
            return [b.name for b in self._interest_model.get_pending_behaviors()]
        if self._behavior_pool is not None:
            return [b.name for b in self._behavior_pool.get_pending()]
        return []

    def execute_pending_behavior(self, behavior_name: str) -> Optional["ExecutionResult"]:
        """
        Execute a pending behavior from the behavior pool.

        Args:
            behavior_name: Name of the behavior to execute

        Returns:
            ExecutionResult if successful, None if no behavior pool
        """
        if self._behavior_pool is None:
            return None
        return self._behavior_pool.execute(behavior_name, self._vault_path)

    def get_scheduling_prompt(self, vault_context: VaultContext) -> Optional[str]:
        """
        Get LLM scheduling prompt for pending behaviors.

        Args:
            vault_context: Current vault context for the prompt

        Returns:
            Scheduling prompt string, or None if no behavior pool
        """
        if self._behavior_scheduler is None or self._behavior_pool is None:
            return None

        points = self._interest_model.points if self._interest_model else 0
        pending = self._behavior_pool.get_pending()

        return self._behavior_scheduler.build_scheduling_prompt(
            pending, vault_context, points
        )


def reduce(state: ModeMachineState, event: str) -> ModeMachineState:
    """
    Pure reducer: (state, event) -> new_state

    Standalone reducer function for lifting into real codebase.
    """
    key = (state.mode, event)
    if key not in VALID_TRANSITIONS:
        return state

    new_mode = VALID_TRANSITIONS[key]
    new_state = ModeMachineState(
        mode=new_mode,
        ws_connected=state.ws_connected,
        idle_timeout_seconds=state.idle_timeout_seconds,
        last_activity_at=state.last_activity_at,
        last_tick_at=datetime.now(),
        tick_count=state.tick_count + 1,
        pending_actions=state.pending_actions.copy(),
    )
    return new_state
