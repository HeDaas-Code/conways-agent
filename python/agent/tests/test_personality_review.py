"""
Tests for the Personality Review System

Tests personality snapshots, drift detection, growth detection, and periodic reviews.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from agent.core.personality_review import EvolutionSystem, PersonalitySnapshot
from agent.core.state import AgentState
from agent.core.memory import MemorySystem
from agent.core.llm import LLMClient
from agent.core.world_fragment import WorldFragment


@pytest.fixture
def temp_history_dir():
    """Create a temporary directory for snapshot history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_state():
    """Create a mock agent state."""
    state = AgentState()
    state.curiosity_level = 0.6
    state.fit_threshold = 0.5
    state.attention_window_size = 3
    state.total_cycles = 50
    return state


@pytest.fixture
def mock_memory(temp_world_dir):
    """Create a memory system with temporary directory."""
    return MemorySystem(world_dir=temp_world_dir)


@pytest.fixture
def temp_world_dir():
    """Create a temporary world directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_llm():
    """Create a mock LLM client."""
    return MockLLMClient()


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(self):
        super().__init__(model="mock/model")

    def complete_str(self, system: str, user: str, **kwargs) -> str:
        """Return a mock reflection response."""
        return """变化描述：测试变化描述

是否有漂移：否
漂移详情：无
是否有成长：是
成长详情：测试成长详情"""


class MockLLMClientWithDrift(LLMClient):
    """Mock LLM client that simulates drift."""

    def __init__(self):
        super().__init__(model="mock/model")

    def complete_str(self, system: str, user: str, **kwargs) -> str:
        """Return a mock response indicating drift."""
        return """变化描述：显著变化描述

是否有漂移：是
漂移详情：好奇心强度异常变化
是否有成长：是
成长详情：处理模式增加"""


class MockLLMClientNoHistory(LLMClient):
    """Mock LLM client for first-time review."""

    def __init__(self):
        super().__init__(model="mock/model")

    def complete_str(self, system: str, user: str, **kwargs) -> str:
        """Return a mock response for first review."""
        return """变化描述：首次快照

是否有漂移：否
漂移详情：无历史数据
是否有成长：否
成长详情：无历史数据"""


def test_take_snapshot(mock_state, mock_memory, mock_llm, temp_history_dir):
    """take_snapshot should capture current personality state."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    snapshot = evolution.take_snapshot()

    assert snapshot.curiosity_level == 0.6
    assert snapshot.fit_threshold == 0.5
    assert snapshot.attention_window_size == 3
    assert snapshot.world_corpus_size == 0
    assert snapshot.processing_patterns == []
    assert isinstance(snapshot.captured_at, datetime)


def test_save_and_load_snapshot(mock_state, mock_memory, mock_llm, temp_history_dir):
    """Snapshot should persist and load correctly."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    snapshot = evolution.take_snapshot()
    path = evolution.save_snapshot(snapshot)

    assert path.exists()
    assert path.name.startswith("snapshot-")

    # Load snapshots
    loaded = evolution.load_snapshots()
    assert len(loaded) == 1
    assert loaded[0].curiosity_level == snapshot.curiosity_level
    assert loaded[0].fit_threshold == snapshot.fit_threshold


def test_snapshot_markdown_format(mock_state, mock_memory, mock_llm, temp_history_dir):
    """Snapshot markdown should have proper format."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    snapshot = evolution.take_snapshot()
    markdown = snapshot.to_markdown()

    assert "---" in markdown
    assert "snapshot_at:" in markdown
    assert "curiosity_level: 0.6" in markdown
    assert "fit_threshold: 0.5" in markdown
    assert "# 人格快照" in markdown


def test_detect_drift_no_previous(mock_state, mock_memory, mock_llm, temp_history_dir):
    """detect_drift with no previous snapshot should return False."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    current = evolution.take_snapshot()
    result = evolution.detect_drift(None, current)

    assert result["detected"] is False
    assert "No previous snapshot" in result["details"]


def test_detect_drift_significant_change(mock_state, mock_memory, mock_llm, temp_history_dir):
    """detect_drift should detect significant parameter changes."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    old = PersonalitySnapshot(
        captured_at=datetime.now() - timedelta(days=1),
        curiosity_level=0.6,
        fit_threshold=0.5,
        attention_window_size=3,
        active_goals_count=10,
        world_corpus_size=10,
        processing_patterns=["prefers translation"],
    )

    new = PersonalitySnapshot(
        captured_at=datetime.now(),
        curiosity_level=0.95,  # Large change
        fit_threshold=0.5,
        attention_window_size=3,
        active_goals_count=15,
        world_corpus_size=12,
        processing_patterns=["prefers translation"],
    )

    result = evolution.detect_drift(old, new)

    assert result["detected"] is True
    assert "好奇心强度大幅变化" in result["details"]


