"""
BehaviorScheduler - LLM-driven scheduling interface.

Issue #39:
- build_scheduling_context(): Build context dict for LLM
- build_scheduling_prompt(): Generate prompt per NOTES.md specification
- decide_next_action(): Mock LLM scheduling decision

LLM Scheduling prompt format (from NOTES.md):
```
当前状态：
- 积分: {points}
- 模式: {mode}
- 待触发行为: {pending_behaviors}
- Vault 最近活动: {recent_activity}

请选择一个行为执行，或选择"不执行"。
```
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Optional

from agent.core.behavior_pool import Behavior, BehaviorPool


# ==================== Vault Context ====================

@dataclass
class VaultContext:
    """Context about the Vault for behavior execution."""
    files: list[str] = field(default_factory=list)
    links: dict[str, list[str]] = field(default_factory=dict)
    recent_files: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


# ==================== BehaviorScheduler ====================

class BehaviorScheduler:
    """
    LLM-driven behavior scheduling.
    
    Provides structured context for LLM to make scheduling decisions.
    """

    def __init__(self, pool: BehaviorPool):
        """
        Initialize scheduler with a behavior pool.
        
        Args:
            pool: BehaviorPool instance to schedule behaviors from
        """
        self.pool = pool

    def build_scheduling_context(
        self,
        pending_behaviors: list[Behavior],
        vault_context: VaultContext,
        current_points: int
    ) -> dict:
        """
        Build context dictionary for LLM scheduling decision.

        Returns structured data that can be used to construct a prompt.
        """
        context = {
            "current_points": current_points,
            "vault_files_count": len(vault_context.files),
            "vault_recent_files": vault_context.recent_files[:5],
            "vault_tags": vault_context.tags[:10],
            "pending_behaviors": [],
            "available_behaviors": [],
            "behavior_details": {},
        }

        # Pending behaviors details
        for behavior in pending_behaviors:
            context["pending_behaviors"].append({
                "name": behavior.name,
                "threshold": behavior.threshold,
                "cost": behavior.cost,
                "description": behavior.description,
            })
            context["behavior_details"][behavior.name] = behavior.description

        # Available but not pending
        for behavior in self.pool.get_available_behaviors(current_points):
            if behavior.name not in [b.name for b in pending_behaviors]:
                context["available_behaviors"].append({
                    "name": behavior.name,
                    "threshold": behavior.threshold,
                    "cost": behavior.cost,
                    "description": behavior.description,
                })

        return context

    def build_scheduling_prompt(
        self,
        pending_behaviors: list[Behavior],
        vault_context: VaultContext,
        current_points: int
    ) -> str:
        """
        Build a prompt for LLM to decide next action.
        
        The prompt includes:
        1. Current system state (points, vault files)
        2. Pending behaviors with details
        3. Available behaviors
        4. Vault context
        5. Instructions for decision making
        """
        context = self.build_scheduling_context(
            pending_behaviors, vault_context, current_points
        )

        lines = [
            "# Behavior Scheduling Decision",
            "",
            "## Current State",
            f"- Interest Points: {context['current_points']}",
            f"- Vault Files: {context['vault_files_count']}",
            "",
            "## Pending Behaviors (ready to execute)",
        ]

        if context["pending_behaviors"]:
            for b in context["pending_behaviors"]:
                lines.append(f"- **{b['name']}** (threshold: {b['threshold']}, cost: {b['cost']})")
                lines.append(f"  - {b['description']}")
        else:
            lines.append("- (none)")

        lines.extend([
            "",
            "## Available Behaviors (threshold met but not pending)",
        ])

        if context["available_behaviors"]:
            for b in context["available_behaviors"]:
                lines.append(f"- **{b['name']}** (threshold: {b['threshold']}, cost: {b['cost']})")
        else:
            lines.append("- (none)")

        lines.extend([
            "",
            "## Vault Context",
            f"- Recent Files: {', '.join(context['vault_recent_files']) or '(none)'}",
            f"- Top Tags: {', '.join(context['vault_tags']) or '(none)'}",
            "",
            "## Instructions",
            "Based on the current interest state and vault context, decide which behavior to execute next.",
            "Consider:",
            "1. Cost vs. benefit: higher threshold behaviors are typically more valuable",
            "2. Cooldowns: behaviors in cooldown cannot be triggered again",
            "3. Vault state: behaviors should be relevant to recent activity",
            "",
            "Respond with the behavior name to execute, or 'NONE' if no action is appropriate.",
        ])

        return "\n".join(lines)

    def decide_next_action(
        self,
        pending_behaviors: list[Behavior],
        vault_context: VaultContext,
        current_points: int
    ) -> str:
        """
        Mock LLM scheduling decision.
        
        In production, this would call an actual LLM.
        For prototyping, we use a simple heuristic:
        - Prefer highest-value pending behavior
        - Consider vault context relevance
        """
        if not pending_behaviors:
            return "NONE"

        # Sort by threshold (descending) to prefer higher-value behaviors
        sorted_behaviors = sorted(
            pending_behaviors,
            key=lambda b: b.threshold,
            reverse=True
        )

        # Mock: randomly select from top behaviors (simulating LLM reasoning)
        top_threshold = sorted_behaviors[0].threshold
        top_behaviors = [b for b in sorted_behaviors if b.threshold >= top_threshold * 0.8]

        selected = random.choice(top_behaviors)
        return selected.name


# ==================== Demo ====================

if __name__ == "__main__":
    from agent.core.behavior_pool import BehaviorPool

    pool = BehaviorPool()
    scheduler = BehaviorScheduler(pool)

    print("=== Scheduler Demo ===\n")

    # Build context at different points
    for points in [0, 25, 50, 70]:
        print(f"--- Points: {points} ---")
        
        pending = pool.check_and_trigger(points)
        
        vault = VaultContext(
            files=["python-intro.md", "ai-overview.md", "learning-notes.md"],
            recent_files=["ai-overview.md", "python-intro.md"],
            tags=["python", "ai", "learning"]
        )
        
        context = scheduler.build_scheduling_context(pending, vault, points)
        print(f"Pending: {[b['name'] for b in context['pending_behaviors']]}")
        print(f"Available: {[b['name'] for b in context['available_behaviors']]}")
        
        decision = scheduler.decide_next_action(pending, vault, points)
        print(f"Decision: {decision}")
        print()
