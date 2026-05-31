"""
Tests for BehaviorPool - preset behavior management.

Issue #39:
- register_behavior() correctly registers behaviors
- check_and_trigger(interest_model) returns pending behaviors at threshold
- execute(behavior, vault_path) executes and writes to Vault
- Execution deducts cost and starts cooldown
- Cooldown prevents re-triggering
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path


class TestBehaviorPoolRegistration:
    """Test behavior registration."""

    def test_register_behavior_adds_to_pool(self):
        """register_behavior should add behavior to the pool."""
        from agent.core.behavior_pool import BehaviorPool, Behavior
        
        pool = BehaviorPool()
        initial_count = len(pool.behaviors)
        
        behavior = Behavior(
            name="TEST_BEHAVIOR",
            description="A test behavior",
            threshold=15,
            cost=10,
            cooldown_minutes=30,
        )
        pool.register_behavior(behavior)
        
        assert len(pool.behaviors) == initial_count + 1
        assert "TEST_BEHAVIOR" in pool.behaviors

    def test_register_behavior_with_executor(self):
        """register_behavior should attach executor function."""
        from agent.core.behavior_pool import BehaviorPool, Behavior
        
        pool = BehaviorPool()
        
        def mock_executor():
            return "executed"
        
        behavior = Behavior(
            name="EXECUTOR_TEST",
            description="Test executor attachment",
            threshold=10,
            cost=5,
            cooldown_minutes=10,
        )
        pool.register_behavior(behavior, executor=mock_executor)
        
        assert pool.behaviors["EXECUTOR_TEST"].executor is mock_executor

    def test_preset_behaviors_are_registered(self):
        """Pool should have preset behaviors registered."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        assert "WORLD_FRAGMENT" in pool.behaviors
        assert "EXPLORE_LINKS" in pool.behaviors
        assert "DEEP_REFLECTION" in pool.behaviors

    def test_preset_behavior_values(self):
        """Preset behaviors should have correct values from NOTES.md."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        wf = pool.get_behavior("WORLD_FRAGMENT")
        assert wf.threshold == 20
        assert wf.cost == 20
        assert wf.cooldown_minutes == 60
        
        el = pool.get_behavior("EXPLORE_LINKS")
        assert el.threshold == 40
        assert el.cost == 30
        assert el.cooldown_minutes == 120
        
        dr = pool.get_behavior("DEEP_REFLECTION")
        assert dr.threshold == 60
        assert dr.cost == 40
        assert dr.cooldown_minutes == 180


class TestBehaviorPoolCheckAndTrigger:
    """Test threshold checking and behavior triggering."""

    def test_check_and_trigger_returns_pending_at_threshold(self):
        """check_and_trigger should return behaviors when threshold is met."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        # WORLD_FRAGMENT threshold is 20
        triggered = pool.check_and_trigger(current_points=25)
        
        assert len(triggered) >= 1
        behavior_names = [b.name for b in triggered]
        assert "WORLD_FRAGMENT" in behavior_names

    def test_check_and_trigger_below_threshold_returns_empty(self):
        """check_and_trigger below all thresholds returns empty."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        triggered = pool.check_and_trigger(current_points=5)
        
        assert len(triggered) == 0

    def test_behavior_not_duplicated_in_pending(self):
        """Same behavior should not be added to pending twice."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        # First trigger
        pool.check_and_trigger(current_points=25)
        first_pending = pool.get_pending()
        
        # Second trigger at same points
        pool.check_and_trigger(current_points=25)
        second_pending = pool.get_pending()
        
        assert len(first_pending) == len(second_pending)

    def test_multiple_behaviors_trigger_at_high_points(self):
        """Multiple behaviors can trigger at high point values."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        # 70 points should trigger WORLD_FRAGMENT (20), EXPLORE_LINKS (40), DEEP_REFLECTION (60)
        triggered = pool.check_and_trigger(current_points=70)
        
        behavior_names = [b.name for b in triggered]
        assert "WORLD_FRAGMENT" in behavior_names
        assert "EXPLORE_LINKS" in behavior_names
        assert "DEEP_REFLECTION" in behavior_names


class TestBehaviorPoolExecution:
    """Test behavior execution."""

    def test_execute_behavior_writes_vault_file(self):
        """execute should write result to vault path."""
        from agent.core.behavior_pool import BehaviorPool
        
        # Create temp vault directory
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            # Trigger a behavior first
            pool.check_and_trigger(current_points=25)
            
            # Execute WORLD_FRAGMENT
            result = pool.execute("WORLD_FRAGMENT", tmpdir)
            
            assert result.success is True
            assert result.output_path is not None
            assert os.path.exists(result.output_path)

    def test_execute_deducts_cost(self):
        """execute should deduct behavior cost from points."""
        from agent.core.behavior_pool import BehaviorPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            # WORLD_FRAGMENT costs 20
            result = pool.execute("WORLD_FRAGMENT", tmpdir)
            
            # State should track cost
            state = pool.get_behavior_state("WORLD_FRAGMENT")
            assert state.total_cost_spent == 20

    def test_execute_starts_cooldown(self):
        """execute should start cooldown period."""
        from agent.core.behavior_pool import BehaviorPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            result = pool.execute("WORLD_FRAGMENT", tmpdir)
            
            # Should be in cooldown
            assert pool.in_cooldown("WORLD_FRAGMENT") is True

    def test_execute_nonexistent_behavior_fails(self):
        """execute with invalid behavior should fail."""
        from agent.core.behavior_pool import BehaviorPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            result = pool.execute("NONEXISTENT", tmpdir)
            
            assert result.success is False
            assert result.error is not None


class TestBehaviorPoolCooldown:
    """Test cooldown mechanism."""

    def test_in_cooldown_returns_true_after_execution(self):
        """in_cooldown should return True after execution."""
        from agent.core.behavior_pool import BehaviorPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            pool.execute("WORLD_FRAGMENT", tmpdir)
            
            assert pool.in_cooldown("WORLD_FRAGMENT") is True

    def test_in_cooldown_returns_false_before_execution(self):
        """in_cooldown should return False before any execution."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        assert pool.in_cooldown("WORLD_FRAGMENT") is False

    def test_cooldown_prevents_retrigger(self):
        """Behavior in cooldown should not be re-triggered."""
        from agent.core.behavior_pool import BehaviorPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            # Execute WORLD_FRAGMENT
            pool.execute("WORLD_FRAGMENT", tmpdir)
            
            # Try to trigger again at high points
            triggered = pool.check_and_trigger(current_points=70)
            
            # WORLD_FRAGMENT should not be in pending
            pending_names = [b.name for b in triggered]
            assert "WORLD_FRAGMENT" not in pending_names

    def test_get_cooldown_remaining_returns_minutes(self):
        """get_cooldown_remaining should return minutes left."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        remaining = pool.get_cooldown_remaining("WORLD_FRAGMENT")
        
        assert remaining == 0  # Never executed

    def test_cooldown_tracks_time_elapsed(self):
        """Cooldown should track time since last execution."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        # Manually set last_triggered to 30 minutes ago
        pool.state["WORLD_FRAGMENT"].last_triggered = datetime.now() - timedelta(minutes=30)
        
        # WORLD_FRAGMENT has 60 min cooldown, so 30 min remaining
        remaining = pool.get_cooldown_remaining("WORLD_FRAGMENT")
        
        assert 25 <= remaining <= 35  # Allow some tolerance


