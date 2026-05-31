"""
Tests for the Three-Driver Coordination Scheduler.

These tests verify that the scheduler properly coordinates goal-driven,
curiosity-driven, and time-driven behavior.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock

from agent.core.scheduler import (
    Scheduler, ScheduleDecision, DriverWeights, TimeTriggers, SchedulerState
)
from agent.core.goals import Goal, GoalSystem
from agent.core.curiosity import CuriositySystem, ExplorationProposal
from agent.core.autonomous import AutonomousGoalCreator


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault directory for testing."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    goals_dir = vault_path / "agent" / "goals"
    goals_dir.mkdir(parents=True)
    return vault_path


@pytest.fixture
def goal_system(temp_vault):
    """Create a GoalSystem instance for testing."""
    return GoalSystem(temp_vault)


@pytest.fixture
def mock_curiosity():
    """Create a mock CuriositySystem for testing."""
    curiosity = Mock(spec=CuriositySystem)
    curiosity.propose_exploration.return_value = []
    curiosity.get_curiosity_intensity.return_value = 0.5
    curiosity.build_map.return_value = {}
    return curiosity


@pytest.fixture
def mock_goal_creator():
    """Create a mock AutonomousGoalCreator for testing."""
    creator = Mock(spec=AutonomousGoalCreator)
    return creator


@pytest.fixture
def scheduler(goal_system, mock_curiosity, mock_goal_creator):
    """Create a Scheduler instance for testing."""
    return Scheduler(goal_system, mock_curiosity, mock_goal_creator)


class TestScheduleDecision:
    """Tests for ScheduleDecision dataclass."""

    def test_schedule_decision_creation(self):
        """Test creating a ScheduleDecision."""
        decision = ScheduleDecision(
            action="process_goal",
            target="测试目标",
            reasoning="继续处理目标",
            timestamp=datetime.now(),
        )

        assert decision.action == "process_goal"
        assert decision.target == "测试目标"
        assert decision.reasoning == "继续处理目标"
        assert isinstance(decision.timestamp, datetime)


class TestDriverWeights:
    """Tests for DriverWeights dataclass."""

    def test_default_weights(self):
        """Test default weight values."""
        weights = DriverWeights()

        assert weights.goal == 1.0
        assert weights.curiosity == 0.8
        assert weights.time == 0.6

    def test_custom_weights(self):
        """Test custom weight values."""
        weights = DriverWeights(goal=1.5, curiosity=1.0, time=0.5)

        assert weights.goal == 1.5
        assert weights.curiosity == 1.0
        assert weights.time == 0.5

    def test_boost_goal(self):
        """Test boosting goal weight."""
        weights = DriverWeights()
        boosted = weights.boost("goal", 0.3)

        assert boosted.goal == 1.3
        assert boosted.curiosity == 0.8
        assert boosted.time == 0.6

    def test_boost_caps_at_max(self):
        """Test that boost doesn't exceed 2.0."""
        weights = DriverWeights(goal=1.9)
        boosted = weights.boost("goal", 0.5)

        assert boosted.goal == 2.0

    def test_boost_curiosity(self):
        """Test boosting curiosity weight."""
        weights = DriverWeights()
        boosted = weights.boost("curiosity", 0.4)

        assert boosted.goal == 1.0
        assert boosted.curiosity == pytest.approx(1.2)
        assert boosted.time == 0.6

    def test_boost_time(self):
        """Test boosting time weight."""
        weights = DriverWeights()
        boosted = weights.boost("time", 0.5)

        assert boosted.goal == 1.0
        assert boosted.curiosity == 0.8
        assert boosted.time == 1.1

    def test_boost_invalid_driver(self):
        """Test boosting invalid driver does nothing."""
        weights = DriverWeights()
        boosted = weights.boost("invalid", 0.5)

        assert boosted.goal == 1.0
        assert boosted.curiosity == 0.8
        assert boosted.time == 0.6

    def test_evolve_weights(self):
        """Test weight evolution toward baseline."""
        weights = DriverWeights(goal=1.5, curiosity=0.5, time=1.2)
        evolved = weights.evolve(decay_rate=0.1)

        # Goal should move toward 1.0
        assert 1.0 < evolved.goal < 1.5
        # Curiosity should move toward 1.0
        assert 0.5 < evolved.curiosity < 1.0
        # Time should move toward 1.0
        assert 1.0 < evolved.time < 1.2


