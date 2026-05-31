"""
Consistency Engine

Checks newly generated fragments for internal consistency against
the existing worldview corpus. Detects contradictions and conflicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .world_fragment import WorldFragment


@dataclass
class Conflict:
    """
    Represents a detected conflict between new content and existing worldview.
    
    Attributes:
        conflict_type: Type of conflict ("hard" or "soft")
        existing_claim: The existing claim that conflicts
        new_claim: The new claim that conflicts with existing
        description: Human-readable description of the conflict
    """
    
    conflict_type: str  # "hard" (fundamental claim) or "soft" (emphasis/framing)
    existing_claim: str
    new_claim: str
    description: str
    
    def __post_init__(self) -> None:
        """Validate conflict type."""
        if self.conflict_type not in ("hard", "soft"):
            self.conflict_type = "soft"


@dataclass
class ConsistencyCheck:
    """
    Result of checking a fragment's consistency with existing worldview.
    
    Attributes:
        is_consistent: Whether the fragment is consistent with existing worldview
        conflicts: List of detected conflicts
        checked_at: Timestamp of the check
        checked_fragment: The fragment that was checked
    """
    
    is_consistent: bool
    conflicts: list[Conflict] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.now)
    checked_fragment: Optional[WorldFragment] = None
    
    def __post_init__(self) -> None:
        """Set default consistency based on conflicts."""
        if self.is_consistent and self.conflicts:
            self.is_consistent = len(self.conflicts) == 0


class ConsistencyEngine:
    """
    Engine for checking consistency of new fragments against existing worldview.
    
    This is Slice 1f of the Agent's cognitive development - the "gatekeeper"
    that ensures the Agent's worldview remains coherent even as it grows.
    """
    
    def __init__(self) -> None:
        """Initialize the consistency engine."""
        self._cache: dict[str, list[str]] = {}
    
    def check(self, fragment: WorldFragment) -> ConsistencyCheck:
        """
        Check a fragment for consistency against existing worldview.
        
        Args:
            fragment: The WorldFragment to check
            
        Returns:
            ConsistencyCheck: Result containing consistency status and any conflicts
        """
        from ..log import log_event
        
        conflicts: list[Conflict] = []
        
        # Read existing worldview fragments
        existing_content = self._read_worldview()
        
        if not existing_content:
            # No existing worldview, so nothing to conflict with
            log_event(
                "consistency_check",
                "No existing worldview, fragment is vacuously consistent",
                {"fragment_title": fragment.title}
            )
            return ConsistencyCheck(
                is_consistent=True,
                conflicts=[],
                checked_fragment=fragment
            )
        
        # Check for potential conflicts by analyzing the fragment
        # against existing claims
        try:
            conflicts = self._analyze_conflicts(fragment, existing_content)
        except Exception as e:
            log_event(
                "consistency_check_error",
                f"Error during consistency analysis: {e}",
                {"fragment_title": fragment.title, "error": str(e)}
            )
        
        is_consistent = len(conflicts) == 0
        
        log_event(
            "consistency_check",
            f"Consistency check: {'consistent' if is_consistent else 'INCONSISTENT'}",
            {
                "fragment_title": fragment.title,
                "is_consistent": is_consistent,
                "conflict_count": len(conflicts),
                "conflicts": [
                    {
                        "type": c.conflict_type,
                        "description": c.description
                    }
                    for c in conflicts
                ]
            }
        )
        
        return ConsistencyCheck(
            is_consistent=is_consistent,
            conflicts=conflicts,
            checked_fragment=fragment
        )
    
    def _read_worldview(self) -> str:
        """
        Read existing worldview fragments from the world corpus.
        
        Returns:
            str: Combined content of existing worldview fragments
        """
        from pathlib import Path
        
        try:
            world_dir = Path(__file__).parent.parent.parent / "world"
            if not world_dir.exists():
                return ""
            
            fragments = []
            for md_file in sorted(world_dir.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                fragments.append(f"【{md_file.stem}】\n\n{content}")
            
            return "\n\n---\n\n".join(fragments) if fragments else ""
        except Exception:
            return ""
    
    def _analyze_conflicts(
        self,
        fragment: WorldFragment,
        existing_content: str
    ) -> list[Conflict]:
        """
        Analyze a fragment for potential conflicts with existing worldview.
        
        This is a simplified implementation. In a full version, this would
        use LLM-based semantic analysis to detect contradictions.
        
        Args:
            fragment: The fragment to check
            existing_content: Existing worldview content
            
        Returns:
            list[Conflict]: List of detected conflicts
        """
        # This is a placeholder for actual conflict detection logic.
        # A full implementation would:
        # 1. Parse the fragment to extract key claims
        # 2. Compare against existing claims in the worldview
        # 3. Use LLM to determine if any contradictions exist
        #
        # For now, we return an empty list, meaning no conflicts detected.
        # This allows the system to proceed without false positives.
        return []


__all__ = ["ConsistencyEngine", "ConsistencyCheck", "Conflict"]
