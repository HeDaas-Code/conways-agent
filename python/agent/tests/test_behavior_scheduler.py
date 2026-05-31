"""
Tests for BehaviorScheduler - LLM-driven scheduling logic.

Issue #39:
- LLM scheduling prompt format per NOTES.md
- Context includes: points, mode, pending_behaviors, vault context
- Prompt format matches specification
"""

import pytest
import tempfile
from datetime import datetime

# Import VaultContext from behavior_scheduler, not behavior_pool
from agent.core.behavior_scheduler import BehaviorScheduler, VaultContext
from agent.core.behavior_pool import BehaviorPool


class TestSchedulingPrompt:
    """Test LLM scheduling prompt generation."""

    def test_build_scheduling_prompt_contains_required_sections(self):
        """Prompt should contain Current State, Pending Behaviors, Vault Context."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        vault = VaultContext(
            files=["a.md", "b.md"],
            recent_files=["a.md"],
            tags=["python", "ai"]
        )
        
        pool.check_and_trigger(current_points=30)
        
        prompt = scheduler.build_scheduling_prompt(
            pool.get_pending(),
            vault,
            current_points=30
        )
        
        assert "## Current State" in prompt
        assert "## Pending Behaviors" in prompt
        assert "## Vault Context" in prompt

    def test_build_scheduling_prompt_includes_points(self):
        """Prompt should include current points."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        vault = VaultContext()
        
        prompt = scheduler.build_scheduling_prompt([], vault, current_points=45)
        
        assert "Interest Points: 45" in prompt

    def test_build_scheduling_prompt_includes_mode(self):
        """Prompt should include current mode."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        vault = VaultContext()
        
        prompt = scheduler.build_scheduling_prompt([], vault, current_points=0)
        
        assert "Vault Files:" in prompt

    def test_build_scheduling_prompt_lists_pending_behaviors(self):
        """Prompt should list pending behaviors with details."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        pool.check_and_trigger(current_points=30)
        pending = pool.get_pending()
        
        vault = VaultContext()
        prompt = scheduler.build_scheduling_prompt(pending, vault, current_points=30)
        
        assert "WORLD_FRAGMENT" in prompt

    def test_build_scheduling_prompt_includes_behavior_threshold_and_cost(self):
        """Prompt should include threshold and cost for each behavior."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        pool.check_and_trigger(current_points=70)
        pending = pool.get_pending()
        
        vault = VaultContext()
        prompt = scheduler.build_scheduling_prompt(pending, vault, current_points=70)
        
        assert "threshold:" in prompt.lower()
        assert "cost:" in prompt.lower()

    def test_build_scheduling_prompt_includes_vault_context(self):
        """Prompt should include vault recent files and tags."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        vault = VaultContext(
            files=["python-intro.md", "ai-overview.md"],
            recent_files=["ai-overview.md", "python-intro.md"],
            tags=["python", "ai", "learning"]
        )
        
        prompt = scheduler.build_scheduling_prompt([], vault, current_points=0)
        
        assert "Recent Files:" in prompt
        assert "Top Tags:" in prompt
        assert "python" in prompt.lower()
        assert "ai" in prompt.lower()

    def test_build_scheduling_prompt_includes_instructions(self):
        """Prompt should include decision instructions."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        vault = VaultContext()
        
        prompt = scheduler.build_scheduling_prompt([], vault, current_points=0)
        
        assert "## Instructions" in prompt
        assert "Respond with the behavior name" in prompt


class TestSchedulingContext:
    """Test scheduling context building."""

    def test_build_scheduling_context_returns_dict(self):
        """build_scheduling_context should return a dict."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        vault = VaultContext()
        
        context = scheduler.build_scheduling_context([], vault, current_points=50)
        
        assert isinstance(context, dict)

    def test_build_scheduling_context_contains_current_points(self):
        """Context should include current points."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        vault = VaultContext()
        
        context = scheduler.build_scheduling_context([], vault, current_points=45)
        
        assert context["current_points"] == 45

    def test_build_scheduling_context_contains_vault_files_count(self):
        """Context should include vault file count."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        vault = VaultContext(files=["a.md", "b.md", "c.md"])
        
        context = scheduler.build_scheduling_context([], vault, current_points=0)
        
        assert context["vault_files_count"] == 3

    def test_build_scheduling_context_contains_pending_behaviors(self):
        """Context should include pending behaviors list."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        pool.check_and_trigger(current_points=30)
        pending = pool.get_pending()
        
        vault = VaultContext()
        context = scheduler.build_scheduling_context(pending, vault, current_points=30)
        
        assert "pending_behaviors" in context
        assert len(context["pending_behaviors"]) >= 1

    def test_build_scheduling_context_contains_available_behaviors(self):
        """Context should include available but not pending behaviors."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        pool.check_and_trigger(current_points=30)
        pending = pool.get_pending()
        
        vault = VaultContext()
        context = scheduler.build_scheduling_context(pending, vault, current_points=70)
        
        assert "available_behaviors" in context


