"""
Interest Model - Core logic for interest accumulation and behavior triggering.

Issue #38:
- Interest Vector: Dict mapping topics to their frequency/strength
- Interest Points: Scalar measure of overall interest level
- Pending Behaviors: Behaviors queued for execution when thresholds are met

Sources and their point mappings:
- dialogue: 5 + len(keywords) * 2 points
- vault_create: 3 points
- vault_edit: 2 points
- tag_use: 4 points
- link_establish: 3 points

Decay:
- In INTERACTION mode: -5 points per tick (min 0)
- In SELF mode: no decay
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from agent.core.interest_model_behaviors import Behavior, BEHAVIORS
from agent.core.interest_model_keywords import TopicExtractor


class Mode(Enum):
    """Agent operating mode."""
    INTERACTION = "interaction"
    SELF = "self"


# Decay configuration
DECAY_RATE_PER_TICK = 5
DECAY_RATE_SELF = 0  # No decay in SELF mode

# Decay rate for interest vector (5% decay per tick in INTERACTION mode)
VECTOR_DECAY_RATE = 0.95


# Point mappings per event type
POINTS_CONFIG: dict[str, int] = {
    "dialogue": 5,              # Base points for dialogue
    "dialogue_per_keyword": 2,   # Additional points per keyword
    "vault_create": 3,
    "vault_edit": 2,
    "tag_use": 4,
    "link_establish": 3,
}


@dataclass
class InterestVector:
    """
    Represents the agent's interest as a vector of topics.

    Each topic maps to a frequency count showing how often
    the topic has been encountered.
    """
    _topics: dict[str, int] = field(default_factory=dict)

    def add(self, topic: str, weight: float = 1.0) -> None:
        """Add weight to a topic."""
        current = self._topics.get(topic, 0)
        self._topics[topic] = int(current + weight)

    def add_many(self, topics: list[str], weight: float = 1.0) -> None:
        """Add multiple topics with the same weight."""
        for topic in topics:
            self.add(topic, weight)

    def get(self, topic: str) -> int:
        """Get frequency for a topic."""
        return self._topics.get(topic, 0)

    def top_n(self, n: int = 5) -> list[tuple[str, int]]:
        """Get top N topics by frequency."""
        sorted_topics = sorted(
            self._topics.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_topics[:n]

    def decay(self, rate: float = 0.9) -> None:
        """
        Decay all topic frequencies.

        Args:
            rate: Multiplicative decay rate (0.95 = 5% decay)
        """
        self._topics = {
            topic: max(0, int(freq * rate))
            for topic, freq in self._topics.items()
        }
        # Remove zero-frequency topics
        self._topics = {t: f for t, f in self._topics.items() if f > 0}

    def __len__(self) -> int:
        return len(self._topics)

    def __repr__(self) -> str:
        return f"InterestVector({self._topics})"


@dataclass
class BehaviorTrigger:
    """Represents a pending behavior trigger."""
    behavior: Behavior
    triggered_at: datetime = field(default_factory=datetime.now)
    cooldown_remaining: int = 0


@dataclass
class InterestModelState:
    """Complete state of the interest model."""
    points: int = 0
    mode: Mode = Mode.INTERACTION
    tick_count: int = 0
    interest_vector: InterestVector = field(default_factory=InterestVector)
    pending_behaviors: list[BehaviorTrigger] = field(default_factory=list)
    cooldown_tracker: dict[str, int] = field(default_factory=dict)  # behavior_name -> ticks remaining
    history: list[dict] = field(default_factory=list)  # Event log


class InterestModel:
    """
    Core interest accumulation model.

    Manages:
    - Points accumulation from various sources
    - Interest vector (topic frequencies)
    - Behavior triggering at thresholds
    - Decay in INTERACTION mode
    """

    def __init__(self, initial_mode: Mode = Mode.INTERACTION):
        """
        Initialize interest model.

        Args:
            initial_mode: Starting mode (default: INTERACTION)
        """
        self.state = InterestModelState(mode=initial_mode)
        self._topic_extractor = TopicExtractor()

    @property
    def points(self) -> int:
        """Current interest points."""
        return self.state.points

    @property
    def mode(self) -> Mode:
        """Current mode."""
        return self.state.mode

    @property
    def tick_count(self) -> int:
        """Number of ticks elapsed."""
        return self.state.tick_count

    # ==================== Source Event Handlers ====================

    def accumulate(
        self,
        source: str,
        event_data: Optional[dict] = None
    ) -> list[Behavior]:
        """
        Accumulate interest from a source event.

        Args:
            source: Event source type
            event_data: Optional additional data (e.g., message content)

        Returns:
            List of newly triggered behaviors
        """
        event_data = event_data or {}
        keywords: list[str] = []

        if source == "dialogue":
            message = event_data.get("message", "")
            keywords = self._topic_extractor.extract_keywords(message)
            points = POINTS_CONFIG["dialogue"] + len(keywords) * POINTS_CONFIG["dialogue_per_keyword"]
            self._add_to_vector(keywords)
            self._log_event("dialogue", {"message": message[:50], "keywords": keywords, "points": points})

        elif source == "vault_create":
            points = POINTS_CONFIG["vault_create"]
            self._log_event("vault_create", {"points": points})

        elif source == "vault_edit":
            points = POINTS_CONFIG["vault_edit"]
            self._log_event("vault_edit", {"points": points})

        elif source == "tag_use":
            tag = event_data.get("tag", "")
            # Try to extract topic from tag
            topics = self._topic_extractor.extract_keywords(tag)
            if topics:
                self._add_to_vector(topics)
            else:
                self._add_to_vector([tag])
            points = POINTS_CONFIG["tag_use"]
            self._log_event("tag_use", {"tag": tag, "keywords": topics, "points": points})

        elif source == "link_establish":
            target = event_data.get("target", "")
            topics = self._topic_extractor.extract_keywords(target)
            self._add_to_vector(topics)
            points = POINTS_CONFIG["link_establish"]
            self._log_event("link_establish", {"target": target, "keywords": topics, "points": points})

        else:
            points = 0

        self.state.points += points
        return self._check_and_queue_behaviors()

    def extract_topic(self, message: str) -> list[str]:
        """
        Extract topics from a message.

        Args:
            message: Input message text

        Returns:
            List of extracted topic keywords
        """
        return self._topic_extractor.extract_keywords(message)

    # ==================== Time & Mode ====================

    def tick(self) -> list[Behavior]:
        """
        Advance time by one minute.

        In INTERACTION mode: decay points and interest vector
        In SELF mode: just increment tick counter

        Returns:
            List of newly triggered behaviors
        """
        self.state.tick_count += 1

        if self.state.mode == Mode.INTERACTION:
            # Decay points
            self.state.points = max(0, self.state.points - DECAY_RATE_PER_TICK)
            # Decay interest vector
            self.state.interest_vector.decay(rate=VECTOR_DECAY_RATE)
            # Decay cooldowns
            self._decay_cooldowns()
            self._log_event("tick_decay", {"points_lost": DECAY_RATE_PER_TICK})
        else:
            # SELF mode: just tick, no decay
            self._log_event("tick_passive", {})

        return self._check_and_queue_behaviors()

    def set_mode(self, mode: Mode) -> None:
        """
        Change the operating mode.

        Args:
            mode: New mode to set
        """
        old_mode = self.state.mode
        self.state.mode = mode
        self._log_event("mode_change", {"from": old_mode.value, "to": mode.value})

    def set_mode_by_name(self, mode_name: str) -> bool:
        """
        Set mode by name string.

        Args:
            mode_name: "interaction" or "self"

        Returns:
            True if mode was set, False if invalid name
        """
        try:
            mode = Mode(mode_name.lower())
            self.set_mode(mode)
            return True
        except ValueError:
            return False

    # ==================== Behavior Management ====================

    def get_pending_behaviors(self) -> list[Behavior]:
        """
        Get list of pending (queued) behaviors.

        Returns:
            List of Behavior objects waiting to be executed
        """
        return [trigger.behavior for trigger in self.state.pending_behaviors]

    def execute_behavior(self, behavior_name: str) -> bool:
        """
        Execute a pending behavior (consume it).

        Args:
            behavior_name: Name of behavior to execute

        Returns:
            True if behavior was executed, False if not pending or in cooldown
        """
        # Find the trigger
        trigger = None
        for t in self.state.pending_behaviors:
            if t.behavior.name == behavior_name:
                trigger = t
                break

        if not trigger:
            return False

        # Deduct cost
        self.state.points = max(0, self.state.points - trigger.behavior.cost)

        # Set cooldown
        self.state.cooldown_tracker[behavior_name] = trigger.behavior.cooldown_ticks

        # Remove from pending
        self.state.pending_behaviors.remove(trigger)

        # Decay interest vector after behavior execution
        self.state.interest_vector.decay(rate=0.8)

        self._log_event("behavior_executed", {
            "name": behavior_name,
            "cost": trigger.behavior.cost,
            "cooldown": trigger.behavior.cooldown_ticks
        })

        return True

    # ==================== Display Helpers ====================

    def get_interest_summary(self) -> dict:
        """Get a summary of current interest state."""
        top_topics = self.state.interest_vector.top_n(5)
        return {
            "points": self.state.points,
            "mode": self.state.mode.value,
            "tick": self.state.tick_count,
            "top_topics": top_topics,
            "pending_behaviors": [t.behavior.name for t in self.state.pending_behaviors],
            "active_cooldowns": {
                name: ticks
                for name, ticks in self.state.cooldown_tracker.items()
                if ticks > 0
            }
        }

    def format_display(self) -> str:
        """Format the current state for display."""
        summary = self.get_interest_summary()

        lines = []
        lines.append("=" * 50)
        lines.append(f"[状态] Points: {summary['points']} | Mode: {summary['mode'].upper()} | Tick: {summary['tick']}")
        lines.append("-" * 50)

        # Interest vector
        lines.append("兴趣向量 (Top 5):")
        if summary['top_topics']:
            for topic, freq in summary['top_topics']:
                bar = "█" * min(freq, 20)
                lines.append(f"  {topic:12s} {freq:3d} {bar}")
        else:
            lines.append("  (空)")

        lines.append("-" * 50)

        # Pending behaviors
        if summary['pending_behaviors']:
            lines.append(f"待触发行为: {', '.join(summary['pending_behaviors'])}")
        else:
            lines.append("待触发行为: (无)")

        # Active cooldowns
        if summary['active_cooldowns']:
            cooldowns_str = ", ".join(
                f"{name}({ticks})" for name, ticks in summary['active_cooldowns'].items()
            )
            lines.append(f"冷却中: {cooldowns_str}")

        lines.append("=" * 50)
        return "\n".join(lines)

    # ==================== Private Methods ====================

    def _add_to_vector(self, topics: list[str], weight: float = 1.0) -> None:
        """Add topics to interest vector."""
        for topic in topics:
            self.state.interest_vector.add(topic, weight)

    def _check_and_queue_behaviors(self) -> list[Behavior]:
        """
        Check thresholds and queue any newly triggered behaviors.

        Returns:
            List of newly triggered behaviors
        """
        newly_triggered: list[Behavior] = []

        for behavior in BEHAVIORS.values():
            # Skip if already pending
            if any(t.behavior.name == behavior.name for t in self.state.pending_behaviors):
                continue

            # Skip if in cooldown
            if self.state.cooldown_tracker.get(behavior.name, 0) > 0:
                continue

            # Check threshold
            if self.state.points >= behavior.threshold:
                trigger = BehaviorTrigger(behavior=behavior)
                self.state.pending_behaviors.append(trigger)
                newly_triggered.append(behavior)
                self._log_event("behavior_queued", {"name": behavior.name, "threshold": behavior.threshold})

        return newly_triggered

    def _decay_cooldowns(self) -> None:
        """Decrement all active cooldowns."""
        for name in self.state.cooldown_tracker:
            if self.state.cooldown_tracker[name] > 0:
                self.state.cooldown_tracker[name] -= 1

    def _log_event(self, event_type: str, data: dict) -> None:
        """Log an event to history."""
        self.state.history.append({
            "type": event_type,
            "data": data,
            "tick": self.state.tick_count,
            "timestamp": datetime.now().isoformat()
        })