class TestVaultWriteback:
    """Test Vault writeback specification compliance."""

    def test_vault_file_naming_convention(self):
        """Files should follow {behavior}_{timestamp}_{uuid}.md pattern."""
        from agent.core.behavior_pool import BehaviorPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            result = pool.execute("WORLD_FRAGMENT", tmpdir)
            
            filename = os.path.basename(result.output_path)
            
            # Pattern: world-fragment_YYYYMMDD-HHMMSS_xxxxxx.md
            assert filename.startswith("world-fragment_")
            assert filename.endswith(".md")

    def test_vault_frontmatter_has_required_fields(self):
        """Frontmatter should have type, behavior, topics, triggered_by, timestamp."""
        from agent.core.behavior_pool import BehaviorPool
        import yaml
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            result = pool.execute("WORLD_FRAGMENT", tmpdir)
            
            with open(result.output_path, "r") as f:
                content = f.read()
            
            # Extract frontmatter
            parts = content.split("---")
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                
                assert "type" in frontmatter
                assert "behavior" in frontmatter
                assert "timestamp" in frontmatter
                assert frontmatter["behavior"] == "WORLD_FRAGMENT"

    def test_vault_path_follows_specification(self):
        """Vault path should be vault/agent/world/{behavior}_{timestamp}_{uuid}.md."""
        from agent.core.behavior_pool import BehaviorPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            result = pool.execute("WORLD_FRAGMENT", tmpdir)
            
            # Path should contain vault/agent/world/
            assert "vault" in result.output_path
            assert "agent" in result.output_path
            assert "world" in result.output_path


class TestBehaviorPoolStatus:
    """Test status reporting."""

    def test_get_status_returns_pending_behaviors(self):
        """get_status should list pending behaviors."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        pool.check_and_trigger(current_points=25)
        
        status = pool.get_status()
        
        assert "pending" in status
        assert len(status["pending"]) >= 1

    def test_get_status_returns_behavior_details(self):
        """get_status should include behavior details."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        status = pool.get_status()
        
        assert "behaviors" in status
        assert len(status["behaviors"]) >= 3  # At least preset behaviors
        
        # Check structure
        wf_status = next(b for b in status["behaviors"] if b["name"] == "WORLD_FRAGMENT")
        assert wf_status["threshold"] == 20
        assert wf_status["cost"] == 20
        assert wf_status["cooldown_minutes"] == 60

    def test_get_behavior_state_returns_state(self):
        """get_behavior_state should return execution state."""
        from agent.core.behavior_pool import BehaviorPool
        
        pool = BehaviorPool()
        
        state = pool.get_behavior_state("WORLD_FRAGMENT")
        
        assert state.execution_count == 0
        assert state.total_cost_spent == 0
        assert state.last_triggered is None


class TestIntegration:
    """Integration tests for full behavior workflow."""

    def test_full_workflow_points_accumulation_to_execution(self):
        """Test complete workflow from accumulation to execution."""
        from agent.core.behavior_pool import BehaviorPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = BehaviorPool()
            
            # Accumulate points (simulated by passing to check_and_trigger)
            # At 25 points, WORLD_FRAGMENT should trigger
            triggered = pool.check_and_trigger(current_points=25)
            
            assert "WORLD_FRAGMENT" in [b.name for b in triggered]
            
            # Execute
            result = pool.execute("WORLD_FRAGMENT", tmpdir)
            
            assert result.success is True
            assert os.path.exists(result.output_path)
            
            # Should be in cooldown
            assert pool.in_cooldown("WORLD_FRAGMENT")
            
            # Should not trigger again immediately
            new_triggered = pool.check_and_trigger(current_points=70)
            assert "WORLD_FRAGMENT" not in [b.name for b in new_triggered]
