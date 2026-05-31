"""
Interest Accumulator

Manages interest points for autonomous behavior triggering.
Interest accumulates from dialogue and vault events.
Interest decays in INTERACTION mode but is preserved in SELF mode.

Pure state machine — call tick(), add_dialogue(), add_vault_event(),
decay(), then check pending_actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from agent.core.mode_machine import Mode


EventSource = Literal["dialogue", "vault_event", "metadata", "tick"]


# Decay rate: 5 points per minute in INTERACTION mode
DECAY_RATE_PER_MINUTE = 5

# Points awarded per event type
POINTS_PER_TICK = 1
POINTS_PER_DIALOGUE = 5
POINTS_PER_VAULT_EVENT = 3


class AutonomousAction(Enum):
    """Autonomous behaviors triggered by interest thresholds."""
    GENERATE_WORLD_FRAGMENT = "generate_world_fragment"
    EXPLORE_NOTE_LINKS = "explore_note_links"
    DEEP_REFLECTION = "deep_reflection"


@dataclass
class InterestState:
    """Interest accumulation state."""
    points: int = 0
    last_accumulated_at: datetime = field(default_factory=datetime.now)
    sources: list[EventSource] = field(default_factory=list)
    pending_actions: list[AutonomousAction] = field(default_factory=list)
    tick_count: int = 0
    mode: "Mode | None" = None  # Current mode for decay context

    # Thresholds
    WORLD_FRAGMENT_THRESHOLD: int = 20
    EXPLORE_LINKS_THRESHOLD: int = 40


@dataclass
class InterestAccumulator:
    """
    Accumulates interest from various sources and triggers
    autonomous behaviors at thresholds.

    In INTERACTION mode, interest decays over time.
    In SELF mode, interest is preserved (no decay).
    """

    state: InterestState = field(default_factory=InterestState)

    def decay(self, mode: "Mode") -> list[AutonomousAction]:
        """
        Apply decay to interest points based on mode.
        Only decays in INTERACTION mode.

        Args:
            mode: Current mode of the agent

        Returns:
            List of newly triggered actions (may be empty)
        """
        if mode.value == "interaction":
            self.state.points = max(0, self.state.points - DECAY_RATE_PER_MINUTE)
        
        self.state.mode = mode
        return self._check_thresholds()

    def tick(self) -> list[AutonomousAction]:
        """
        Advance time by one minute. Adds passive interest.

        Returns:
            List of newly triggered actions (may be empty)
        """
        self.state.tick_count += 1
        self.state.points += POINTS_PER_TICK
        self.state.last_accumulated_at = datetime.now()
        self.state.sources.append("tick")  # type: ignore

        return self._check_thresholds()

    def add_dialogue(self, topic: str = "") -> list[AutonomousAction]:
        """
        Record a dialogue interaction.

        Args:
            topic: Optional topic string (ignored in prototype)

        Returns:
            List of newly triggered actions
        """
        self.state.points += POINTS_PER_DIALOGUE
        self.state.last_accumulated_at = datetime.now()
        self.state.sources.append("dialogue")  # type: ignore

        return self._check_thresholds()

    def add_vault_event(self) -> list[AutonomousAction]:
        """
        Record a vault file change event.

        Returns:
            List of newly triggered actions
        """
        self.state.points += POINTS_PER_VAULT_EVENT
        self.state.last_accumulated_at = datetime.now()
        self.state.sources.append("vault_event")  # type: ignore

        return self._check_thresholds()

    def _check_thresholds(self) -> list[AutonomousAction]:
        """
        Check if any threshold is met and queue corresponding action.
        Each action triggers only once until consumed.

        Returns:
            List of newly triggered actions
        """
        triggered: list[AutonomousAction] = []

        if (
            self.state.points >= InterestState.WORLD_FRAGMENT_THRESHOLD
            and AutonomousAction.GENERATE_WORLD_FRAGMENT
            not in self.state.pending_actions
        ):
            triggered.append(AutonomousAction.GENERATE_WORLD_FRAGMENT)
            self.state.pending_actions.append(
                AutonomousAction.GENERATE_WORLD_FRAGMENT
            )

        if (
            self.state.points >= InterestState.EXPLORE_LINKS_THRESHOLD
            and AutonomousAction.EXPLORE_NOTE_LINKS
            not in self.state.pending_actions
        ):
            triggered.append(AutonomousAction.EXPLORE_NOTE_LINKS)
            self.state.pending_actions.append(
                AutonomousAction.EXPLORE_NOTE_LINKS
            )

        return triggered

    def consume_action(
        self, action: AutonomousAction
    ) -> bool:
        """
        Consume (remove) a pending action after execution.

        Args:
            action: The action to consume

        Returns:
            True if action was pending and now removed, False otherwise
        """
        if action in self.state.pending_actions:
            self.state.pending_actions.remove(action)
            return True
        return False

    def consume_all_actions(self) -> list[AutonomousAction]:
        """Consume all pending actions. Returns the list that was pending."""
        consumed = self.state.pending_actions.copy()
        self.state.pending_actions.clear()
        return consumed

    def reset(self) -> None:
        """Reset interest state (e.g., when entering INTERACTION mode)."""
        self.state = InterestState()

    def get_state(self) -> InterestState:
        """Return a copy of current interest state."""
        return InterestState(
            points=self.state.points,
            last_accumulated_at=self.state.last_accumulated_at,
            sources=self.state.sources.copy(),
            pending_actions=self.state.pending_actions.copy(),
            tick_count=self.state.tick_count,
            mode=self.state.mode,
        )

    def get_pending_actions(self) -> list[AutonomousAction]:
        """Return copy of pending actions."""
        return self.state.pending_actions.copy()
