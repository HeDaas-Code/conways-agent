"""
Memory Decay System

Simulates forgetting over time — fragments that haven't been accessed or referenced
gradually become "faded" and less likely to be retrieved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .vault import get_vault_path, get_memory_index_path, load_memory_index, save_memory_index


# Constants for decay calculation
MAX_AGE_DAYS: float = 90.0  # Fragment fades to 0 after 90 days
MIN_ACCESS_FOR_VIVID: int = 5  # Need 5 accesses to be considered "vivid"


@dataclass
class MemoryEntry:
    """An entry in the memory index tracking access and freshness."""
    file_path: str
    last_accessed: datetime
    access_count: int
    freshness_score: float  # 0.0 (faded) to 1.0 (vivid)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "file_path": self.file_path,
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "freshness_score": self.freshness_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        """Create from dictionary."""
        last_accessed = data.get("last_accessed")
        if isinstance(last_accessed, str):
            last_accessed = datetime.fromisoformat(last_accessed)
        elif last_accessed is None:
            last_accessed = datetime.now()

        return cls(
            file_path=data.get("file_path", ""),
            last_accessed=last_accessed,
            access_count=data.get("access_count", 0),
            freshness_score=data.get("freshness_score", 1.0),
        )

    @classmethod
    def create_new(cls, file_path: str) -> MemoryEntry:
        """Create a new memory entry with maximum freshness."""
        return cls(
            file_path=file_path,
            last_accessed=datetime.now(),
            access_count=0,
            freshness_score=1.0,
        )


class MemoryDecay:
    """
    Manages memory decay — simulates forgetting over time.

    Freshness score formula:
        freshness = base * (1 - time_factor) * access_factor

    Where:
        - time_factor = min(days_since_access / max_age_days, 1.0)
        - access_factor = min(access_count / min_access_for_vivid, 1.0)
        - base starts at 1.0 for newly written fragments
    """

    def __init__(
        self,
        memory_system: Optional[object] = None,
        max_age_days: float = MAX_AGE_DAYS,
        min_access_for_vivid: int = MIN_ACCESS_FOR_VIVID,
    ) -> None:
        """
        Initialize the memory decay system.

        Args:
            memory_system: Optional MemorySystem instance for integration
            max_age_days: Days until freshness reaches 0
            min_access_for_vivid: Access count needed to maintain vividness
        """
        self.memory = memory_system
        self._max_age_days = max_age_days
        self._min_access_for_vivid = min_access_for_vivid
        self._index_path = get_memory_index_path()
        self._entries: dict[str, MemoryEntry] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load the memory index from file."""
        index = load_memory_index()

        entries_data = index.get("decay_entries", {})
        for file_path, entry_data in entries_data.items():
            self._entries[file_path] = MemoryEntry.from_dict(entry_data)

    def _save_index(self) -> None:
        """Save the memory index to file."""
        index = load_memory_index()

        decay_entries = {}
        for file_path, entry in self._entries.items():
            decay_entries[file_path] = entry.to_dict()

        index["decay_entries"] = decay_entries
        index["updated"] = datetime.now().isoformat()

        save_memory_index(index)

    def record_access(self, path: str) -> None:
        """
        Record that a fragment was accessed.

        Args:
            path: Path to the accessed fragment (relative to vault)
        """
        path_key = str(path)

        if path_key in self._entries:
            entry = self._entries[path_key]
            entry.last_accessed = datetime.now()
            entry.access_count += 1
            entry.freshness_score = self.calculate_freshness(entry)
        else:
            entry = MemoryEntry.create_new(path_key)
            entry.last_accessed = datetime.now()
            entry.access_count = 1
            entry.freshness_score = 1.0
            self._entries[path_key] = entry

        self._save_index()

    def calculate_freshness(self, entry: MemoryEntry) -> float:
        """
        Calculate freshness score based on time since last access and access count.

        Args:
            entry: The memory entry to calculate freshness for

        Returns:
            float: Freshness score between 0.0 and 1.0
        """
        now = datetime.now()
        days_since_access = (now - entry.last_accessed).total_seconds() / (24 * 3600)

        time_factor = min(days_since_access / self._max_age_days, 1.0)
        access_factor = min(entry.access_count / self._min_access_for_vivid, 1.0)

        freshness = (1.0 - time_factor) * access_factor

        return max(0.0, min(1.0, freshness))

    def decay_all(self) -> list[tuple[str, float]]:
        """
        Apply decay to all memory entries.

        Returns:
            list[tuple[str, float]]: List of (path, new_freshness) pairs
        """
        results: list[tuple[str, float]] = []

        for path_key, entry in self._entries.items():
            entry.freshness_score = self.calculate_freshness(entry)
            results.append((path_key, entry.freshness_score))

        self._save_index()
        return results

    def get_vivid_fragments(self, threshold: float = 0.5) -> list[Path]:
        """
        Get fragments above a freshness threshold (for retrieval).

        Args:
            threshold: Minimum freshness score (default 0.5)

        Returns:
            list[Path]: List of paths to vivid fragments
        """
        vault_path = get_vault_path()
        vivid_paths: list[Path] = []

        for entry in self._entries.values():
            if entry.freshness_score >= threshold:
                full_path = vault_path / entry.file_path
                if full_path.exists():
                    vivid_paths.append(full_path)

        return vivid_paths

    def get_faded_fragments(self, threshold: float = 0.3) -> list[Path]:
        """
        Get fragments below a freshness threshold (faded from memory).

        Args:
            threshold: Maximum freshness score (default 0.3)

        Returns:
            list[Path]: List of paths to faded fragments
        """
        vault_path = get_vault_path()
        faded_paths: list[Path] = []

        for entry in self._entries.values():
            if entry.freshness_score < threshold:
                full_path = vault_path / entry.file_path
                if full_path.exists():
                    faded_paths.append(full_path)

        return faded_paths

    def on_fragment_written(self, path: str) -> None:
        """
        Called when a new fragment is written — starts with high freshness.

        Args:
            path: Path to the newly written fragment
        """
        path_key = str(path)

        entry = MemoryEntry.create_new(path_key)
        entry.freshness_score = 1.0
        self._entries[path_key] = entry

        self._save_index()

    def on_fragment_read(self, path: str) -> None:
        """
        Called when a fragment is read — refreshes freshness.

        Args:
            path: Path to the read fragment
        """
        self.record_access(path)

    def on_fragment_referenced(self, path: str) -> None:
        """
        Called when a fragment is linked to — partial refresh.

        This gives a smaller boost than full access.

        Args:
            path: Path to the referenced fragment
        """
        path_key = str(path)

        if path_key in self._entries:
            entry = self._entries[path_key]
            entry.access_count += 1
            entry.freshness_score = self.calculate_freshness(entry)
        else:
            entry = MemoryEntry.create_new(path_key)
            entry.access_count = 1
            entry.freshness_score = 0.8
            self._entries[path_key] = entry

        self._save_index()

    def get_freshness(self, path: str) -> float:
        """
        Get the current freshness score for a fragment.

        Args:
            path: Path to the fragment

        Returns:
            float: Freshness score, or 1.0 if not in index
        """
        path_key = str(path)
        if path_key in self._entries:
            return self._entries[path_key].freshness_score
        return 1.0

    def get_entry(self, path: str) -> Optional[MemoryEntry]:
        """
        Get the memory entry for a path.

        Args:
            path: Path to the fragment

        Returns:
            MemoryEntry or None if not found
        """
        return self._entries.get(str(path))


# Global instance for easy access
_decay_instance: Optional[MemoryDecay] = None


def get_decay_system() -> MemoryDecay:
    """
    Get the global memory decay system instance.

    Returns:
        MemoryDecay: The global instance
    """
    global _decay_instance
    if _decay_instance is None:
        _decay_instance = MemoryDecay()
    return _decay_instance


__all__ = ["MemoryDecay", "MemoryEntry", "get_decay_system"]
