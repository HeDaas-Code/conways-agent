"""
Behavior Pool - Preset autonomous behaviors with thresholds and costs.

Issue #38: Each behavior has:
- threshold: minimum points to trigger
- cost: points consumed when behavior executes
- cooldown_ticks: ticks before can trigger again
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Behavior:
    """A behavior that can be triggered by interest accumulation."""
    name: str
    description: str
    threshold: int
    cost: int
    cooldown_ticks: int = 0  # Ticks before can trigger again

    def __repr__(self) -> str:
        return f"Behavior({self.name}, threshold={self.threshold}, cost={self.cost})"


# Preset behavior pool
BEHAVIORS: dict[str, Behavior] = {
    "QUICK_ASSOCIATION": Behavior(
        name="QUICK_ASSOCIATION",
        description="Quick association of current topic with notes",
        threshold=10,
        cost=5,
        cooldown_ticks=3,
    ),
    "WORLD_FRAGMENT": Behavior(
        name="WORLD_FRAGMENT",
        description="Generate a world fragment from current interest vector",
        threshold=20,
        cost=15,
        cooldown_ticks=10,
    ),
    "EXPLORE_LINKS": Behavior(
        name="EXPLORE_LINKS",
        description="Explore note links related to top interests",
        threshold=40,
        cost=25,
        cooldown_ticks=15,
    ),
    "DEEP_REFLECTION": Behavior(
        name="DEEP_REFLECTION",
        description="Deep reflection on accumulated interests",
        threshold=60,
        cost=35,
        cooldown_ticks=20,
    ),
}


def get_behavior(name: str) -> Optional[Behavior]:
    """Get behavior by name."""
    return BEHAVIORS.get(name.upper())


def get_behaviors_by_threshold(threshold: int) -> list[Behavior]:
    """Get all behaviors that can trigger at given points."""
    return [b for b in BEHAVIORS.values() if b.threshold <= threshold]


def create_custom_behavior(
    name: str,
    threshold: int,
    cost: int,
    description: str = "",
    cooldown_ticks: int = 0,
) -> Behavior:
    """Create a custom behavior and add it to the pool."""
    behavior = Behavior(
        name=name.upper(),
        description=description or f"Custom behavior: {name}",
        threshold=threshold,
        cost=cost,
        cooldown_ticks=cooldown_ticks,
    )
    BEHAVIORS[name.upper()] = behavior
    return behavior