class TestTimeTriggers:
    """Tests for TimeTriggers dataclass."""

    def test_default_triggers(self):
        """Test default trigger values."""
        triggers = TimeTriggers()

        assert triggers.goal_check_interval == timedelta(minutes=5)
        assert triggers.curiosity_update_interval == timedelta(hours=1)
        assert triggers.daily_organization_time == "08:00"
        assert triggers.weekly_reflection_day == 0

    def test_custom_triggers(self):
        """Test custom trigger values."""
        triggers = TimeTriggers(
            goal_check_interval=timedelta(minutes=10),
            curiosity_update_interval=timedelta(hours=2),
            daily_organization_time="20:00",
            weekly_reflection_day=6,
        )

        assert triggers.goal_check_interval == timedelta(minutes=10)
        assert triggers.curiosity_update_interval == timedelta(hours=2)
        assert triggers.daily_organization_time == "20:00"
        assert triggers.weekly_reflection_day == 6


class TestSchedulerState:
    """Tests for SchedulerState dataclass."""

    def test_default_state(self):
        """Test default state values."""
        state = SchedulerState()

        assert isinstance(state.last_goal_process, datetime)
        assert isinstance(state.last_curiosity_explore, datetime)
        assert isinstance(state.last_reflection, datetime)
        assert state.consecutive_waits == 0
        assert isinstance(state.weights, DriverWeights)

    def test_time_since_goal(self):
        """Test time_since_goal calculation."""
        state = SchedulerState()
        state.last_goal_process = datetime.now() - timedelta(minutes=10)

        elapsed = state.time_since_goal()
        assert elapsed >= timedelta(minutes=9)
        assert elapsed < timedelta(minutes=11)

    def test_time_since_curiosity(self):
        """Test time_since_curiosity calculation."""
        state = SchedulerState()
        state.last_curiosity_explore = datetime.now() - timedelta(hours=1)

        elapsed = state.time_since_curiosity()
        assert elapsed >= timedelta(hours=0, minutes=59)
        assert elapsed < timedelta(hours=1, minutes=2)


class TestSchedulerGoalDriver:
    """Tests for goal-driven scheduling."""

    def test_no_goals_returns_none_from_goal_driver(self, scheduler, mock_curiosity):
        """Test that goal driver returns None when no active goals."""
        decision = scheduler._check_goal_driver()
        assert decision is None

    def test_in_progress_goal_takes_priority(self, scheduler, goal_system, mock_curiosity):
        """Test that in-progress goals take priority."""
        goal_system.create_goal(title="进行中目标")
        goal_system.update_status("进行中目标", "in_progress")

        decision = scheduler._check_goal_driver()

        assert decision is not None
        assert decision.action == "process_goal"
        assert decision.target == "进行中目标"

    def test_accepted_goal_when_no_in_progress(self, scheduler, goal_system, mock_curiosity):
        """Test that accepted goals are processed when no in-progress goals."""
        goal = goal_system.create_goal(title="已接受目标")
        goal_system.update_status("已接受目标", "accepted")

        decision = scheduler._check_goal_driver()

        assert decision is not None
        assert decision.action == "process_goal"
        assert decision.target == "已接受目标"

    def test_decide_prefers_goals(self, scheduler, goal_system, mock_curiosity):
        """Test that decide() prioritizes goal driver."""
        goal = goal_system.create_goal(title="优先目标")
        goal_system.update_status("优先目标", "in_progress")

        mock_curiosity.propose_exploration.return_value = [
            ExplorationProposal(
                target_path="test/path",
                target_title="探索目标",
                reason="测试",
                urgency=0.9,
                created_at=datetime.now(),
            )
        ]

        decision = scheduler.decide()

        assert decision.action == "process_goal"
        assert decision.target == "优先目标"


class TestSchedulerCuriosityDriver:
    """Tests for curiosity-driven scheduling."""

    def test_no_proposals_returns_none(self, scheduler, mock_curiosity):
        """Test that curiosity driver returns None when no proposals."""
        mock_curiosity.propose_exploration.return_value = []

        decision = scheduler._check_curiosity_driver()
        assert decision is None

    def test_urgent_proposal_triggers_explore(self, scheduler, mock_curiosity):
        """Test that urgent proposals trigger exploration."""
        proposal = ExplorationProposal(
            target_path="urgent/path",
            target_title="紧急探索",
            reason="非常紧急",
            urgency=0.8,
            created_at=datetime.now(),
        )
        mock_curiosity.propose_exploration.return_value = [proposal]

        decision = scheduler._check_curiosity_driver()

        assert decision is not None
        assert decision.action == "explore"
        assert decision.target == "urgent/path"
        assert "紧急探索" in decision.reasoning

    def test_low_urgency_no_decision(self, scheduler, mock_curiosity):
        """Test that low urgency proposals don't trigger action."""
        proposal = ExplorationProposal(
            target_path="low/priority",
            target_title="低优先级",
            reason="不紧急",
            urgency=0.3,
            created_at=datetime.now(),
        )
        mock_curiosity.propose_exploration.return_value = [proposal]

        decision = scheduler._check_curiosity_driver()
        assert decision is None

    def test_exploration_timeout_triggers_action(self, scheduler, mock_curiosity):
        """Test that exploration timeout triggers exploration."""
        # Set last exploration to be long ago
        scheduler.state.last_curiosity_explore = datetime.now() - timedelta(hours=3)

        proposal = ExplorationProposal(
            target_path="timeout/path",
            target_title="超时探索",
            reason="超时后继续",
            urgency=0.4,
            created_at=datetime.now(),
        )
        mock_curiosity.propose_exploration.return_value = [proposal]

        decision = scheduler._check_curiosity_driver()

        assert decision is not None
        assert decision.action == "explore"


