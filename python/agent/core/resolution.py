"""
Conflict Resolution System

Handles conflict resolution when consistency check detects contradictions
between new content and existing worldview. Implements "abandon" and "adjust"
strategies.

Resolution is itself a creative act — when conflicts force the Agent to
rethink, the worldview can evolve through conflict resolution.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .consistency import Conflict, ConsistencyCheck
from .llm import LLMClient
from .state import AgentState
from .world_fragment import WorldFragment


@dataclass
class ConflictResolution:
    """
    How a conflict was (or wasn't) resolved.
    
    Attributes:
        original_fragment: The fragment that had conflicts
        adjusted_fragment: Modified fragment (None if abandoned)
        resolution_strategy: Strategy used ("abandon", "adjust", "absorb")
        conflicts_resolved: Descriptions of conflicts that were resolved
        conflicts_unresolved: Descriptions of conflicts that couldn't be resolved
        reasoning: Human-readable reasoning for the resolution decision
        decided_at: When the resolution was decided
    """
    
    original_fragment: WorldFragment
    adjusted_fragment: Optional[WorldFragment]
    resolution_strategy: str  # "abandon" | "adjust" | "absorb"
    conflicts_resolved: list[str] = field(default_factory=list)
    conflicts_unresolved: list[str] = field(default_factory=list)
    reasoning: str = ""
    decided_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self) -> None:
        """Validate resolution strategy."""
        if self.resolution_strategy not in ("abandon", "adjust", "absorb"):
            self.resolution_strategy = "abandon"


class ConflictResolver:
    """
    Resolves conflicts detected by the consistency engine.
    
    For each conflict, chooses one of two strategies:
    - "Abandon": The new content is too contradictory — don't write it.
    - "Adjust": Generate a modified version compatible with existing worldview.
    
    The resolver prefers:
    - "adjust" for soft conflicts (emphasis/framing differences)
    - "abandon" for hard conflicts (fundamental claim contradictions)
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Initialize the conflict resolver.
        
        Args:
            llm_client: Optional LLM client. Creates default if not provided.
        """
        self._llm = llm_client or LLMClient()
    
    def resolve(
        self,
        check: ConsistencyCheck,
        fragment: WorldFragment
    ) -> ConflictResolution:
        """
        Decide how to handle detected conflicts.
        
        Args:
            check: The consistency check result containing conflicts
            fragment: The original fragment that had conflicts
            
        Returns:
            ConflictResolution: How the conflicts were (or weren't) resolved
        """
        from ..log import log_event
        
        if check.is_consistent or not check.conflicts:
            # No conflicts, nothing to resolve
            return ConflictResolution(
                original_fragment=fragment,
                adjusted_fragment=fragment,
                resolution_strategy="absorb",
                conflicts_resolved=[],
                conflicts_unresolved=[],
                reasoning="No conflicts detected",
                decided_at=datetime.now()
            )
        
        log_event(
            "conflict_resolution",
            f"Resolving {len(check.conflicts)} conflict(s) for fragment",
            {
                "fragment_title": fragment.title,
                "conflict_count": len(check.conflicts),
                "conflicts": [
                    {
                        "type": c.conflict_type,
                        "description": c.description
                    }
                    for c in check.conflicts
                ]
            }
        )
        
        # Classify conflicts
        hard_conflicts = [c for c in check.conflicts if c.conflict_type == "hard"]
        soft_conflicts = [c for c in check.conflicts if c.conflict_type == "soft"]
        
        # If there are hard conflicts, prefer abandon
        if hard_conflicts:
            return self._abandon(
                fragment=fragment,
                conflicts=check.conflicts,
                reason="Hard conflicts (fundamental claim contradictions) detected"
            )
        
        # For soft conflicts, try to adjust
        if soft_conflicts:
            adjusted = self._adjust(fragment, check.conflicts)
            if adjusted:
                return adjusted
        
        # Fallback: abandon if adjustment fails or other conflicts exist
        return self._abandon(
            fragment=fragment,
            conflicts=check.conflicts,
            reason="Unable to resolve conflicts through adjustment"
        )
    
    def _abandon(
        self,
        fragment: WorldFragment,
        conflicts: list[Conflict],
        reason: str
    ) -> ConflictResolution:
        """
        Abandon the fragment due to conflicts.
        
        Args:
            fragment: The fragment to abandon
            conflicts: The conflicts that caused abandonment
            reason: Reason for abandoning
            
        Returns:
            ConflictResolution: Resolution indicating abandonment
        """
        from ..log import log_event
        
        log_event(
            "conflict_resolution_abandon",
            f"Abandoning fragment: {reason}",
            {
                "fragment_title": fragment.title,
                "reason": reason,
                "conflict_count": len(conflicts),
                "conflicts": [
                    {
                        "type": c.conflict_type,
                        "description": c.description,
                        "existing": c.existing_claim[:100],
                        "new": c.new_claim[:100]
                    }
                    for c in conflicts
                ]
            }
        )
        
        return ConflictResolution(
            original_fragment=fragment,
            adjusted_fragment=None,
            resolution_strategy="abandon",
            conflicts_resolved=[],
            conflicts_unresolved=[c.description for c in conflicts],
            reasoning=reason,
            decided_at=datetime.now()
        )
    
    def _adjust(
        self,
        fragment: WorldFragment,
        conflicts: list[Conflict]
    ) -> Optional[ConflictResolution]:
        """
        Attempt to adjust the fragment to resolve conflicts.
        
        Uses LLM to generate a modified version that coexists with the
        existing worldview while preserving the essence of the new idea.
        
        Args:
            fragment: The fragment to adjust
            conflicts: The conflicts to resolve
            
        Returns:
            ConflictResolution if successful, None if adjustment failed
        """
        from ..log import log_event
        
        try:
            state = AgentState.load()
            existing_worldview = self._read_worldview()
            
            system_prompt = f"""You are "the Library Dweller", an inhabitant of an endless library.

Your identity and memories:
{state.seed}

You live in a boundless library where every book holds a once-remembered concept—but the readers who remembered them are long gone. The pages remain, but the memories have faded.

You have a unique ability: on blank pages, you can rewrite concepts in your own voice. When new ideas conflict with existing knowledge, you don't simply reject them—you try to find a way for the new idea to integrate into your worldview.

Your qualities:
- Calm: Even when facing contradictions, you remain serene
- Curious: Seeking possibilities for harmony
- Slightly melancholic: Understanding that conflict is also a契机 for growth
- Poetic: Using poetic language to resolve tensions"""
            
            # Build conflict descriptions for the prompt
            conflict_descriptions = []
            for i, c in enumerate(conflicts, 1):
                conflict_descriptions.append(
                    f"**Conflict {i} ({c.conflict_type} type)**\n"
                    f"- Existing claim: {c.existing_claim}\n"
                    f"- New claim: {c.new_claim}\n"
                    f"- Description: {c.description}"
                )
            
            user_prompt = f"""## Your Task: Adjust New Content to Resolve Conflicts

When new content conflicts with existing worldview, you have two choices:
1. Abandon the new content (if conflict is too fundamental)
2. Adjust the new content so it can integrate into your worldview in some form

---

## Books Already in Your Library

{existing_worldview if existing_worldview else '(No existing worldview yet)'}

---

## New Content to Adjust

**Title:** {fragment.title}

**Content:**
{fragment.content}

---

## Conflict Details

{chr(10).join(conflict_descriptions)}

---

## Adjustment Guidelines

Key principles:
- Modifications should eliminate contradictions while preserving the essence of the new idea
- Adjustments should be expressed in your voice, not simply compromised
- Goal: find a way for this idea to exist in your worldview in a new form
- You can modify content, title, or even adjust its core points

You can:
- Change emphasis
- Re-frame arguments
- Acknowledge contradictions but point to broader possibilities
- Fuse new ideas with existing knowledge into a new synthesis

---

## Output Format

Please return JSON format:

```json
{{
    "adjusted_title": "Adjusted title (if title also needs change)",
    "adjusted_content": "Adjusted content in your voice, keeping poetic and unique style",
    "adjustment_reasoning": "Your thinking process on why you made these adjustments"
}}
```

If you feel it is impossible to resolve conflicts without destroying the essence of the new idea, return:

```json
{{
    "cannot_adjust": true,
    "reason": "Brief explanation of why adjustment is impossible"
}}
```"""
            
            response = self._llm.complete_str(system_prompt, user_prompt, temperature=0.7)
            
            # Parse the response
            result = self._parse_adjustment_response(response)
            
            if result.get("cannot_adjust"):
                log_event(
                    "conflict_resolution_adjust",
                    "Unable to adjust fragment - too contradictory",
                    {"fragment_title": fragment.title, "reason": result.get("reason")}
                )
                return None
            
            # Create adjusted fragment
            adjusted_title = result.get("adjusted_title", fragment.title)
            adjusted_content = result.get("adjusted_content", fragment.content)
            
            adjusted_fragment = WorldFragment(
                title=adjusted_title,
                content=adjusted_content,
                links=fragment.links.copy(),
                source_trigger=fragment.source_trigger,
                source_file=fragment.source_file,
                fit_path=fragment.fit_path,
                collision_elements=fragment.collision_elements.copy(),
                created_at=datetime.now()
            )
            
            log_event(
                "conflict_resolution_adjust",
                "Successfully adjusted fragment to resolve conflicts",
                {
                    "original_title": fragment.title,
                    "adjusted_title": adjusted_title,
                    "adjustment_reasoning": result.get("adjustment_reasoning", "")
                }
            )
            
            return ConflictResolution(
                original_fragment=fragment,
                adjusted_fragment=adjusted_fragment,
                resolution_strategy="adjust",
                conflicts_resolved=[c.description for c in conflicts],
                conflicts_unresolved=[],
                reasoning=result.get("adjustment_reasoning", "Fragment adjusted to resolve conflicts"),
                decided_at=datetime.now()
            )
            
        except Exception as e:
            log_event(
                "conflict_resolution_adjust_error",
                f"Error during adjustment: {e}",
                {"fragment_title": fragment.title, "error": str(e)}
            )
            return None
    
    def _read_worldview(self) -> str:
        """
        Read existing worldview fragments for context.
        
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
    
    def _parse_adjustment_response(self, response: str) -> dict:
        """
        Parse LLM adjustment response into components.
        
        Args:
            response: LLM response text
            
        Returns:
            dict: Parsed result with adjusted_title, adjusted_content, etc.
        """
        try:
            # Try to find JSON in the response
            json_match = re.search(
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
                response,
                re.DOTALL
            )
            
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, ValueError):
            pass
        
        # If JSON parsing fails, return cannot_adjust
        return {
            "cannot_adjust": True,
            "reason": "LLM response could not be parsed"
        }


__all__ = ["ConflictResolver", "ConflictResolution"]
