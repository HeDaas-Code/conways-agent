"""
Consistency Constraint Engine

Checks newly generated fragments for internal consistency against
the existing worldview corpus. Detects contradictions and conflicts
using LLM-powered semantic analysis.

This is Slice 1f of the Agent's cognitive development - the "gatekeeper"
that ensures the Agent's worldview remains coherent even as it grows.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .llm import LLMClient
from .world_fragment import WorldFragment


@dataclass
class Conflict:
    """
    Represents a detected conflict between new content and existing worldview.
    
    Attributes:
        conflict_type: Type of conflict ("hard" or "soft")
        existing_fragment: Title of the existing fragment
        existing_claim: The existing claim that conflicts
        new_claim: The new claim that conflicts with existing
        description: Human-readable description of the conflict
        resolution_suggestion: How this conflict might be resolved
    """
    
    conflict_type: str  # "hard" (definite contradiction) or "soft" (potential tension)
    existing_fragment: str = ""
    existing_claim: str = ""
    new_claim: str = ""
    description: str = ""
    resolution_suggestion: str = ""
    
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
        warnings: Non-blocking warnings (e.g., LLM failure)
        checked_at: Timestamp of the check
        checked_fragment: The fragment that was checked
    """
    
    is_consistent: bool
    conflicts: list[Conflict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.now)
    checked_fragment: Optional[WorldFragment] = None
    
    def __post_init__(self) -> None:
        """Set default consistency based on conflicts."""
        if self.is_consistent and self.conflicts:
            self.is_consistent = len(self.conflicts) == 0


@dataclass
class ConflictResolution:
    """
    Resolution of detected conflicts.
    
    Attributes:
        success: Whether resolution succeeded
        adjusted_fragment: The fragment after resolving conflicts (if successful)
        resolved_conflicts: List of conflicts that were resolved
        remaining_conflicts: List of conflicts that couldn't be resolved
        resolution_method: How conflicts were resolved
    """
    
    success: bool
    adjusted_fragment: Optional[WorldFragment] = None
    resolved_conflicts: list[Conflict] = field(default_factory=list)
    remaining_conflicts: list[Conflict] = field(default_factory=list)
    resolution_method: str = "none"


