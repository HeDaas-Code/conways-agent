"""
BehaviorPool - Preset autonomous behaviors with thresholds, costs, and execution logic.

Issue #39:
- Behavior: A preset action with threshold, cost, cooldown_minutes
- BehaviorPool: Manages registered behaviors and execution state
- Execution: Write results to Vault following specification

Key design decisions from NOTES.md:
1. Execution timing: Threshold-triggered + LLM control batch execution
2. Vault writeback: Structured markdown with frontmatter
3. Cooldown: Minutes-based cooldown prevents re-triggering
"""

from __future__ import annotations

import copy
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


# ==================== Data Models ====================

@dataclass
class Behavior:
    """A behavior that can be triggered by interest accumulation."""
    name: str
    description: str
    threshold: int           # Points needed to trigger
    cost: int                # Points consumed when executed
    cooldown_minutes: int    # Minutes before can trigger again
    executor: Optional[Callable] = None  # Function to execute

    def __repr__(self) -> str:
        return f"Behavior({self.name}, threshold={self.threshold}, cost={self.cost})"


@dataclass
class ExecutionResult:
    """Result of behavior execution."""
    behavior_name: str
    success: bool
    output_path: Optional[str] = None
    content: str = ""
    error: Optional[str] = None
    executed_at: datetime = field(default_factory=datetime.now)


@dataclass
class BehaviorState:
    """Runtime state for a behavior."""
    last_triggered: Optional[datetime] = None
    execution_count: int = 0
    total_cost_spent: int = 0


# ==================== Vault Writer ====================