def test_detect_drift_processing_pattern_change(mock_state, mock_memory, mock_llm, temp_history_dir):
    """detect_drift should detect processing pattern changes."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    old = PersonalitySnapshot(
        captured_at=datetime.now() - timedelta(days=1),
        curiosity_level=0.6,
        fit_threshold=0.5,
        attention_window_size=3,
        active_goals_count=10,
        world_corpus_size=10,
        processing_patterns=["prefers translation"],
    )

    new = PersonalitySnapshot(
        captured_at=datetime.now(),
        curiosity_level=0.6,
        fit_threshold=0.5,
        attention_window_size=3,
        active_goals_count=10,
        world_corpus_size=10,
        processing_patterns=["favors collision"],  # Different pattern
    )

    result = evolution.detect_drift(old, new)

    assert result["detected"] is True
    assert "新增处理模式" in result["details"] or "消失处理模式" in result["details"]


def test_detect_drift_no_change(mock_state, mock_memory, mock_llm, temp_history_dir):
    """detect_drift should return False when no significant changes."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    old = PersonalitySnapshot(
        captured_at=datetime.now() - timedelta(days=1),
        curiosity_level=0.6,
        fit_threshold=0.5,
        attention_window_size=3,
        active_goals_count=10,
        world_corpus_size=10,
        processing_patterns=["prefers translation"],
    )

    new = PersonalitySnapshot(
        captured_at=datetime.now(),
        curiosity_level=0.62,  # Small change
        fit_threshold=0.52,    # Small change
        attention_window_size=3,
        active_goals_count=10,
        world_corpus_size=12,
        processing_patterns=["prefers translation"],
    )

    result = evolution.detect_drift(old, new)

    assert result["detected"] is False
    assert "无显著漂移" in result["details"]


def test_detect_growth_no_previous(mock_state, mock_memory, mock_llm, temp_history_dir):
    """detect_growth with no previous snapshot should return False."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    current = evolution.take_snapshot()
    result = evolution.detect_growth(None, current)

    assert result["detected"] is False
    assert "No previous snapshot" in result["details"]


def test_detect_growth_corpus_expansion(mock_state, mock_memory, mock_llm, temp_history_dir):
    """detect_growth should detect corpus expansion as growth."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    old = PersonalitySnapshot(
        captured_at=datetime.now() - timedelta(days=1),
        curiosity_level=0.6,
        fit_threshold=0.5,
        attention_window_size=3,
        active_goals_count=10,
        world_corpus_size=10,
        processing_patterns=["prefers translation"],
    )

    new = PersonalitySnapshot(
        captured_at=datetime.now(),
        curiosity_level=0.6,
        fit_threshold=0.5,
        attention_window_size=3,
        active_goals_count=10,
        world_corpus_size=15,  # Growth
        processing_patterns=["prefers translation"],
    )

    result = evolution.detect_growth(old, new)

    assert result["detected"] is True
    assert "世界语料库扩展" in result["details"]


def test_detect_growth_new_patterns(mock_state, mock_memory, mock_llm, temp_history_dir):
    """detect_growth should detect new processing patterns as growth."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    old = PersonalitySnapshot(
        captured_at=datetime.now() - timedelta(days=1),
        curiosity_level=0.6,
        fit_threshold=0.5,
        attention_window_size=3,
        active_goals_count=10,
        world_corpus_size=10,
        processing_patterns=["prefers translation"],
    )

    new = PersonalitySnapshot(
        captured_at=datetime.now(),
        curiosity_level=0.6,
        fit_threshold=0.5,
        attention_window_size=3,
        active_goals_count=10,
        world_corpus_size=10,
        processing_patterns=["prefers translation", "favors collision"],
    )

    result = evolution.detect_growth(old, new)

    assert result["detected"] is True
    assert "新的处理方式出现" in result["details"]


def test_should_review_cycles_threshold(mock_state, mock_memory, mock_llm, temp_history_dir):
    """should_review should trigger on cycle threshold."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
        cycles_threshold=50,
    )

    # Not enough cycles yet
    assert evolution.should_review() is False

    # Add more cycles
    mock_state.total_cycles = 100
    assert evolution.should_review() is True


def test_should_review_corpus_growth(mock_state, mock_memory, mock_llm, temp_history_dir):
    """should_review should trigger on corpus growth."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
        corpus_growth_threshold=3,
    )

    # Add fragments
    for i in range(3):
        fragment = WorldFragment(
            title=f"Fragment {i}",
            content=f"Content {i}",
            fit_path="translation",
            created_at=datetime.now(),
        )
        mock_memory.write_fragment(fragment)

    assert evolution.should_review() is True


def test_review_first_time(mock_state, mock_memory, temp_history_dir):
    """First review should handle no previous snapshot."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=MockLLMClientNoHistory(),
        history_dir=temp_history_dir,
    )

    result = evolution.review()

    assert result["snapshot"] is not None
    assert result["previous_snapshot"] is None
    assert result["drift"]["detected"] is False
    assert result["growth"]["detected"] is False


