"""
Tests for the Autonomous Goal Creator
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# Set up mock vault path before importing modules
MOCK_VAULT_PATH = Path(tempfile.mkdtemp())


@pytest.fixture
def mock_vault():
    """Create a mock vault directory."""
    vault = MOCK_VAULT_PATH / "agent"
    vault.mkdir(parents=True, exist_ok=True)
    world_dir = vault / "world"
    world_dir.mkdir(parents=True, exist_ok=True)
    goals_dir = vault / "goals"
    goals_dir.mkdir(parents=True, exist_ok=True)
    return vault


@pytest.fixture
def mock_env_vault(mock_vault):
    """Patch the vault path environment variable."""
    with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(MOCK_VAULT_PATH)}):
        yield mock_vault


@pytest.fixture
def mock_llm():
    """Create a mock LLM client."""
    llm = MagicMock()
    llm.complete_str = MagicMock(return_value="目标标题：测试目标\n目标描述：这是一个测试目标。\n是否追寻：是")
    return llm


@pytest.fixture
def mock_state():
    """Create a mock agent state."""
    state = MagicMock()
    state.curiosity_level = 0.7
    state.personality = {
        "description": "好奇的探索者",
        "traits": {
            "curious": 0.8,
            "careful": 0.5,
            "creative": 0.6,
            "methodical": 0.4,
        }
    }
    return state


@pytest.fixture
def memory_index_file():
    """Create the memory index file."""
    agent_dir = MOCK_VAULT_PATH / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    index_path = agent_dir / "memory-index.json"
    initial_data = {
        "version": "1.0.0",
        "created": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "entries": [],
        "stats": {"total_entries": 0, "by_type": {}},
        "decay_entries": {},
    }
    index_path.write_text(json.dumps(initial_data), encoding="utf-8")
    return index_path


class TestAutonomousGoalCreator:
    """Tests for the AutonomousGoalCreator class."""

    def test_propose_from_curiosity(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """Curiosity findings should generate goal proposals."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        result = creator.propose_from_curiosity("关于时间本质的思考")

        assert result is not None
        assert result.title == "测试目标"
        assert "测试" in result.description
        mock_llm.complete_str.assert_called_once()

    def test_propose_from_curiosity_no_pursue(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """When LLM says no pursue, still returns a proposed goal."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        mock_llm.complete_str.return_value = "目标标题：探索想法\n目标描述：探索一个新想法。\n是否追寻：否"

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        result = creator.propose_from_curiosity("一些随机的想法")

        # Should return a proposed goal (not accepted)
        assert result is not None
        assert result.title == "探索想法"

    def test_propose_from_time(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """Time triggers should generate goal proposals."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        result = creator.propose_from_time("daily_organization")

        assert result is not None
        assert result.title == "测试目标"

    def test_propose_from_time_invalid_trigger(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """Invalid time trigger should raise ValueError."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        with pytest.raises(ValueError, match="Invalid trigger_type"):
            creator.propose_from_time("invalid_trigger")

    def test_propose_from_conversation(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """User conversation should generate goal proposals."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        result = creator.propose_from_conversation("我想了解哲学")

        assert result is not None
        assert result.title == "测试目标"

    def test_propose_from_conversation_no_goal(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """When LLM cannot parse goal, return None."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        mock_llm.complete_str.return_value = "这个对话没有产生任何目标。"

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        result = creator.propose_from_conversation("随便说点什么")

        assert result is None


class TestShouldAcceptLogic:
    """Tests for goal acceptance logic."""

    def test_has_active_goal_check(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """Check if system has active goal detection."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        goal_system.create_goal(
            title="已有目标",
            description="这是一个已存在的目标",
            triggered_by="test",
        )

        has_active = goal_system.get_goal("已有目标")
        assert has_active is not None
        assert has_active.status == "proposed"

    def test_llm_judges_acceptance(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """LLM should be used to judge goal acceptance."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem, Goal
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        new_goal = Goal(
            title="全新目标",
            description="这是一个全新的目标",
            status="proposed",
            curiosity_triggered=False,
            created=datetime.now(),
            updated=datetime.now(),
        )

        creator._should_accept(new_goal)

        assert mock_llm.complete_str.call_count >= 1

    def test_llm_yes_returns_true(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """When LLM says yes, goal is accepted."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem, Goal
        from agent.core.autonomous import AutonomousGoalCreator

        mock_llm.complete_str.return_value = "是"

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        new_goal = Goal(
            title="可接受的目标",
            description="这应该是可接受的",
            status="proposed",
            curiosity_triggered=False,
            created=datetime.now(),
            updated=datetime.now(),
        )

        should_accept = creator._should_accept(new_goal)

        assert should_accept is True

    def test_llm_no_returns_false(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """When LLM says no, goal is rejected."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem, Goal
        from agent.core.autonomous import AutonomousGoalCreator

        mock_llm.complete_str.return_value = "否"

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        new_goal = Goal(
            title="不可接受的目标",
            description="这太大了",
            status="proposed",
            curiosity_triggered=False,
            created=datetime.now(),
            updated=datetime.now(),
        )

        should_accept = creator._should_accept(new_goal)

        assert should_accept is False


class TestPromptParsing:
    """Tests for LLM response parsing."""

    def test_extract_title_with_colon(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """Should extract title with Chinese colon."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        title = creator._extract_title("目标标题：探索时间的本质")
        assert title == "探索时间的本质"

    def test_extract_title_with_english_colon(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """Should extract title with English colon."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        title = creator._extract_title("目标标题: 探索时间的本质")
        assert title == "探索时间的本质"

    def test_extract_description(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """Should extract description."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        text = "目标描述：深入探索时间与记忆的关系\n是否追寻：是"
        desc = creator._extract_description(text)
        assert "时间" in desc
        assert "记忆" in desc

    def test_extract_should_pursue_yes(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """Should detect yes decision."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        should = creator._extract_should_pursue("是否追寻：是")
        assert should is True

    def test_extract_should_pursue_no(self, mock_env_vault, mock_llm, mock_state, memory_index_file):
        """Should detect no decision."""
        from agent.core.decay import MemoryDecay
        from agent.core.goals import GoalSystem
        from agent.core.autonomous import AutonomousGoalCreator

        goal_system = GoalSystem(MOCK_VAULT_PATH)
        decay = MemoryDecay()
        creator = AutonomousGoalCreator(mock_llm, mock_state, goal_system, decay)

        should = creator._extract_should_pursue("是否追寻：否")
        assert should is False
