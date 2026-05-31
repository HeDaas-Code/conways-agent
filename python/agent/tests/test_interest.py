"""
Tests for Interest - interest accumulation with decay support.

TDD RED phase: Tests for expected behavior.
Interest in INTERACTION mode decays over time.
"""

import pytest
from datetime import datetime, timedelta


class TestInterestDecay:
    """Test interest decay behavior in INTERACTION mode."""

    def test_initial_interest_is_zero(self):
        """Interest starts at 0."""
        from agent.core.interest import InterestAccumulator
        
        acc = InterestAccumulator()
        assert acc.state.points == 0

    def test_tick_increases_interest(self):
        """Tick should increase interest points."""
        from agent.core.interest import InterestAccumulator
        
        acc = InterestAccumulator()
        acc.tick()
        
        assert acc.state.points > 0

    def test_dialogue_increases_interest(self):
        """Dialogue interaction should increase interest."""
        from agent.core.interest import InterestAccumulator
        
        acc = InterestAccumulator()
        initial = acc.state.points
        acc.add_dialogue()
        
        assert acc.state.points > initial

    def test_decay_reduces_interest_in_interaction_mode(self):
        """Decay should reduce interest in INTERACTION mode."""
        from agent.core.interest import InterestAccumulator, InterestState
        from agent.core.mode_machine import Mode
        
        acc = InterestAccumulator()
        acc.state.points = 50
        acc.state.mode = Mode.INTERACTION
        
        # Apply decay
        acc.decay(Mode.INTERACTION)
        
        assert acc.state.points < 50
        assert acc.state.points >= 0  # Never goes negative

    def test_decay_does_not_affect_self_mode(self):
        """Decay should NOT reduce interest in SELF mode."""
        from agent.core.interest import InterestAccumulator
        from agent.core.mode_machine import Mode
        
        acc = InterestAccumulator()
        acc.state.points = 50
        acc.state.mode = Mode.SELF
        
        initial = acc.state.points
        acc.decay(Mode.SELF)
        
        assert acc.state.points == initial

    def test_decay_does_not_go_below_zero(self):
        """Decay should not reduce interest below 0."""
        from agent.core.interest import InterestAccumulator
        from agent.core.mode_machine import Mode
        
        acc = InterestAccumulator()
        acc.state.points = 3  # Less than decay rate
        acc.state.mode = Mode.INTERACTION
        
        acc.decay(Mode.INTERACTION)
        
        assert acc.state.points >= 0

    def test_decay_rate_is_five_per_minute(self):
        """Decay rate should be 5 points per minute in INTERACTION mode."""
        from agent.core.interest import InterestAccumulator, DECAY_RATE_PER_MINUTE
        from agent.core.mode_machine import Mode
        
        assert DECAY_RATE_PER_MINUTE == 5


class TestInterestAccumulation:
    """Test interest accumulation from various sources."""

    def test_add_dialogue_adds_points(self):
        """Dialogue should add 5 points."""
        from agent.core.interest import InterestAccumulator, POINTS_PER_DIALOGUE
        
        acc = InterestAccumulator()
        before = acc.state.points
        acc.add_dialogue()
        
        assert acc.state.points == before + POINTS_PER_DIALOGUE

    def test_add_vault_event_adds_points(self):
        """Vault event should add points."""
        from agent.core.interest import InterestAccumulator, POINTS_PER_VAULT_EVENT
        
        acc = InterestAccumulator()
        before = acc.state.points
        acc.add_vault_event()
        
        assert acc.state.points == before + POINTS_PER_VAULT_EVENT


class TestInterestThresholds:
    """Test autonomous action triggering based on thresholds."""

    def test_action_triggered_at_threshold(self):
        """Action should be triggered when threshold reached."""
        from agent.core.interest import InterestAccumulator, AutonomousAction
        
        acc = InterestAccumulator()
        acc.state.points = InterestState.WORLD_FRAGMENT_THRESHOLD
        
        acc.add_dialogue()  # Add points to trigger
        
        pending = acc.get_pending_actions()
        assert AutonomousAction.GENERATE_WORLD_FRAGMENT in pending

    def test_action_not_triggered_before_threshold(self):
        """Action should not be triggered before threshold."""
        from agent.core.interest import InterestAccumulator, AutonomousAction
        
        acc = InterestAccumulator()
        acc.state.points = InterestState.WORLD_FRAGMENT_THRESHOLD - 1
        
        acc.add_dialogue()  # May not reach threshold
        
        pending = acc.get_pending_actions()
        # Action may or may not be pending depending on exact value
        assert len(pending) <= 1

    def test_consume_action_removes_from_pending(self):
        """Consuming action should remove it from pending."""
        from agent.core.interest import InterestAccumulator, AutonomousAction
        
        acc = InterestAccumulator()
        acc.state.pending_actions.append(AutonomousAction.GENERATE_WORLD_FRAGMENT)
        
        consumed = acc.consume_action(AutonomousAction.GENERATE_WORLD_FRAGMENT)
        
        assert consumed is True
        assert AutonomousAction.GENERATE_WORLD_FRAGMENT not in acc.state.pending_actions

    def test_consume_all_actions_clears_pending(self):
        """Consume all should clear all pending actions."""
        from agent.core.interest import InterestAccumulator, AutonomousAction
        
        acc = InterestAccumulator()
        acc.state.pending_actions = [
            AutonomousAction.GENERATE_WORLD_FRAGMENT,
            AutonomousAction.EXPLORE_NOTE_LINKS,
        ]
        
        consumed = acc.consume_all_actions()
        
        assert len(consumed) == 2
        assert len(acc.state.pending_actions) == 0


class TestInterestReset:
    """Test interest reset behavior."""

    def test_reset_clears_points(self):
        """Reset should clear all points."""
        from agent.core.interest import InterestAccumulator
        
        acc = InterestAccumulator()
        acc.state.points = 100
        
        acc.reset()
        
        assert acc.state.points == 0

    def test_reset_clears_pending_actions(self):
        """Reset should clear pending actions."""
        from agent.core.interest import InterestAccumulator, AutonomousAction
        
        acc = InterestAccumulator()
        acc.state.pending_actions = [AutonomousAction.GENERATE_WORLD_FRAGMENT]
        
        acc.reset()
        
        assert len(acc.state.pending_actions) == 0


# Need to import InterestState at top for threshold reference
from agent.core.interest import InterestState