def _generate_vault_filename(behavior_name: str) -> str:
    """Generate a unique filename following Vault spec."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_id = str(uuid.uuid4())[:6]
    # Convert behavior name to kebab-case
    kebab_name = behavior_name.lower().replace("_", "-")
    return f"{kebab_name}_{timestamp}_{short_id}.md"


def _write_vault_file(
    behavior: Behavior,
    content: str,
    topics: list[str],
    vault_path: str
) -> tuple[str, str]:
    """
    Write behavior result to vault following specification.
    
    Vault path: vault/agent/world/{behavior}_{timestamp}_{uuid}.md
    
    Returns:
        (full_path, filename)
    """
    # Ensure vault directory structure
    vault_dir = Path(vault_path) / "vault" / "agent" / "world"
    vault_dir.mkdir(parents=True, exist_ok=True)
    
    filename = _generate_vault_filename(behavior.name)
    filepath = vault_dir / filename
    
    # Build frontmatter per spec
    type_mapping = {
        "WORLD_FRAGMENT": "world-fragment",
        "EXPLORE_LINKS": "link-exploration", 
        "DEEP_REFLECTION": "deep-reflection",
    }
    frontmatter_type = type_mapping.get(behavior.name, behavior.name.lower())
    
    frontmatter_lines = [
        "---",
        f"type: {frontmatter_type}",
        f"behavior: {behavior.name}",
        f"topics:",
    ]
    for topic in topics:
        frontmatter_lines.append(f"  - {topic}")
    frontmatter_lines.extend([
        f"triggered_by: threshold",
        f"timestamp: {datetime.now().isoformat()}",
        "---",
        "",
    ])
    
    # Write file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(frontmatter_lines))
        f.write(content)
    
    return str(filepath), filename


# ==================== BehaviorPool ====================

class BehaviorPool:
    """
    Manages registered behaviors and their execution lifecycle.
    
    Preset behaviors (from NOTES.md):
    - WORLD_FRAGMENT: threshold=20, cost=20, cooldown=60min
    - EXPLORE_LINKS: threshold=40, cost=30, cooldown=120min
    - DEEP_REFLECTION: threshold=60, cost=40, cooldown=180min
    """

    PRESET_BEHAVIORS = {
        "WORLD_FRAGMENT": Behavior(
            name="WORLD_FRAGMENT",
            description="Generate a world fragment from current interest vector",
            threshold=20,
            cost=20,
            cooldown_minutes=60,
        ),
        "EXPLORE_LINKS": Behavior(
            name="EXPLORE_LINKS",
            description="Explore note links related to top interests",
            threshold=40,
            cost=30,
            cooldown_minutes=120,
        ),
        "DEEP_REFLECTION": Behavior(
            name="DEEP_REFLECTION",
            description="Deep reflection on accumulated interests",
            threshold=60,
            cost=40,
            cooldown_minutes=180,
        ),
    }

    def __init__(self):
        self.behaviors: dict[str, Behavior] = {}
        self.state: dict[str, BehaviorState] = {}
        self.pending: list[str] = []  # Behaviors waiting to execute
        
        # Register preset behaviors (copy to avoid shared state)
        for name, behavior in self.PRESET_BEHAVIORS.items():
            # Use copy to ensure each pool has its own behavior instances
            self.register_behavior(copy.deepcopy(behavior))

    def register_behavior(
        self,
        behavior: Behavior,
        executor: Optional[Callable] = None
    ) -> None:
        """Register a behavior with an optional executor."""
        self.behaviors[behavior.name] = behavior
        if executor:
            self.behaviors[behavior.name].executor = executor
        self.state[behavior.name] = BehaviorState()

    def get_behavior(self, name: str) -> Optional[Behavior]:
        """Get behavior by name."""
        return self.behaviors.get(name.upper())

    def get_behavior_state(self, name: str) -> Optional[BehaviorState]:
        """Get execution state for a behavior."""
        return self.state.get(name.upper())

    def get_available_behaviors(self, current_points: int) -> list[Behavior]:
        """Get all behaviors that can be triggered at current points."""
        available = []
        for name, behavior in self.behaviors.items():
            state = self.state[name]

            # Check cooldown
            if state.last_triggered:
                elapsed = (datetime.now() - state.last_triggered).total_seconds() / 60
                if elapsed < behavior.cooldown_minutes:
                    continue

            # Check threshold
            if current_points >= behavior.threshold:
                available.append(behavior)

        return available

    def check_and_trigger(self, current_points: int) -> list[Behavior]:
        """
        Check thresholds and return behaviors ready to execute.

        Returns list of behaviors that have met their thresholds
        and are not in cooldown.
        """
        triggered = []
        for behavior in self.get_available_behaviors(current_points):
            if behavior.name not in self.pending:
                self.pending.append(behavior.name)
                triggered.append(behavior)

        return triggered

    def get_pending(self) -> list[Behavior]:
        """Get list of pending behaviors."""
        return [self.behaviors[name] for name in self.pending if name in self.behaviors]

    def execute(self, behavior_name: str, vault_path: str) -> ExecutionResult:
        """
        Execute a behavior and write result to Vault.
        
        Args:
            behavior_name: Name of behavior to execute
            vault_path: Base path for vault directory
            
        Returns:
            ExecutionResult with success status and output path
        """
        name = behavior_name.upper()
        behavior = self.get_behavior(name)
        
        if not behavior:
            return ExecutionResult(
                behavior_name=name,
                success=False,
                error=f"Behavior '{name}' not found"
            )
        
        # Mark as pending removal
        self.mark_executed(name)
        
        # Execute if executor available, otherwise generate default content
        if behavior.executor:
            content = behavior.executor()
        else:
            content = self._generate_default_content(behavior)
        
        # Write to vault
        output_path, _ = _write_vault_file(
            behavior=behavior,
            content=content,
            topics=["interest-driven"],  # Default topics
            vault_path=vault_path
        )
        
        # Update state with cost
        self.state[name].total_cost_spent += behavior.cost
        
        return ExecutionResult(
            behavior_name=name,
            success=True,
            output_path=output_path,
            content=content,
        )

    def _generate_default_content(self, behavior: Behavior) -> str:
        """Generate default content for a behavior."""
        templates = {
            "WORLD_FRAGMENT": """## World Fragment

