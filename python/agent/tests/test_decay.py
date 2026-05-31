"""
Tests for the Memory Decay System
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.core.decay import MemoryEntry


# Set up mock vault path before importing decay module
MOCK_VAULT_PATH = Path(tempfile.mkdtemp())


@pytest.fixture
def mock_vault():
    """Create a mock vault directory."""
    vault = MOCK_VAULT_PATH / "agent"
    vault.mkdir(parents=True, exist_ok=True)
    world_dir = vault / "world"
    world_dir.mkdir(parents=True, exist_ok=True)
    return vault


@pytest.fixture
def mock_env_vault(mock_vault):
    """Patch the vault path environment variable."""
    with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(mock_vault)}):
        yield mock_vault


@pytest.fixture
def memory_index_file(mock_vault):
    """Create the memory index file."""
    index_path = mock_vault / "agent" / "memory-index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
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


class TestMemoryEntry:
    """Tests for the MemoryEntry dataclass."""

    def test_create_new_starts_vivid(self):
        """New fragments should have freshness = 1.0."""
        entry = MemoryEntry.create_new("world/测试.md")

        assert entry.freshness_score == 1.0
        assert entry.access_count == 0
        assert entry.file_path == "world/测试.md"
        assert isinstance(entry.last_accessed, datetime)

    def test_entry_to_dict(self):
        """Entry should serialize correctly."""
        entry = MemoryEntry(
            file_path="world/测试.md",
            last_accessed=datetime(2026, 5, 31, 14, 0, 0),
            access_count=3,
            freshness_score=0.75,
        )

        data = entry.to_dict()

        assert data["file_path"] == "world/测试.md"
        assert data["last_accessed"] == "2026-05-31T14:00:00"
        assert data["access_count"] == 3
        assert data["freshness_score"] == 0.75

    def test_entry_from_dict(self):
        """Entry should deserialize correctly."""
        data = {
            "file_path": "world/测试.md",
            "last_accessed": "2026-05-31T14:00:00",
            "access_count": 3,
            "freshness_score": 0.75,
        }

        entry = MemoryEntry.from_dict(data)

        assert entry.file_path == "world/测试.md"
        assert entry.last_accessed == datetime(2026, 5, 31, 14, 0, 0)
        assert entry.access_count == 3
        assert entry.freshness_score == 0.75


class TestMemoryDecay:
    """Tests for the MemoryDecay class."""

    def test_new_fragment_starts_vivid(self, mock_env_vault, memory_index_file):
        """New fragments should have freshness = 1.0."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)
        decay.on_fragment_written("world/关于虚无的随笔.md")

        entry = decay.get_entry("world/关于虚无的随笔.md")
        assert entry is not None
        assert entry.freshness_score == 1.0

    def test_decay_over_time(self, mock_env_vault, memory_index_file):
        """Freshness should decrease as time passes."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        entry = MemoryEntry.from_dict({
            "file_path": "test/path.md",
            "last_accessed": (datetime.now() - timedelta(days=45)).isoformat(),
            "access_count": 5,
            "freshness_score": 1.0,
        })
        decay._entries["test/path.md"] = entry

        freshness = decay.calculate_freshness(entry)
        assert 0.4 < freshness < 0.6

    def test_decay_after_max_age(self, mock_env_vault, memory_index_file):
        """Freshness should approach 0 after max age days."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        entry = MemoryEntry.from_dict({
            "file_path": "test/old.md",
            "last_accessed": (datetime.now() - timedelta(days=100)).isoformat(),
            "access_count": 5,
            "freshness_score": 1.0,
        })

        freshness = decay.calculate_freshness(entry)
        assert freshness < 0.1

    def test_frequent_access_maintains_freshness(self, mock_env_vault, memory_index_file):
        """Frequently accessed fragments should stay vivid."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        entry = MemoryEntry.from_dict({
            "file_path": "test/frequent.md",
            "last_accessed": (datetime.now() - timedelta(days=30)).isoformat(),
            "access_count": 10,
            "freshness_score": 1.0,
        })

        freshness = decay.calculate_freshness(entry)
        assert freshness > 0.5

    def test_record_access_increments_count(self, mock_env_vault, memory_index_file):
        """Recording access should increment the access count."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)
        decay.on_fragment_written("test/path.md")

        initial_count = decay.get_entry("test/path.md").access_count

        decay.record_access("test/path.md")
        decay.record_access("test/path.md")

        entry = decay.get_entry("test/path.md")
        assert entry.access_count == initial_count + 2

    def test_on_fragment_written(self, mock_env_vault, memory_index_file):
        """Newly written fragments should have freshness 1.0."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        decay.on_fragment_written("world/新随笔.md")

        entry = decay.get_entry("world/新随笔.md")
        assert entry is not None
        assert entry.freshness_score == 1.0
        assert entry.access_count == 0

    def test_on_fragment_read(self, mock_env_vault, memory_index_file):
        """Reading a fragment should record access."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)
        decay.on_fragment_written("test/read.md")

        before_read = decay.get_entry("test/read.md").access_count

        decay.on_fragment_read("test/read.md")

        after_read = decay.get_entry("test/read.md").access_count
        assert after_read == before_read + 1

    def test_on_fragment_referenced(self, mock_env_vault, memory_index_file):
        """Referencing a fragment should partially refresh it."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        entry = MemoryEntry.from_dict({
            "file_path": "test/ref.md",
            "last_accessed": (datetime.now() - timedelta(days=30)).isoformat(),
            "access_count": 2,
            "freshness_score": 0.3,
        })
        decay._entries["test/ref.md"] = entry

        decay.on_fragment_referenced("test/ref.md")

        result = decay.get_entry("test/ref.md")
        assert result.access_count == 3

    def test_get_vivid_fragments(self, mock_env_vault, memory_index_file):
        """Should return fragments above threshold."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        vivid_entry = MemoryEntry.from_dict({
            "file_path": "world/vivid.md",
            "last_accessed": datetime.now().isoformat(),
            "access_count": 5,
            "freshness_score": 0.8,
        })
        decay._entries["world/vivid.md"] = vivid_entry
        world_dir = mock_env_vault / "world"
        world_dir.mkdir(exist_ok=True)
        (world_dir / "vivid.md").touch()

        faded_entry = MemoryEntry.from_dict({
            "file_path": "world/faded.md",
            "last_accessed": (datetime.now() - timedelta(days=100)).isoformat(),
            "access_count": 1,
            "freshness_score": 0.1,
        })
        decay._entries["world/faded.md"] = faded_entry
        (world_dir / "faded.md").touch()

        vivid = decay.get_vivid_fragments(threshold=0.5)

        vivid_paths = [str(p) for p in vivid]
        assert any("vivid.md" in p for p in vivid_paths)
        assert not any("faded.md" in p for p in vivid_paths)

    def test_get_faded_fragments(self, mock_env_vault, memory_index_file):
        """Should return fragments below threshold."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        vivid_entry = MemoryEntry.from_dict({
            "file_path": "world/vivid.md",
            "last_accessed": datetime.now().isoformat(),
            "access_count": 5,
            "freshness_score": 0.8,
        })
        decay._entries["world/vivid.md"] = vivid_entry
        world_dir = mock_env_vault / "world"
        world_dir.mkdir(exist_ok=True)
        (world_dir / "vivid.md").touch()

        faded_entry = MemoryEntry.from_dict({
            "file_path": "world/faded.md",
            "last_accessed": (datetime.now() - timedelta(days=100)).isoformat(),
            "access_count": 1,
            "freshness_score": 0.1,
        })
        decay._entries["world/faded.md"] = faded_entry
        (world_dir / "faded.md").touch()

        faded = decay.get_faded_fragments(threshold=0.3)

        faded_paths = [str(p) for p in faded]
        assert any("faded.md" in p for p in faded_paths)
        assert not any("vivid.md" in p for p in faded_paths)

    def test_decay_all(self, mock_env_vault, memory_index_file):
        """decay_all should update all freshness scores."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        entry = MemoryEntry.from_dict({
            "file_path": "test/old.md",
            "last_accessed": (datetime.now() - timedelta(days=50)).isoformat(),
            "access_count": 5,
            "freshness_score": 1.0,
        })
        decay._entries["test/old.md"] = entry

        results = decay.decay_all()

        assert len(results) > 0
        assert any("test/old.md" in path for path, _ in results)

        old_entry = decay.get_entry("test/old.md")
        assert old_entry.freshness_score < 1.0


class TestMemoryIndexPersistence:
    """Tests for memory index persistence."""

    def test_memory_index_persistence(self, mock_env_vault, memory_index_file):
        """Memory index should be saved and loaded correctly."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)
        decay.on_fragment_written("world/持久化测试.md")
        decay.record_access("world/持久化测试.md")

        decay2 = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        entry = decay2.get_entry("world/持久化测试.md")
        assert entry is not None
        assert entry.access_count >= 1

    def test_index_updates_on_mutation(self, mock_env_vault, memory_index_file):
        """Index should be updated on every mutation."""
        from agent.core.decay import MemoryDecay

        decay = MemoryDecay(max_age_days=90.0, min_access_for_vivid=5)

        decay.on_fragment_written("world/更新测试.md")

        index_path = mock_env_vault / "agent" / "memory-index.json"
        index_data = json.loads(index_path.read_text(encoding="utf-8"))

        assert "decay_entries" in index_data
        assert "world/更新测试.md" in index_data["decay_entries"]
