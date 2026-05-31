"""
Tests for CuriositySystem

Tests the curiosity system's ability to build maps, identify gaps,
and generate exploration proposals.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from agent.core.curiosity import CuriositySystem, TerritoryNode, ExplorationProposal
from agent.core.memory import MemorySystem
from agent.core.world_fragment import WorldFragment


@pytest.fixture
def temp_world_dir(tmp_path):
    """Create a temporary world directory."""
    world_dir = tmp_path / "agent" / "world"
    world_dir.mkdir(parents=True)
    return world_dir


@pytest.fixture
def memory_system(temp_world_dir, monkeypatch):
    """Create a memory system with temp directory."""
    # Mock vault path for the test
    vault_path = temp_world_dir.parent.parent
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_path))

    return MemorySystem(world_dir=temp_world_dir, enable_index=False)


@pytest.fixture
def curiosity_system(memory_system):
    """Create a curiosity system with test memory."""
    return CuriositySystem(memory_system)


class TestBuildMap:
    """Tests for build_map functionality."""

    def test_build_map_from_fragments(self, memory_system, curiosity_system):
        """Map should correctly identify explored vs linked vs orphan."""
        # Create fragments with links
        fragment1 = WorldFragment(
            title="Concept A",
            content="This is about concept A.",
            links=["Concept B", "Concept C"],
            created_at=datetime.now()
        )
        fragment2 = WorldFragment(
            title="Concept B",
            content="This is about concept B.",
            links=["Concept A"],
            created_at=datetime.now()
        )

        memory_system.write_fragment(fragment1)
        memory_system.write_fragment(fragment2)

        # Build the curiosity map
        curiosity_map = curiosity_system.build_map()

        # Both fragments should be explored
        assert curiosity_map["concept a"].explored is True
        assert curiosity_map["concept b"].explored is True

        # Concept C is linked but not explored (orphan)
        assert curiosity_map["concept c"].explored is False
        assert curiosity_map["concept c"].link_count == 1

    def test_build_map_tracks_link_counts(self, memory_system, curiosity_system):
        """Link counts should be correctly tracked across fragments."""
        fragment1 = WorldFragment(
            title="Main Topic",
            content="Main topic content.",
            links=["Topic A", "Topic B"],
            created_at=datetime.now()
        )
        fragment2 = WorldFragment(
            title="Topic A",
            content="Topic A content.",
            links=["Topic B"],
            created_at=datetime.now()
        )
        fragment3 = WorldFragment(
            title="Topic B",
            content="Topic B content.",
            links=[],
            created_at=datetime.now()
        )

        memory_system.write_fragment(fragment1)
        memory_system.write_fragment(fragment2)
        memory_system.write_fragment(fragment3)

        curiosity_map = curiosity_system.build_map()

        # Topic A should have link_count >= 1 (from Main Topic)
        assert curiosity_map["topic a"].link_count >= 1
        assert curiosity_map["topic b"].explored is True

    def test_empty_memory_returns_empty_map(self, curiosity_system):
        """Empty memory should return empty map."""
        curiosity_map = curiosity_system.build_map()
        assert len(curiosity_map) == 0


class TestIdentifyOrphans:
    """Tests for orphan identification."""

    def test_identify_orphans_finds_unlinked(self, memory_system, curiosity_system):
        """Orphan detection should find unreferenced files."""
        # Create fragments that link to Concept A
        fragment1 = WorldFragment(
            title="Source Fragment",
            content="Links to Concept A.",
            links=["Concept A"],
            created_at=datetime.now()
        )

        memory_system.write_fragment(fragment1)
        curiosity_system.build_map()

        orphans = curiosity_system.identify_gaps()

        # Concept A is referenced but not explored
        assert "Concept A" in orphans

    def test_identify_orphans_excludes_explored(self, memory_system, curiosity_system):
        """Should not include explored fragments as orphans."""
        fragment1 = WorldFragment(
            title="Explored Fragment",
            content="Already explored.",
            links=[],
            created_at=datetime.now()
        )
        fragment2 = WorldFragment(
            title="Source Fragment",
            content="Links to Explored Fragment.",
            links=["Explored Fragment"],
            created_at=datetime.now()
        )

        memory_system.write_fragment(fragment1)
        memory_system.write_fragment(fragment2)
        curiosity_system.build_map()

        orphans = curiosity_system.identify_gaps()

        # Explored Fragment is linked but also explored - not an orphan
        assert "Explored Fragment" not in orphans


class TestUrgencyCalculation:
    """Tests for urgency calculation."""

    def test_urgency_calculation_unexplored(self, curiosity_system):
        """Urgency should be higher for unexplored content."""
        # Create nodes with different exploration states
        explored_node = TerritoryNode(
            path="Explored",
            explored=True,
            explored_at=datetime.now(),
            link_count=5,
            orphans=[]
        )
        unexplored_node = TerritoryNode(
            path="Unexplored",
            explored=False,
            explored_at=None,
            link_count=5,
            orphans=[]
        )

        explored_urgency = curiosity_system._calculate_urgency("Explored", explored_node)
        unexplored_urgency = curiosity_system._calculate_urgency("Unexplored", unexplored_node)

        # Unexplored should have higher urgency
        assert unexplored_urgency > explored_urgency

    def test_urgency_calculation_many_links(self, curiosity_system):
        """Urgency should be higher for highly-linked content."""
        low_links_node = TerritoryNode(
            path="Low Links",
            explored=False,
            explored_at=None,
            link_count=1,
            orphans=[]
        )
        high_links_node = TerritoryNode(
            path="High Links",
            explored=False,
            explored_at=None,
            link_count=10,
            orphans=[]
        )

        low_urgency = curiosity_system._calculate_urgency("Low Links", low_links_node)
        high_urgency = curiosity_system._calculate_urgency("High Links", high_links_node)

        # High links should have higher urgency
        assert high_urgency > low_urgency

    def test_urgency_calculation_old_exploration(self, curiosity_system):
        """Urgency should be higher for old explorations."""
        recent_node = TerritoryNode(
            path="Recent",
            explored=True,
            explored_at=datetime.now(),
            link_count=5,
            orphans=[]
        )
        old_node = TerritoryNode(
            path="Old",
            explored=True,
            explored_at=datetime.now() - timedelta(days=30),
            link_count=5,
            orphans=[]
        )

        recent_urgency = curiosity_system._calculate_urgency("Recent", recent_node)
        old_urgency = curiosity_system._calculate_urgency("Old", old_node)

        # Old exploration should have higher urgency
        assert old_urgency > recent_urgency

    def test_urgency_normalized_to_0_1(self, curiosity_system):
        """Urgency scores should always be between 0 and 1."""
        # Test various extreme cases
        extreme_node = TerritoryNode(
            path="Extreme",
            explored=False,
            explored_at=None,
            link_count=100,  # Many more than threshold
            orphans=[]
        )

        urgency = curiosity_system._calculate_urgency("Extreme", extreme_node)
        assert 0.0 <= urgency <= 1.0


class TestExplorationProposals:
    """Tests for exploration proposal generation."""

    def test_propose_exploration_returns_proposals(self, memory_system, curiosity_system):
        """Should generate exploration proposals."""
        # Create an orphan link
        fragment1 = WorldFragment(
            title="Source",
            content="Links to orphan concept.",
            links=["Orphan Concept"],
            created_at=datetime.now()
        )
        memory_system.write_fragment(fragment1)
        curiosity_system.build_map()

        proposals = curiosity_system.propose_exploration()

        assert len(proposals) > 0
        assert all(isinstance(p, ExplorationProposal) for p in proposals)

    def test_proposals_sorted_by_urgency(self, memory_system, curiosity_system):
        """Proposals should be sorted by urgency descending."""
        fragment1 = WorldFragment(
            title="Source",
            content="Links to multiple concepts.",
            links=["High Priority", "Low Priority", "Low Priority"],
            created_at=datetime.now()
        )
        memory_system.write_fragment(fragment1)
        curiosity_system.build_map()

        proposals = curiosity_system.propose_exploration()

        if len(proposals) > 1:
            # Check descending order
            for i in range(len(proposals) - 1):
                assert proposals[i].urgency >= proposals[i + 1].urgency

    def test_proposals_have_required_fields(self, memory_system, curiosity_system):
        """Proposals should have all required fields."""
        fragment1 = WorldFragment(
            title="Source",
            content="Links to something.",
            links=["Target"],
            created_at=datetime.now()
        )
        memory_system.write_fragment(fragment1)
        curiosity_system.build_map()

        proposals = curiosity_system.propose_exploration()

        if proposals:
            proposal = proposals[0]
            assert hasattr(proposal, 'target_path')
            assert hasattr(proposal, 'target_title')
            assert hasattr(proposal, 'reason')
            assert hasattr(proposal, 'urgency')
            assert hasattr(proposal, 'created_at')
            assert 0.0 <= proposal.urgency <= 1.0


class TestMarkExplored:
    """Tests for mark_explored functionality."""

    def test_mark_explored_updates_node(self, curiosity_system):
        """Marking explored should update node status."""
        # Add an orphan node
        curiosity_system._map["orphan"] = TerritoryNode(
            path="Orphan",
            explored=False,
            explored_at=None,
            link_count=1,
            orphans=[]
        )

        curiosity_system.mark_explored("Orphan")

        assert curiosity_system._map["orphan"].explored is True
        assert curiosity_system._map["orphan"].explored_at is not None

    def test_mark_explored_creates_node_if_missing(self, curiosity_system):
        """Marking unexplored path should create new node."""
        curiosity_system.mark_explored("New Concept")

        assert "new concept" in curiosity_system._map
        assert curiosity_system._map["new concept"].explored is True


class TestCuriosityIntensity:
    """Tests for curiosity intensity calculation."""

    def test_curiosity_intensity_range(self, curiosity_system):
        """Curiosity intensity should be between 0 and 1."""
        intensity = curiosity_system.get_curiosity_intensity()
        assert 0.0 <= intensity <= 1.0

    def test_curiosity_intensity_changes_with_time(self, memory_system, curiosity_system):
        """Curiosity should increase with time since last build."""
        # Create a fragment
        fragment = WorldFragment(
            title="Test",
            content="Test content.",
            links=[],
            created_at=datetime.now()
        )
        memory_system.write_fragment(fragment)
        curiosity_system.build_map()

        initial_intensity = curiosity_system.get_curiosity_intensity()

        # Simulate time passing
        curiosity_system._last_build = datetime.now() - timedelta(days=6)
        new_intensity = curiosity_system.get_curiosity_intensity()

        # Intensity should increase (or at least not decrease)
        assert new_intensity >= initial_intensity


class TestMapSummary:
    """Tests for map summary generation."""

    def test_get_map_summary_returns_dict(self, curiosity_system):
        """Map summary should return a dictionary."""
        summary = curiosity_system.get_map_summary()

        assert isinstance(summary, dict)
        assert "total_nodes" in summary
        assert "explored" in summary
        assert "orphans" in summary
        assert "curiosity_intensity" in summary

    def test_get_map_summary_counts_correctly(self, memory_system, curiosity_system):
        """Map summary should correctly count nodes."""
        fragment1 = WorldFragment(
            title="Explored 1",
            content="Content.",
            links=["Orphan"],
            created_at=datetime.now()
        )
        fragment2 = WorldFragment(
            title="Explored 2",
            content="Content.",
            links=[],
            created_at=datetime.now()
        )

        memory_system.write_fragment(fragment1)
        memory_system.write_fragment(fragment2)
        curiosity_system.build_map()

        summary = curiosity_system.get_map_summary()

        # Should have: Explored 1, Explored 2, Orphan (3 nodes)
        assert summary["total_nodes"] == 3
        # Explored 1 and Explored 2 are explored
        assert summary["explored"] == 2
        # Orphan is not explored but linked
        assert summary["orphans"] == 1