### Generated from Interest Vector

This world fragment captures insights from recent interest accumulation.

### Key Observations
- Interest-driven content generation
- Pattern recognition across topics

### Connections
- Related to current interest vector
- Connects multiple knowledge domains

### Reflection
The agent has generated this fragment based on accumulated interests.
""",
            "EXPLORE_LINKS": """## Link Exploration Report

### Explored Connections

Analyzed note links related to current interests.

### Discovery Summary
Found connections between notes based on interest patterns.

### Recommendations
1. Strengthen existing connections
2. Explore weak ties
3. Consider bridging nodes
""",
            "DEEP_REFLECTION": """## Deep Reflection

### Interest Trajectory
Reflecting on accumulated interest patterns.

### Core Themes
1. Primary focus areas identified
2. Secondary but significant patterns
3. Emerging patterns detected

### Knowledge Gaps
- Areas requiring further exploration
- Questions that remain unanswered

### Action Items
- [ ] Follow up on primary themes
- [ ] Research secondary connections
- [ ] Document findings
""",
        }
        return templates.get(
            behavior.name,
            f"## {behavior.name}\n\nBehavior executed at {datetime.now().isoformat()}"
        )

    def mark_executed(self, behavior_name: str) -> None:
        """Mark a behavior as executed."""
        name = behavior_name.upper()
        if name in self.pending:
            self.pending.remove(name)

        if name in self.state:
            self.state[name].last_triggered = datetime.now()
            self.state[name].execution_count += 1

    def in_cooldown(self, behavior_name: str) -> bool:
        """Check if behavior is in cooldown."""
        name = behavior_name.upper()
        behavior = self.get_behavior(name)
        if not behavior:
            return False

        state = self.state.get(name)
        if not state or not state.last_triggered:
            return False

        elapsed = (datetime.now() - state.last_triggered).total_seconds() / 60
        return elapsed < behavior.cooldown_minutes

    def get_cooldown_remaining(self, behavior_name: str) -> int:
        """Get remaining cooldown in minutes."""
        name = behavior_name.upper()
        behavior = self.get_behavior(name)
        if not behavior:
            return 0

        state = self.state.get(name)
        if not state or not state.last_triggered:
            return 0

        elapsed = (datetime.now() - state.last_triggered).total_seconds() / 60
        remaining = behavior.cooldown_minutes - elapsed
        return max(0, int(remaining))

    def get_status(self) -> dict:
        """Get status of all behaviors."""
        statuses = []
        for name, behavior in self.behaviors.items():
            state = self.state[name]
            cooldown = self.get_cooldown_remaining(name)

            statuses.append({
                "name": name,
                "threshold": behavior.threshold,
                "cost": behavior.cost,
                "cooldown_minutes": behavior.cooldown_minutes,
                "cooldown_remaining": cooldown,
                "in_pending": name in self.pending,
                "last_triggered": state.last_triggered.isoformat() if state.last_triggered else None,
                "execution_count": state.execution_count,
            })

        return {
            "pending": self.pending.copy(),
            "behaviors": statuses,
        }


# ==================== Demo ====================

if __name__ == "__main__":
    pool = BehaviorPool()

    print("=== Behavior Pool Demo ===\n")

    # Check available behaviors at different points
    for points in [0, 20, 40, 60]:
        available = pool.get_available_behaviors(points)
        print(f"Points: {points} -> Available: {[b.name for b in available]}")

    # Trigger some behaviors
    print("\n=== Triggering behaviors ===")
    triggered = pool.check_and_trigger(60)
    print(f"Triggered: {[b.name for b in triggered]}")
    print(f"Pending: {pool.pending}")

    # Status
    print("\n=== Status ===")
    status = pool.get_status()
    print(f"Pending: {status['pending']}")
    for b in status['behaviors']:
        print(f"  {b['name']}: cooldown={b['cooldown_remaining']}min")