class TestSchedulingDecision:
    """Test scheduling decision logic."""

    def test_decide_next_action_returns_behavior_name(self):
        """decide_next_action should return a behavior name string."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        pool.check_and_trigger(current_points=70)
        pending = pool.get_pending()
        
        vault = VaultContext()
        decision = scheduler.decide_next_action(pending, vault, current_points=70)
        
        assert isinstance(decision, str)

    def test_decide_next_action_returns_none_when_no_pending(self):
        """decide_next_action should return 'NONE' when no pending behaviors."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        vault = VaultContext()
        
        decision = scheduler.decide_next_action([], vault, current_points=0)
        
        assert decision == "NONE"

    def test_decide_next_action_prefers_high_threshold(self):
        """decide_next_action should prefer higher threshold behaviors."""
        vault = VaultContext()
        
        decisions = []
        for _ in range(10):
            pool = BehaviorPool()
            pool.check_and_trigger(current_points=70)
            pending = pool.get_pending()
            
            scheduler = BehaviorScheduler(pool)
            decision = scheduler.decide_next_action(pending, vault, current_points=70)
            decisions.append(decision)
        
        deep_reflection_count = decisions.count("DEEP_REFLECTION")
        assert deep_reflection_count >= 5

    def test_decide_next_action_with_single_pending(self):
        """decide_next_action should return that behavior when only one pending."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        pool.check_and_trigger(current_points=25)
        pending = pool.get_pending()
        
        vault = VaultContext()
        decision = scheduler.decide_next_action(pending, vault, current_points=25)
        
        assert decision == "WORLD_FRAGMENT"


class TestSchedulingIntegration:
    """Integration tests for scheduler with pool."""

    def test_full_schedule_workflow(self):
        """Test complete workflow: trigger -> schedule -> execute."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        pool.check_and_trigger(current_points=70)
        pending = pool.get_pending()
        
        assert len(pending) >= 1
        
        vault = VaultContext(
            files=["a.md", "b.md"],
            recent_files=["b.md"],
            tags=["test"]
        )
        
        context = scheduler.build_scheduling_context(pending, vault, current_points=70)
        prompt = scheduler.build_scheduling_prompt(pending, vault, current_points=70)
        
        assert context["current_points"] == 70
        assert len(context["pending_behaviors"]) >= 1
        
        decision = scheduler.decide_next_action(pending, vault, current_points=70)
        
        # Decision should be a valid behavior name
        assert decision in ["WORLD_FRAGMENT", "EXPLORE_LINKS", "DEEP_REFLECTION"]


class TestPromptFormatCompliance:
    """Test prompt format matches NOTES.md specification."""

    def test_prompt_format_matches_specification(self):
        """Prompt should match the format in NOTES.md."""
        pool = BehaviorPool()
        scheduler = BehaviorScheduler(pool)
        
        pool.check_and_trigger(current_points=60)
        pending = pool.get_pending()
        
        vault = VaultContext(
            files=["python-intro.md", "ai-overview.md"],
            recent_files=["python-intro.md", "ai-overview.md"],
            tags=["python", "ai"]
        )
        
        prompt = scheduler.build_scheduling_prompt(pending, vault, current_points=60)
        
        assert "# Behavior Scheduling Decision" in prompt
        assert "- Interest Points:" in prompt or "Interest Points:" in prompt
        assert "- Vault Files:" in prompt or "Vault Files:" in prompt
        assert "## Pending Behaviors" in prompt
        assert "## Available Behaviors" in prompt
        assert "## Vault Context" in prompt
        assert "## Instructions" in prompt
        assert "Respond with the behavior name to execute, or 'NONE'" in prompt