def test_review_with_previous_snapshot(mock_state, mock_memory, mock_llm, temp_history_dir):
    """Review should compare with previous snapshot."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    # Create and save initial snapshot
    first_snapshot = evolution.take_snapshot()
    evolution.save_snapshot(first_snapshot)

    # Add a fragment
    fragment = WorldFragment(
        title="New Learning",
        content="Content",
        fit_path="translation",
        created_at=datetime.now(),
    )
    mock_memory.write_fragment(fragment)

    # Second review
    mock_state.total_cycles = 150
    result = evolution.review()

    assert result["snapshot"] is not None
    assert result["previous_snapshot"] is not None
    assert result["snapshot"].world_corpus_size > result["previous_snapshot"].world_corpus_size


def test_evolution_summary(mock_state, mock_memory, mock_llm, temp_history_dir):
    """get_evolution_summary should return correct summary."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    # Create multiple snapshots with different curiosity levels
    for i in range(3):
        mock_state.curiosity_level = 0.5 + (i * 0.1)
        snapshot = evolution.take_snapshot()
        evolution.save_snapshot(snapshot)

    summary = evolution.get_evolution_summary()

    assert summary["total_snapshots"] == 3
    assert summary["oldest_snapshot"] is not None
    assert summary["newest_snapshot"] is not None
    assert "curiosity_change" in summary["trends"]


def test_processing_pattern_detection(mock_state, mock_memory, mock_llm, temp_history_dir):
    """_detect_processing_patterns should analyze fragments correctly."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    # Add collision fragments
    for i in range(5):
        fragment = WorldFragment(
            title=f"Collision {i}",
            content="Content",
            fit_path="collision",
            created_at=datetime.now(),
        )
        mock_memory.write_fragment(fragment)

    # Add translation fragment
    fragment = WorldFragment(
        title="Translation 1",
        content="Content",
        fit_path="translation",
        created_at=datetime.now(),
    )
    mock_memory.write_fragment(fragment)

    patterns = evolution._detect_processing_patterns()

    assert "favors collision" in patterns


def test_review_prompt_format(mock_state, mock_memory, mock_llm, temp_history_dir):
    """Review prompt should include all required sections."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    prompt = evolution._build_review_prompt(None)

    assert "【当前状态】" in prompt
    assert "【历史状态】" in prompt
    assert "好奇心强度" in prompt
    assert "契合度阈值" in prompt
    assert "格式" in prompt


def test_llm_response_parsing(mock_state, mock_memory, mock_llm, temp_history_dir):
    """LLM response should be parsed correctly."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    response = mock_llm.complete_str("", "")

    parsed = evolution._parse_llm_response(response)

    assert parsed["success"] is True
    assert "change_description" in parsed  # key is change_description, not 变化描述
    assert "has_drift" in parsed
    assert "has_growth" in parsed


def test_snapshot_serialization(mock_state, mock_memory, mock_llm, temp_history_dir):
    """Snapshot should serialize and deserialize correctly."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    snapshot = evolution.take_snapshot()
    snapshot_dict = snapshot.to_dict()
    restored = PersonalitySnapshot.from_dict(snapshot_dict)

    assert restored.curiosity_level == snapshot.curiosity_level
    assert restored.fit_threshold == snapshot.fit_threshold
    assert restored.captured_at == snapshot.captured_at


def test_corpus_size_tracking(mock_state, mock_memory, mock_llm, temp_history_dir):
    """Evolution should track corpus size correctly."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    initial_size = evolution._get_corpus_size()
    assert initial_size == 0

    # Add fragments
    for i in range(5):
        fragment = WorldFragment(
            title=f"Fragment {i}",
            content=f"Content {i}",
            fit_path="translation",
            created_at=datetime.now(),
        )
        mock_memory.write_fragment(fragment)

    new_size = evolution._get_corpus_size()
    assert new_size == 5


def test_review_saves_snapshot(mock_state, mock_memory, mock_llm, temp_history_dir):
    """review() should save the current snapshot."""
    evolution = EvolutionSystem(
        state=mock_state,
        memory=mock_memory,
        llm=mock_llm,
        history_dir=temp_history_dir,
    )

    initial_count = len(evolution.load_snapshots())
    evolution.review()
    after_count = len(evolution.load_snapshots())

    assert after_count == initial_count + 1