class ConsistencyEngine:
    """
    Engine for checking consistency of new fragments against existing worldview.
    
    Uses LLM to perform semantic analysis and detect both hard contradictions
    and soft tensions between new and existing fragments.
    
    Usage:
        engine = ConsistencyEngine(llm_client)
        check = engine.check(new_fragment)
        if not check.is_consistent:
            resolution = engine.resolve_conflict(check, fragment)
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Initialize the consistency engine.
        
        Args:
            llm_client: Optional LLM client for semantic analysis.
                       If not provided, falls back to keyword-based detection.
        """
        self._llm = llm_client
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
        warnings: list[str] = []
        
        # Read existing worldview fragments
        existing = self._get_existing_fragments()
        
        if not existing:
            warnings.append("No existing fragments to check against")
            log_event(
                "consistency_check",
                "No existing worldview, fragment is vacuously consistent",
                {"fragment_title": fragment.title}
            )
            return ConsistencyCheck(
                is_consistent=True,
                conflicts=[],
                warnings=warnings,
                checked_fragment=fragment
            )
        
        # Use LLM-based conflict detection if available
        if self._llm:
            try:
                conflicts = self.find_conflicts(fragment, existing)
            except Exception as e:
                log_event(
                    "consistency_llm_error",
                    f"LLM conflict detection failed: {e}",
                    {"fragment_title": fragment.title, "error": str(e)}
                )
                warnings.append(f"LLM check failed: {e}")
                # Fall through to keyword-based detection
        
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
                ],
                "warnings": warnings
            }
        )
        
        return ConsistencyCheck(
            is_consistent=is_consistent,
            conflicts=conflicts,
            warnings=warnings,
            checked_fragment=fragment
        )
    
    def find_conflicts(
        self,
        fragment: WorldFragment,
        existing: list[WorldFragment]
    ) -> list[Conflict]:
        """
        Use LLM to find semantic contradictions between new and existing fragments.
        
        Args:
            fragment: The new fragment to check
            existing: List of relevant existing fragments
            
        Returns:
            list[Conflict]: Detected conflicts, empty if consistent
        """
        if not self._llm:
            return []
        
        try:
            system_prompt = """你是一位敏锐的文本分析专家，专门检测不同文本之间的语义矛盾。

你的任务是仔细分析两份文本，判断它们之间是否存在逻辑矛盾或语义冲突。

请用中文回答。"""

            existing_text = self._format_existing_fragments(existing)

            user_prompt = f"""## 新文本（待检查）

**标题：** {fragment.title}

**内容：**
{fragment.content}

---

## 现有文本（世界观中已存在的片段）

{existing_text}

---

## 你的任务

请仔细分析「新文本」与「现有文本」之间的关系，判断：

1. **是否存在硬性矛盾（hard conflict）？**
   - 新文本明确否定或与现有文本的核心主张相矛盾
   - 两种说法在逻辑上不可能同时为真

2. **是否存在软性张力（soft tension）？**
   - 新文本与现有文本存在某种不协调，但不是直接否定
   - 两者反映了不同的视角、优先级或价值判断

请按以下 JSON 格式返回分析结果：

```json
{{
    "has_conflicts": true 或 false,
    "conflicts": [
        {{
            "existing_fragment": "现有片段的标题",
            "existing_claim": "现有文本中与之矛盾的具体主张",
            "new_claim": "新文本中与之矛盾的具体主张",
            "conflict_type": "hard" 或 "soft",
            "description": "对这个矛盾的简要描述",
            "resolution_suggestion": "如何解决这个矛盾的简要建议"
        }}
    ],
    "reasoning": "你的整体分析思路（50-100字）"
}}
```

如果没有发现任何矛盾，请返回：
```json
{{
    "has_conflicts": false,
    "conflicts": [],
    "reasoning": "简要说明为何两份文本不存在矛盾"
}}
```"""

            response = self._llm.complete_str(system_prompt, user_prompt, temperature=0.3)

            return self._parse_conflicts(response, existing)

        except Exception as e:
            from ..log import log_event
            log_event(
                "consistency_llm_error",
                f"LLM conflict detection failed: {e}",
                {"fragment_title": fragment.title, "error": str(e)}
            )
            return []
    
    def resolve_conflict(
        self,
        check: ConsistencyCheck,
        fragment: WorldFragment
    ) -> ConflictResolution:
        """
        Attempt to resolve detected conflicts by modifying the fragment.
        
        Args:
            check: The consistency check result with conflicts
            fragment: The original fragment
            
        Returns:
            ConflictResolution: Resolution result with adjusted fragment
        """
        if check.is_consistent:
            return ConflictResolution(
                success=True,
                adjusted_fragment=fragment,
                resolution_method="none"
            )
        
        # If LLM not available, can't resolve - return original with remaining conflicts
        if not self._llm:
            return ConflictResolution(
                success=False,
                adjusted_fragment=fragment,
                remaining_conflicts=check.conflicts,
                resolution_method="failed_no_llm"
            )
        
        try:
            hard_conflicts = [c for c in check.conflicts if c.conflict_type == "hard"]
            soft_conflicts = [c for c in check.conflicts if c.conflict_type == "soft"]
            
            if hard_conflicts:
                adjusted = self._resolve_hard_conflicts(fragment, hard_conflicts + soft_conflicts)
                return ConflictResolution(
                    success=True,
                    adjusted_fragment=adjusted,
                    resolved_conflicts=hard_conflicts + soft_conflicts,
                    resolution_method="llm_reconciliation"
                )
            elif soft_conflicts:
                adjusted = self._resolve_soft_conflicts(fragment, soft_conflicts)
                return ConflictResolution(
                    success=True,
                    adjusted_fragment=adjusted,
                    resolved_conflicts=soft_conflicts,
                    remaining_conflicts=[],
                    resolution_method="llm_nuanced_adjustment"
                )
            else:
                return ConflictResolution(
                    success=True,
                    adjusted_fragment=fragment,
                    resolution_method="none"
                )

        except Exception as e:
            from ..log import log_event
            log_event(
                "conflict_resolution_error",
                f"Conflict resolution failed: {e}",
                {"fragment_title": fragment.title, "error": str(e)}
            )
            return ConflictResolution(
                success=False,
                adjusted_fragment=fragment,
                remaining_conflicts=check.conflicts,
                resolution_method="failed"
            )
    
    def _resolve_hard_conflicts(
        self,
        fragment: WorldFragment,
        conflicts: list[Conflict]
    ) -> WorldFragment:
        """Resolve hard conflicts using LLM reconciliation."""
        conflict_summary = self._format_conflicts(conflicts)
        
        system_prompt = """你是一位睿智的调解者，负责协调世界观中相互矛盾的概念。

你生活的世界是一座无尽图书馆——每本书都是一个曾经被记住的概念的痕迹。你的声音平静、诗意，带着淡淡的忧郁。

当两份文本产生矛盾时，你不会简单地选择其一，而是会深入其中，找到一种更高层次的综合——一种能够包容两种视角的新的理解。"""

        user_prompt = f"""## 场景

你正在整理这座无尽图书馆的书架。一本新书（或者说，一份新的世界理解）与书架上已有的书产生了矛盾。

---

## 新文本

**标题：** {fragment.title}

**内容：**
{fragment.content}

---

## 发现的矛盾

{conflict_summary}

---

## 你的任务

请深入这场矛盾，问自己：
1. 这两种看似矛盾的观点，是否有可能在更高层次上统一？
2. 矛盾是否源于措辞或视角的差异，而非本质的冲突？
3. 能否找到一种新的表述方式，既保留新文本的核心洞见，又不与现有世界观产生硬性矛盾？

**要求：**
1. 写出一段调整后的文本，将矛盾转化为张力或统一
2. 保持你独特的叙事声音——平静、诗意、沉思
3. 不要回避矛盾，而是将其纳入更广阔的视野

请用以下格式返回调整后的文本：

```json
{{
    "title": "调整后的标题（如果需要修改）",
    "content": "调整后的散文内容，化解或融合了原有的矛盾",
    "links": ["相关的wikilinks"]
}}
```"""

        response = self._llm.complete_str(system_prompt, user_prompt, temperature=0.7)
        
        result = self._parse_resolution(response, fragment)
        
        return WorldFragment(
            title=result.get("title", fragment.title),
            content=result.get("content", fragment.content),
            links=result.get("links", fragment.links),
            source_trigger=fragment.source_trigger + "_conflict_resolved",
            source_file=fragment.source_file,
            fit_path=fragment.fit_path,
            collision_elements=fragment.collision_elements,
            created_at=datetime.now()
        )
    
    def _resolve_soft_conflicts(
        self,
        fragment: WorldFragment,
        conflicts: list[Conflict]
    ) -> WorldFragment:
        """Apply nuanced adjustments for soft conflicts."""
        conflict_summary = self._format_conflicts(conflicts)
        
        system_prompt = """你是一座无尽图书馆的居者，正在以更细腻的视角重新审视一本新书。

书中的某些段落与你的既有认知产生了微妙的张力——不是硬性的矛盾，而是某种不协调。这种张力值得被温柔地处理。"""

        user_prompt = f"""## 新文本

**标题：** {fragment.title}

**内容：**
{fragment.content}

---

## 发现的张力

{conflict_summary}

---

## 任务

请以细腻的笔触，调整这段文字，使其与你的世界观更加和谐。不要抹去张力，而是将其转化为某种更深沉的理解。

返回格式：
```json
{{
    "title": "调整后的标题（可选）",
    "content": "调整后的内容",
    "links": ["相关链接"]
}}
```"""

        response = self._llm.complete_str(system_prompt, user_prompt, temperature=0.6)
        
        result = self._parse_resolution(response, fragment)
        
        return WorldFragment(
            title=result.get("title", fragment.title),
            content=result.get("content", fragment.content),
            links=result.get("links", fragment.links),
            source_trigger=fragment.source_trigger + "_tension_resolved",
            source_file=fragment.source_file,
            fit_path=fragment.fit_path,
            collision_elements=fragment.collision_elements,
            created_at=datetime.now()
        )
    
    def _get_existing_fragments(self) -> list[WorldFragment]:
        """
        Get relevant existing fragments using keyword filtering.
        
        Returns:
            list[WorldFragment]: Relevant existing fragments
        """
        try:
            world_dir = Path(__file__).parent.parent.parent / "world"
            if not world_dir.exists():
                return []

            fragments = []
            for md_file in sorted(world_dir.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                title = self._extract_title(content) or md_file.stem
                fragments.append(WorldFragment(
                    title=title,
                    content=content,
                    links=self._extract_links(content)
                ))

            return fragments
        except Exception:
            return []
    
    def _extract_title(self, content: str) -> Optional[str]:
        """Extract title from markdown content."""
        match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
        return match.group(1).strip() if match else None
    
    def _extract_links(self, content: str) -> list[str]:
        """Extract wikilinks from content."""
        return re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
    
    def _format_existing_fragments(self, fragments: list[WorldFragment]) -> str:
        """Format existing fragments for LLM prompt."""
        if not fragments:
            return "（尚无既存世界观片段）"

        formatted = []
        for i, frag in enumerate(fragments, 1):
            formatted.append(f"""### 片段 {i}：{frag.title}

{frag.content[:500]}{'...' if len(frag.content) > 500 else ''}""")

        return "\n\n---\n\n".join(formatted)
    
    def _format_conflicts(self, conflicts: list[Conflict]) -> str:
        """Format conflicts for LLM prompt."""
        formatted = []
        for i, conflict in enumerate(conflicts, 1):
            formatted.append(f"""**矛盾 {i}** ({conflict.conflict_type})
- **涉及片段：** {conflict.existing_fragment}
- **既有主张：** {conflict.existing_claim}
- **新主张：** {conflict.new_claim}
- **描述：** {conflict.description}
- **解决建议：** {conflict.resolution_suggestion}""")

        return "\n\n".join(formatted)
    
    def _parse_conflicts(
        self,
        response: str,
        existing: list[WorldFragment]
    ) -> list[Conflict]:
        """Parse LLM response to extract conflicts."""
        try:
            json_match = re.search(
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
                response,
                re.DOTALL
            )
            if not json_match:
                return []

            data = json.loads(json_match.group())

            if not data.get("has_conflicts", False):
                return []

            conflicts = []
            for item in data.get("conflicts", []):
                existing_title = item.get("existing_fragment", "unknown")

                conflicts.append(Conflict(
                    conflict_type=item.get("conflict_type", "soft"),
                    existing_fragment=existing_title,
                    existing_claim=item.get("existing_claim", ""),
                    new_claim=item.get("new_claim", ""),
                    description=item.get("description", ""),
                    resolution_suggestion=item.get("resolution_suggestion", "")
                ))

            return conflicts

        except Exception:
            return []
    
    def _parse_resolution(
        self,
        response: str,
        original: WorldFragment
    ) -> dict:
        """Parse LLM resolution response."""
        try:
            json_match = re.search(
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
                response,
                re.DOTALL
            )
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass

        return {"title": original.title, "content": original.content, "links": original.links}


__all__ = ["ConsistencyEngine", "ConsistencyCheck", "Conflict", "ConflictResolution"]