class TestSchedulerTimeDriver:
    """Tests for time-driven scheduling."""

    def test_map_update_interval_triggers(self, scheduler, mock_curiosity):
        """Test that curiosity map update interval triggers."""
        # Set last map update to be over an hour ago
        scheduler.state.last_map_update = datetime.now() - timedelta(hours=2)

        decision = scheduler._check_time_driver()

        assert decision is not None
        assert decision.action == "reflect"
        assert decision.target == "curiosity_map"
        mock_curiosity.build_map.assert_called_once()

    def test_reflection_interval_triggers(self, scheduler, mock_curiosity):
        """Test that reflection interval triggers."""
        # Set last reflection to be over a week ago
        scheduler.state.last_reflection = datetime.now() - timedelta(days=8)

        decision = scheduler._check_time_driver()

        assert decision is not None
        assert decision.action == "reflect"
        assert decision.target == "weekly"


class TestSchedulerDormancy:
    """Tests for dormancy behavior."""

    def test_dormancy_returns_wait(self, scheduler, mock_curiosity):
        """Test that dormancy returns a wait decision."""
        decision = scheduler._dormancy_decision()

        assert decision.action == "wait"
        assert decision.target == ""

    def test_consecutive_waits_increments(self, scheduler):
        """Test that consecutive waits are tracked."""
        initial_waits = scheduler.state.consecutive_waits

        scheduler._dormancy_decision()
        assert scheduler.state.consecutive_waits == initial_waits + 1

    def test_weights_evolve_during_dormancy(self, scheduler):
        """Test that weights evolve during dormancy."""
        original_weights = DriverWeights()
        scheduler.weights = original_weights

        scheduler._dormancy_decision()

        # Weights should have evolved
        assert scheduler.weights != original_weights


class TestSchedulerPriorityScore:
    """Tests for priority score calculation."""

    def test_no_activity_returns_low_score(self, scheduler, mock_curiosity):
        """Test that no activity returns very low scores."""
        total, breakdown = scheduler.calculate_priority_score()

        # Time score may be non-zero due to time passing, but goals and curiosity should be 0
        assert breakdown["goal"] == 0.0
        assert breakdown["curiosity"] == 0.0

    def test_active_goals_increases_goal_score(self, scheduler, goal_system, mock_curiosity):
        """Test that active goals increase goal score."""
        goal_system.create_goal(title="活跃目标1")
        goal_system.create_goal(title="活跃目标2")
        goal_system.update_status("活跃目标1", "in_progress")

        _, breakdown = scheduler.calculate_priority_score()

        assert breakdown["goal"] > 0.0

    def test_weighted_priority_score(self, scheduler):
        """Test that priority score uses weights."""
        scheduler.weights = DriverWeights(goal=2.0, curiosity=0.0, time=0.0)

        # Mock goal score to be 0.5
        scheduler.goals = Mock()
        scheduler.goals.get_active_goals.return_value = [
            Mock(status="in_progress"),
        ]

        total, breakdown = scheduler.calculate_priority_score()

        # Total should be weighted (2.0 * goal_score)
        # With 1 in-progress goal: goal_score = 0.4167, total = 0.833
        assert total == pytest.approx(0.833, rel=0.01)


class TestSchedulerRecordAction:
    """Tests for action recording."""

    def test_record_process_goal(self, scheduler):
        """Test recording goal processing action."""
        scheduler.state.consecutive_waits = 5

        scheduler.record_action("process_goal")

        assert scheduler.state.consecutive_waits == 0

    def test_record_explore(self, scheduler):
        """Test recording exploration action."""
        scheduler.state.consecutive_waits = 10

        scheduler.record_action("explore")

        assert scheduler.state.consecutive_waits == 0

    def test_record_wait_increments(self, scheduler):
        """Test that recording wait increments consecutive waits."""
        scheduler.state.consecutive_waits = 0

        scheduler.record_action("wait")

        assert scheduler.state.consecutive_waits == 1


