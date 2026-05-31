"""
Curiosity System

Models the Agent's curiosity about the vault's semantic space.
Maintains a map of explored vs. unexplored territory, identifies gaps,
and proposes exploration tasks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .memory import MemorySystem
from .world_fragment import WorldFragment
from .vault import get_vault_path


@dataclass
class TerritoryNode:
    """
    A node in the Agent's curiosity map.

    Attributes:
        path: File path or concept identifier
        explored: Whether this node has been fully explored
        explored_at: Timestamp of last exploration
        link_count: How many links reference this node
        orphans: List of linked paths that haven't been explored
    """
    path: str
    explored: bool
    explored_at: Optional[datetime]
    link_count: int
    orphans: list[str] = field(default_factory=list)


@dataclass
class ExplorationProposal:
    """
    A proposed exploration task from the curiosity system.

    Attributes:
        target_path: Path to explore
        target_title: Human-readable title
        reason: Why this is worth exploring
        urgency: Urgency score from 0.0 to 1.0
        created_at: When this proposal was created
    """
    target_path: str
    target_title: str
    reason: str
    urgency: float
    created_at: datetime


class CuriositySystem:
    """
    Models the Agent's curiosity about the vault's semantic space.

    The curiosity system builds a map of the vault's territory by:
    1. Reading all world fragments from agent/world/
    2. Extracting all [[wikilinks]] from each fragment
    3. Marking linked files as "referenced"
    4. Marking processed files as "explored"
    5. Files that are linked but not explored are "orphans"

    Exploration proposals are generated based on urgency scores that
    consider exploration status, link importance, and time since last access.
    """

    # Constants for urgency calculation
    NOT_EXPLORED_WEIGHT = 0.3
    ORPHAN_WEIGHT = 0.3
    MANY_LINKS_WEIGHT = 0.2
    OLD_EXPLORATION_WEIGHT = 0.2

    # Thresholds
    DEFAULT_URGENCY_THRESHOLD = 0.3
    MAX_EXPLORATION_GAP_DAYS = 14.0
    MANY_LINKS_THRESHOLD = 5

    def __init__(self, memory: MemorySystem):
        """
        Initialize the curiosity system.

        Args:
            memory: The MemorySystem instance to query for fragments
        """
        self.memory = memory
        self._map: dict[str, TerritoryNode] = {}
        self._last_build: Optional[datetime] = None
        self._explored_paths: set[str] = set()
        self._linked_paths: set[str] = set()

    def build_map(self) -> dict[str, TerritoryNode]:
        """
        Build/update the curiosity map from the world corpus.

        Scans all world fragments, extracts wikilinks, and builds
        a territory map with exploration status.

        Returns:
            dict[str, TerritoryNode]: The curiosity map keyed by path
        """
        self._map.clear()
        self._explored_paths.clear()
        self._linked_paths.clear()

        fragments = self.memory.read_all_fragments()

        # First pass: mark all fragment titles as explored
        for fragment in fragments:
            self._explored_paths.add(fragment.title.lower())
            node = TerritoryNode(
                path=fragment.title,
                explored=True,
                explored_at=fragment.created_at,
                link_count=0,
                orphans=[]
            )
            self._map[fragment.title.lower()] = node

        # Second pass: extract wikilinks and count references
        link_counts: dict[str, int] = {}
        all_links: set[str] = set()

        for fragment in fragments:
            for link in fragment.links:
                link_lower = link.lower()
                all_links.add(link_lower)
                self._linked_paths.add(link_lower)
                link_counts[link_lower] = link_counts.get(link_lower, 0) + 1

        # Update link counts in the map
        for link_lower, count in link_counts.items():
            if link_lower in self._map:
                self._map[link_lower].link_count = count
            else:
                # Linked but not explored - orphan node
                self._map[link_lower] = TerritoryNode(
                    path=link,
                    explored=False,
                    explored_at=None,
                    link_count=count,
                    orphans=[]
                )

        # Identify orphans: linked but not explored
        for node in self._map.values():
            if not node.explored and node.link_count > 0:
                for other_node in self._map.values():
                    if other_node.explored and other_node.link_count > 0:
                        node.orphans.append(other_node.path)

        self._last_build = datetime.now()
        return self._map

    def identify_gaps(self) -> list[str]:
        """
        Find orphan concepts — files referenced but not explored.

        These are concepts that appear in wikilinks but haven't been
        processed into world fragments yet.

        Returns:
            list[str]: List of orphan concept titles
        """
        if not self._map:
            self.build_map()

        orphans = []
        for path, node in self._map.items():
            if not node.explored and node.link_count > 0:
                orphans.append(node.path)

        return sorted(orphans, key=lambda p: self._map[p.lower()].link_count, reverse=True)

    def identify_orphans(self) -> list[str]:
        """
        Find files in vault that are not linked from the world corpus.

        These are potential exploration targets that exist in the vault
        but aren't referenced by any world fragment yet.

        Returns:
            list[str]: List of orphan file paths
        """
        if not self._map:
            self.build_map()

        try:
            vault_path = get_vault_path()
            all_md_files: set[str] = set()

            # Scan vault for markdown files (excluding agent/ directory)
            for md_file in vault_path.rglob("*.md"):
                relative = md_file.relative_to(vault_path)
                if not any(part == "agent" for part in relative.parts):
                    all_md_files.add(relative.stem.lower())

            # Find files not in the linked set
            orphan_files = []
            for md_file in all_md_files:
                if md_file not in self._linked_paths and md_file not in self._explored_paths:
                    orphan_files.append(md_file)

            return orphan_files

        except Exception:
            return []

    def propose_exploration(self) -> list[ExplorationProposal]:
        """
        Generate exploration proposals sorted by urgency.

        Uses the curiosity intensity to determine how many proposals
        to generate and the urgency threshold.

        Returns:
            list[ExplorationProposal]: Sorted list of exploration proposals
        """
        if not self._map:
            self.build_map()

        proposals: list[ExplorationProposal] = []
        curiosity = self.get_curiosity_intensity()

        # Adjust threshold based on curiosity
        threshold = self.DEFAULT_URGENCY_THRESHOLD * (1.0 - curiosity * 0.3)

        # Find gaps (orphans)
        gaps = self.identify_gaps()

        for gap_path in gaps:
            node = self._map.get(gap_path.lower())
            if node:
                urgency = self._calculate_urgency(gap_path, node)

                if urgency >= threshold:
                    reason = self._build_reason(node)
                    proposals.append(ExplorationProposal(
                        target_path=gap_path,
                        target_title=self._make_title(gap_path),
                        reason=reason,
                        urgency=urgency,
                        created_at=datetime.now()
                    ))

        # Also consider orphan vault files
        orphan_files = self.identify_orphans()
        for orphan_path in orphan_files[:5]:  # Limit to top 5
            urgency = 0.2  # Base urgency for unreferenced files
            proposals.append(ExplorationProposal(
                target_path=orphan_path,
                target_title=self._make_title(orphan_path),
                reason="Unexplored file in vault — may contain relevant knowledge",
                urgency=urgency,
                created_at=datetime.now()
            ))

        # Sort by urgency descending
        proposals.sort(key=lambda p: p.urgency, reverse=True)

        # Limit proposals based on curiosity
        max_proposals = max(3, int(10 * curiosity))
        return proposals[:max_proposals]

    def _calculate_urgency(self, path: str, node: TerritoryNode) -> float:
        """
        Calculate how urgently this should be explored.

        Factors:
        - Not yet explored: high urgency
        - Orphan (linked but not read): medium urgency
        - Has many links (important concept): higher urgency
        - Age of last exploration: older = higher urgency

        Args:
            path: The path/title of the node
            node: The territory node

        Returns:
            float: Urgency score from 0.0 to 1.0
        """
        # Not explored factor
        not_explored = 1.0 if not node.explored else 0.0

        # Orphan factor (linked but not explored)
        orphan = 1.0 if not node.explored and node.link_count > 0 else 0.0

        # Many links factor (important concept)
        many_links = min(node.link_count / self.MANY_LINKS_THRESHOLD, 1.0)

        # Old exploration factor
        old_exploration = 0.0
        if node.explored_at:
            days_since = (datetime.now() - node.explored_at).days
            old_exploration = min(days_since / self.MAX_EXPLORATION_GAP_DAYS, 1.0)
        elif not node.explored:
            # Unexplored orphans get medium-high old exploration score
            old_exploration = 0.7

        urgency = (
            not_explored * self.NOT_EXPLORED_WEIGHT +
            orphan * self.ORPHAN_WEIGHT +
            many_links * self.MANY_LINKS_WEIGHT +
            old_exploration * self.OLD_EXPLORATION_WEIGHT
        )

        return max(0.0, min(1.0, urgency))

    def _build_reason(self, node: TerritoryNode) -> str:
        """
        Build a human-readable reason for exploring this node.

        Args:
            node: The territory node

        Returns:
            str: Reason string
        """
        reasons = []

        if not node.explored:
            reasons.append("referenced in other fragments but not yet explored")

        if node.link_count > 0:
            if node.link_count >= self.MANY_LINKS_THRESHOLD:
                reasons.append(f"referenced {node.link_count} times — likely important concept")
            else:
                reasons.append(f"referenced {node.link_count} time{'s' if node.link_count > 1 else ''}")

        if not reasons:
            reasons.append("potential knowledge gap")

        return "; ".join(reasons)

    def _make_title(self, path: str) -> str:
        """
        Create a human-readable title from a path.

        Args:
            path: File path or concept

        Returns:
            str: Title-cased title
        """
        # Remove file extension if present
        title = re.sub(r'\.md$', '', path)
        # Replace dashes and underscores with spaces
        title = re.sub(r'[-_]+', ' ', title)
        # Title case
        title = ' '.join(word.capitalize() for word in title.split())
        return title

    def mark_explored(self, path: str) -> None:
        """
        Mark a path as explored.

        Args:
            path: The path or title to mark as explored
        """
        path_lower = path.lower()

        if path_lower in self._map:
            self._map[path_lower].explored = True
            self._map[path_lower].explored_at = datetime.now()
        else:
            self._map[path_lower] = TerritoryNode(
                path=path,
                explored=True,
                explored_at=datetime.now(),
                link_count=0,
                orphans=[]
            )

        self._explored_paths.add(path_lower)

    def get_curiosity_intensity(self) -> float:
        """
        Get current curiosity intensity (from Agent state).

        Returns a value from 0.0 (bored) to 1.0 (highly curious).
        Based on:
        - Time since last exploration
        - Number of recently added world fragments
        - World corpus size

        High curiosity → more exploration proposals, lower urgency threshold
        Low curiosity → fewer proposals, higher urgency threshold

        Returns:
            float: Curiosity intensity from 0.0 to 1.0
        """
        base_intensity = 0.5

        # Check time since last exploration
        time_factor = 0.0
        if self._last_build:
            days_since = (datetime.now() - self._last_build).days
            time_factor = min(days_since / 7.0, 1.0)  # Max curiosity after 7 days

        # Check world corpus size
        size_factor = 0.0
        try:
            fragments = self.memory.read_all_fragments()
            corpus_size = len(fragments)
            # More fragments = more curiosity about gaps
            size_factor = min(corpus_size / 20.0, 1.0)
        except Exception:
            pass

        # Check for new content
        new_content_factor = 0.0
        try:
            fragments = self.memory.read_all_fragments()
            recent_cutoff = datetime.now() - timedelta(days=3)
            recent_count = sum(1 for f in fragments if f.created_at > recent_cutoff)
            new_content_factor = min(recent_count / 5.0, 1.0)
        except Exception:
            pass

        # Combine factors
        curiosity = (
            base_intensity * 0.3 +
            time_factor * 0.3 +
            size_factor * 0.2 +
            new_content_factor * 0.2
        )

        return max(0.0, min(1.0, curiosity))

    def get_map_summary(self) -> dict:
        """
        Get a summary of the curiosity map state.

        Returns:
            dict: Summary with counts and statistics
        """
        if not self._map:
            self.build_map()

        explored = sum(1 for n in self._map.values() if n.explored)
        orphans = sum(1 for n in self._map.values() if not n.explored and n.link_count > 0)
        total_links = sum(n.link_count for n in self._map.values())

        return {
            "total_nodes": len(self._map),
            "explored": explored,
            "orphans": orphans,
            "total_links": total_links,
            "curiosity_intensity": self.get_curiosity_intensity(),
            "last_build": self._last_build.isoformat() if self._last_build else None,
        }


__all__ = ["CuriositySystem", "TerritoryNode", "ExplorationProposal"]
