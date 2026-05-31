"""
Three-Driver Coordination Scheduler

Coordinates goal-driven, curiosity-driven, and time-driven behavior.
The scheduler makes decisions about what to do next based on:
- Goal priority: active goals take precedence
- Curiosity priority: urgent exploration proposals
- Time priority: periodic triggers and dormancy

This module implements the core decision-making loop for the autonomous agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .goals import Goal, GoalSystem
from .curiosity import CuriositySystem, ExplorationProposal
from .autonomous import AutonomousGoalCreator


@dataclass
class ScheduleDecision:
    """
    What the scheduler decided to do this tick.

    Attributes:
        action: One of "process_goal" | "explore" | "reflect" | "wait"
        target: Goal title or file path or null
        reasoning: Human-readable explanation of the decision
        timestamp: When this decision was made
    """
    action: str
    target: str
    reasoning: str
    timestamp: datetime


@dataclass
class DriverWeights:
    """
    Configurable weights for the three drivers.

    These weights determine how much each driver influences
    the final scheduling decision.
    """
    goal: float = 1.0
    curiosity: float = 0.8
    time: float = 0.6

    def evolve(self, decay_rate: float = 0.01) -> DriverWeights:
        """
        Evolve weights based on recent performance.

        Args:
            decay_rate: How fast weights converge to baseline (1.0)

        Returns:
            DriverWeights: New weights after evolution
        """
        return DriverWeights(
            goal=self._decay_toward_baseline(self.goal, decay_rate),
            curiosity=self._decay_toward_baseline(self.curiosity, decay_rate),
            time=self._decay_toward_baseline(self.time, decay_rate),
        )

    def boost(self, driver: str, amount: float) -> DriverWeights:
        """
        Boost a specific driver's weight.

        Args:
            driver: "goal" | "curiosity" | "time"
            amount: Amount to boost (added to current weight)

        Returns:
            DriverWeights: New weights after boost
        """
        weights = DriverWeights(
            goal=self.goal,
            curiosity=self.curiosity,
            time=self.time,
        )
        if driver == "goal":
            weights.goal = min(2.0, self.goal + amount)
        elif driver == "curiosity":
            weights.curiosity = min(2.0, self.curiosity + amount)
        elif driver == "time":
            weights.time = min(2.0, self.time + amount)
        return weights

    def _decay_toward_baseline(self, value: float, rate: float) -> float:
        """Decay a weight toward baseline of 1.0."""
        baseline = 1.0
        diff = value - baseline
        new_value = baseline + diff * (1.0 - rate)
        return round(new_value, 3)


@dataclass
class TimeTriggers:
    """
    Time-based trigger configuration.

    Defines thresholds for periodic actions.
    """
    # Check intervals
    goal_check_interval: timedelta = timedelta(minutes=5)
    curiosity_update_interval: timedelta = timedelta(hours=1)
    daily_organization_time: str = "08:00"
    weekly_reflection_day: int = 0  # 0 = Monday, 6 = Sunday

    # Dormancy thresholds
    max_dormancy: timedelta = timedelta(minutes=30)
    exploration_timeout: timedelta = timedelta(hours=2)
    reflection_interval: timedelta = timedelta(days=7)


@dataclass
class SchedulerState:
    """
    Tracks scheduler state for decision-making.

    Maintains timestamps of last actions and current scores.
    """
    last_goal_process: datetime = field(default_factory=datetime.now)
    last_curiosity_explore: datetime = field(default_factory=datetime.now)
    last_reflection: datetime = field(default_factory=datetime.now)
    last_map_update: datetime = field(default_factory=datetime.now)
    consecutive_waits: int = 0
    weights: DriverWeights = field(default_factory=DriverWeights)

    def time_since_goal(self) -> timedelta:
        return datetime.now() - self.last_goal_process

    def time_since_curiosity(self) -> timedelta:
        return datetime.now() - self.last_curiosity_explore

    def time_since_reflection(self) -> timedelta:
        return datetime.now() - self.last_reflection

    def time_since_map_update(self) -> timedelta:
        return datetime.now() - self.last_map_update


class Scheduler:
    """
    Three-driver coordination: goal-driven + curiosity-driven + time-driven.

    The scheduler implements a priority-based decision loop:
    1. If there are in-progress goals, continue them (goal-driven)
    2. If curiosity finds something urgent, explore it (curiosity-driven)
    3. If time trigger fires, handle it (time-driven)
    4. If nothing urgent, do nothing (dormancy)

    Usage:
        scheduler = Scheduler(goal_system, curiosity_system, goal_creator)
        decision = scheduler.tick()
    """

    # Time thresholds
    URGENT_CURIOUSITY_THRESHOLD = 0.7
    MIN_GOALS_FOR_WEIGHT_BOOST = 3

    def __init__(
        self,
        goal_system: GoalSystem,
        curiosity: CuriositySystem,
        goal_creator: AutonomousGoalCreator,
        weights: DriverWeights | None = None,
        triggers: TimeTriggers | None = None,
    ):
        """
        Initialize the scheduler.

        Args:
            goal_system: The goal system for goal-driven decisions
            curiosity: The curiosity system for exploration proposals
            goal_creator: For creating goals from triggers
            weights: Optional custom driver weights
            triggers: Optional custom time triggers
        """
        self.goals = goal_system
        self.curiosity = curiosity
        self.creator = goal_creator
        self.weights = weights or DriverWeights()
        self.triggers = triggers or TimeTriggers()
        self.state = SchedulerState(weights=self.weights)

    def tick(self) -> ScheduleDecision:
        """
        One scheduling decision.

        This is the main entry point for the scheduling loop.
        It checks all three drivers and returns the most urgent action.

        Returns:
            ScheduleDecision: The decision for this tick
        """
        self._update_state()
        return self.decide()

    def decide(self) -> ScheduleDecision:
        """
        Make a scheduling decision considering all three drivers.

        Priority order:
        1. Goal-driven (if active goals exist)
        2. Curiosity-driven (if urgent exploration found)
        3. Time-driven (if periodic trigger fires)
        4. Dormancy (wait/do nothing)

        Returns:
            ScheduleDecision: The scheduling decision
        """
        # Check goal driver first (highest priority)
        goal_decision = self._check_goal_driver()
        if goal_decision:
            return goal_decision

        # Check curiosity driver
        curiosity_decision = self._check_curiosity_driver()
        if curiosity_decision:
            return curiosity_decision

        # Check time driver
        time_decision = self._check_time_driver()
        if time_decision:
            return time_decision

        # Default: dormancy
        return self._dormancy_decision()

    def _check_goal_driver(self) -> ScheduleDecision | None:
        """
        Check goal-driven priorities.

        Returns a decision if there are active goals to process.

        Returns:
            ScheduleDecision or None
        """
        active_goals = self.goals.get_active_goals()

        if not active_goals:
            return None

        # Find in-progress goals first
        in_progress = [g for g in active_goals if g.status == "in_progress"]
        if in_progress:
            goal = in_progress[0]
            self.state.last_goal_process = datetime.now()
            return ScheduleDecision(
                action="process_goal",
                target=goal.title,
                reasoning=f"继续进行中目标：{goal.title}",
                timestamp=datetime.now(),
            )

        # Then accepted/planned goals
        if active_goals:
            goal = active_goals[0]
            self.state.last_goal_process = datetime.now()
            return ScheduleDecision(
                action="process_goal",
                target=goal.title,
                reasoning=f"处理活跃目标：{goal.title}",
                timestamp=datetime.now(),
            )

        return None

    def _check_curiosity_driver(self) -> ScheduleDecision | None:
        """
        Check curiosity-driven priorities.

        Returns a decision if there's an urgent exploration proposal.

        Returns:
            ScheduleDecision or None
        """
        proposals = self.curiosity.propose_exploration()

        if not proposals:
            return None

        # Check for urgent proposals
        urgent_proposals = [p for p in proposals if p.urgency >= self.URGENT_CURIOUSITY_THRESHOLD]

        if urgent_proposals:
            proposal = urgent_proposals[0]
            self.state.last_curiosity_explore = datetime.now()
            return ScheduleDecision(
                action="explore",
                target=proposal.target_path,
                reasoning=f"好奇心驱动探索：{proposal.target_title} — {proposal.reason}",
                timestamp=datetime.now(),
            )

        # Check if exploration timeout exceeded
        if self.state.time_since_curiosity() >= self.triggers.exploration_timeout:
            if proposals:
                proposal = proposals[0]
                self.state.last_curiosity_explore = datetime.now()
                return ScheduleDecision(
                    action="explore",
                    target=proposal.target_path,
                    reasoning=f"探索超时后继续：{proposal.target_title}",
                    timestamp=datetime.now(),
                )

        return None

    def _check_time_driver(self) -> ScheduleDecision | None:
        """
        Check time-driven priorities.

        Time triggers:
        - Every 5 minutes: check if any files need processing
        - Every hour: periodic curiosity map update
        - Daily: daily organization routine
        - Weekly: weekly reflection

        Returns:
            ScheduleDecision or None
        """
        now = datetime.now()

        # Hourly: curiosity map update
        if self.state.time_since_map_update() >= self.triggers.curiosity_update_interval:
            self.state.last_map_update = now
            self.curiosity.build_map()
            return ScheduleDecision(
                action="reflect",
                target="curiosity_map",
                reasoning="时间驱动：更新好奇心地图",
                timestamp=now,
            )

        # Weekly: reflection
        if self.state.time_since_reflection() >= self.triggers.reflection_interval:
            self.state.last_reflection = now
            return ScheduleDecision(
                action="reflect",
                target="weekly",
                reasoning="时间驱动：周反思",
                timestamp=now,
            )

        # Daily: organization
        daily_time = self.triggers.daily_organization_time
        try:
            hour, minute = map(int, daily_time.split(":"))
            last_daily = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if last_daily > now:
                last_daily -= timedelta(days=1)
            if now - last_daily < timedelta(hours=25) and now.hour == hour:
                return ScheduleDecision(
                    action="reflect",
                    target="daily",
                    reasoning="时间驱动：日常整理",
                    timestamp=now,
                )
        except (ValueError, AttributeError):
            pass

        return None

    def _dormancy_decision(self) -> ScheduleDecision:
        """
        Decide to do nothing (dormancy).

        Tracks consecutive waits and evolves weights.

        Returns:
            ScheduleDecision: A wait decision
        """
        self.state.consecutive_waits += 1

        reasoning = "无紧迫任务，进入休眠"
        if self.state.consecutive_waits > 3:
            reasoning = f"连续第 {self.state.consecutive_waits} 次无任务"

        # Evolve weights during dormancy
        self.state.weights = self.state.weights.evolve(decay_rate=0.05)
        self.weights = self.state.weights

        return ScheduleDecision(
            action="wait",
            target="",
            reasoning=reasoning,
            timestamp=datetime.now(),
        )

    def _update_state(self) -> None:
        """
        Update scheduler state before making a decision.

        Called at the start of each tick.
        """
        # Keep state.weights in sync with self.weights for consistent reads
        # but don't overwrite if they reference the same object already
        if self.state.weights is not self.weights:
            self.state.weights = self.weights

    def calculate_priority_score(self) -> tuple[float, dict[str, float]]:
        """
        Calculate the priority score for all drivers.

        Used for debugging and tuning.

        Returns:
            Tuple of (total_score, individual_scores)
        """
        goal_score = self._goal_score()
        curiosity_score = self._curiosity_score()
        time_score = self._time_score()

        total = (
            self.weights.goal * goal_score +
            self.weights.curiosity * curiosity_score +
            self.weights.time * time_score
        )

        return total, {
            "goal": goal_score,
            "curiosity": curiosity_score,
            "time": time_score,
        }

    def _goal_score(self) -> float:
        """Calculate goal driver score (0.0 to 1.0)."""
        active_goals = self.goals.get_active_goals()

        if not active_goals:
            return 0.0

        # More active goals = higher score
        goal_count = len(active_goals)
        count_score = min(goal_count / self.MIN_GOALS_FOR_WEIGHT_BOOST, 1.0)

        # In-progress goals add urgency
        in_progress = [g for g in active_goals if g.status == "in_progress"]
        urgency_score = 0.5 if in_progress else 0.3

        return count_score * 0.5 + urgency_score * 0.5

    def _curiosity_score(self) -> float:
        """Calculate curiosity driver score (0.0 to 1.0)."""
        proposals = self.curiosity.propose_exploration()

        if not proposals:
            return 0.0

        # Highest urgency proposal
        max_urgency = max(p.urgency for p in proposals)

        # Curiosity intensity from the curiosity system
        intensity = self.curiosity.get_curiosity_intensity()

        # Time since last exploration
        time_factor = min(
            self.state.time_since_curiosity().total_seconds() /
            self.triggers.exploration_timeout.total_seconds(),
            1.0
        )

        return max_urgency * 0.4 + intensity * 0.3 + time_factor * 0.3

    def _time_score(self) -> float:
        """Calculate time driver score (0.0 to 1.0)."""
        # How long since last goal processing
        goal_time = min(
            self.state.time_since_goal().total_seconds() /
            self.triggers.goal_check_interval.total_seconds(),
            1.0
        )

        # How long since last map update
        map_time = min(
            self.state.time_since_map_update().total_seconds() /
            self.triggers.curiosity_update_interval.total_seconds(),
            1.0
        )

        # How long since last reflection
        reflection_time = min(
            self.state.time_since_reflection().total_seconds() /
            self.triggers.reflection_interval.total_seconds(),
            1.0
        )

        return max(goal_time, map_time, reflection_time)

    def boost_driver(self, driver: str, amount: float = 0.2) -> None:
        """
        Boost a driver's weight temporarily.

        Args:
            driver: "goal" | "curiosity" | "time"
            amount: Amount to boost (default 0.2)
        """
        self.state.weights = self.state.weights.boost(driver, amount)
        self.weights = self.state.weights

    def reset_weights(self) -> None:
        """Reset all weights to baseline (1.0)."""
        new_weights = DriverWeights()
        self.state.weights = new_weights
        self.weights = new_weights

    def record_action(self, action: str) -> None:
        """
        Record that an action was taken.

        Updates state timestamps accordingly.

        Args:
            action: The action that was taken
        """
        now = datetime.now()

        if action == "process_goal":
            self.state.last_goal_process = now
            self.state.consecutive_waits = 0
        elif action == "explore":
            self.state.last_curiosity_explore = now
            self.state.consecutive_waits = 0
        elif action == "reflect":
            self.state.last_reflection = now
            self.state.consecutive_waits = 0
        elif action == "wait":
            self.state.consecutive_waits += 1
        else:
            self.state.consecutive_waits = 0

    def get_state_summary(self) -> dict:
        """
        Get a summary of the scheduler state.

        Returns:
            dict: State summary for debugging
        """
        priority_total, priority_breakdown = self.calculate_priority_score()

        return {
            "active_goals": len(self.goals.get_active_goals()),
            "consecutive_waits": self.state.consecutive_waits,
            "time_since_goal": str(self.state.time_since_goal()),
            "time_since_curiosity": str(self.state.time_since_curiosity()),
            "time_since_reflection": str(self.state.time_since_reflection()),
            "weights": {
                "goal": self.weights.goal,
                "curiosity": self.weights.curiosity,
                "time": self.weights.time,
            },
            "priority_score": round(priority_total, 3),
            "priority_breakdown": {k: round(v, 3) for k, v in priority_breakdown.items()},
        }


__all__ = ["Scheduler", "ScheduleDecision", "DriverWeights", "TimeTriggers", "SchedulerState"]