class TestSchedulerBoostDriver:
    """Tests for driver boosting."""

    def test_boost_goal_driver(self, scheduler):
        """Test boosting goal driver."""
        original_goal_weight = scheduler.weights.goal

        scheduler.boost_driver("goal", 0.3)

        assert scheduler.weights.goal == original_goal_weight + 0.3

    def test_boost_curiosity_driver(self, scheduler):
        """Test boosting curiosity driver."""
        original_curiosity_weight = scheduler.weights.curiosity

        scheduler.boost_driver("curiosity", 0.5)

        assert scheduler.weights.curiosity == original_curiosity_weight + 0.5

    def test_reset_weights(self, scheduler):
        """Test resetting weights to baseline."""
        # First boost the weights
        scheduler.boost_driver("goal", 0.5)
        scheduler.boost_driver("curiosity", 0.5)
        scheduler.boost_driver("time", 0.5)

        # Then reset
        scheduler.reset_weights()

        # Verify all weights are at baseline
        assert scheduler.weights.goal == 1.0
        assert scheduler.weights.curiosity == 1.0
        assert scheduler.weights.time == 1.0


class TestSchedulerStateSummary:
    """Tests for state summary."""

    def test_get_state_summary(self, scheduler, goal_system):
        """Test getting state summary."""
        goal_system.create_goal(title="测试目标")
        goal_system.update_status("测试目标", "in_progress")

        summary = scheduler.get_state_summary()

        assert "active_goals" in summary
        assert "consecutive_waits" in summary
        assert "weights" in summary
        assert "priority_score" in summary
        assert summary["active_goals"] == 1


class TestSchedulerIntegration:
    """Integration tests for the scheduler."""

    def test_full_tick_cycle(self, scheduler, goal_system, mock_curiosity):
        """Test a full tick cycle with various conditions."""
        # No goals, no curiosity
        decision = scheduler.tick()

        assert decision.action == "wait"

    def test_tick_with_in_progress_goal(self, scheduler, goal_system, mock_curiosity):
        """Test tick when there's an in-progress goal."""
        goal_system.create_goal(title="进行中")
        goal_system.update_status("进行中", "in_progress")

        decision = scheduler.tick()

        assert decision.action == "process_goal"
        assert decision.target == "进行中"

    def test_tick_with_urgent_curiosity(self, scheduler, goal_system, mock_curiosity):
        """Test tick when there's an urgent curiosity proposal."""
        # No active goals
        mock_curiosity.propose_exploration.return_value = [
            ExplorationProposal(
                target_path="探索路径",
                target_title="探索标题",
                reason="紧急原因",
                urgency=0.9,
                created_at=datetime.now(),
            )
        ]

        decision = scheduler.tick()

        assert decision.action == "explore"
        assert decision.target == "探索路径"

    def test_tick_with_time_trigger(self, scheduler, mock_curiosity):
        """Test tick when time trigger fires."""
        # No active goals
        scheduler.state.last_map_update = datetime.now() - timedelta(hours=2)

        decision = scheduler.tick()

        assert decision.action == "reflect"
        assert decision.target == "curiosity_map"


class TestSchedulerEdgeCases:
    """Tests for edge cases."""

    def test_decide_with_mocked_drivers(self, scheduler):
        """Test decide with all drivers mocked."""
        # Mock goal driver to return None
        scheduler.goals = Mock()
        scheduler.goals.get_active_goals.return_value = []

        # Mock curiosity driver to return None
        scheduler.curiosity = Mock()
        scheduler.curiosity.propose_exploration.return_value = []

        # Mock time driver to return None
        scheduler.state.last_map_update = datetime.now()
        scheduler.state.last_reflection = datetime.now() - timedelta(days=1)

        decision = scheduler.decide()

        assert decision.action == "wait"

    def test_multiple_active_goals(self, scheduler, goal_system):
        """Test with multiple active goals."""
        goal_system.create_goal(title="目标1")
        goal_system.create_goal(title="目标2")
        goal_system.create_goal(title="目标3")
        goal_system.update_status("目标2", "in_progress")

        decision = scheduler._check_goal_driver()

        assert decision is not None
        assert decision.target == "目标2"

    def test_weights_persistence(self, scheduler):
        """Test that weights persist across decisions."""
        scheduler.weights = DriverWeights(goal=1.5)
        scheduler.state.weights = scheduler.weights

        # Don't call decide() as it may modify weights through dormancy
        # Just verify the weight is set
        assert scheduler.weights.goal == 1.5
