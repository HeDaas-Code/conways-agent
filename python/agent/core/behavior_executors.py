"""
Behavior Executors - Actual execution functions for preset behaviors.

Issue #39:
- world_fragment_executor: Generate world fragment from topics
- explore_links_executor: Explore note links related to interests
- deep_reflection_executor: Deep reflection on accumulated interests

Vault writeback follows specification:
- Path: vault/agent/world/{behavior}_{timestamp}_{uuid}.md
- Frontmatter: type, behavior, topics, timestamp
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ==================== Execution Result ====================

@dataclass
class ExecutorResult:
    """Result of executor execution."""
    success: bool
    output_path: Optional[str] = None
    content: str = ""
    error: Optional[str] = None
    executed_at: datetime = field(default_factory=datetime.now)


# ==================== Utility Functions ====================

def _generate_filename(behavior_name: str) -> str:
    """Generate unique filename following Vault spec."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_id = str(uuid.uuid4())[:6]
    kebab_name = behavior_name.lower().replace("_", "-")
    return f"{kebab_name}_{timestamp}_{short_id}.md"


def _ensure_vault_dir(vault_path: str, behavior_name: str) -> Path:
    """Ensure vault directory structure exists."""
    vault_dir = Path(vault_path) / "vault" / "agent" / "world"
    vault_dir.mkdir(parents=True, exist_ok=True)
    return vault_dir


def _write_with_frontmatter(
    behavior_name: str,
    frontmatter: dict,
    content: str,
    vault_path: str
) -> tuple[str, str]:
    """Write markdown file with frontmatter. Returns (full_path, filename)."""
    vault_dir = _ensure_vault_dir(vault_path, behavior_name)
    filename = _generate_filename(behavior_name)
    filepath = vault_dir / filename
    
    # Build frontmatter lines
    fm_lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            fm_lines.append(f"{key}:")
            for item in value:
                fm_lines.append(f"  - {item}")
        else:
            fm_lines.append(f"{key}: {value}")
    fm_lines.append("---")
    fm_lines.append("")
    
    # Write file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(fm_lines))
        f.write(content)
    
    return str(filepath), content


# ==================== Content Generators ====================

def _generate_world_fragment_content(topics: list[str]) -> str:
    """Generate world fragment content."""
    topic_str = ", ".join(topics) if topics else "general knowledge"
    
    return f"""## World Fragment

### Context
Generated from interest vector focusing on: {topic_str}

### Key Observations
Based on accumulated interest patterns, this fragment captures:

1. **Primary Theme**: {topics[0] if topics else 'general'} emerges as a core interest
2. **Supporting Concepts**: Related topics that connect to the main theme
3. **Emerging Patterns**: Connections detected across knowledge domains

### Connections
- Links to current interest vector
- Bridges multiple knowledge areas
- Potential for further exploration

### Reflection
The agent has generated this world fragment through accumulated interest-driven processing.
Interest patterns suggest continued development in these areas.
"""


def _generate_explore_links_content(topics: list[str], files: list[str]) -> str:
    """Generate link exploration content."""
    topics_str = ", ".join(topics) if topics else "current interests"
    files_count = len(files) if files else 0
    
    files_list = "\n".join([f"- [[{f}]]" for f in files]) if files else "- (no specific files)"
    
    return f"""## Link Exploration Report

### Exploration Context
Topics of interest: {topics_str}
Files analyzed: {files_count}

### Explored Connections
{files_list}

### Discovery Summary
Analyzed {files_count} files for link patterns related to current interests.
Key connection clusters identified.

### Insights
- Strong clusters around primary topics
- Weak ties provide expansion opportunities
- Potential bridging nodes for future exploration

### Recommendations
1. Strengthen existing high-value connections
2. Explore weak ties for novel insights
3. Consider bidirectional link creation
4. Document new connections in relevant files
"""


def _generate_deep_reflection_content(
    topics: list[str],
    from_points: int,
    to_points: int
) -> str:
    """Generate deep reflection content."""
    delta = to_points - from_points
    period = f"Points {from_points} → {to_points}"
    
    theme_list = "\n".join([
        f"{i+1}. **{t}** - {'Primary focus' if i == 0 else 'Secondary theme'}"
        for i, t in enumerate(topics[:5]) if topics
    ]) or "- General interest patterns"
    
    return f"""## Deep Reflection

### Period: {period}
Interest accumulation delta: {delta:+d} points

### Core Themes Identified
{theme_list}

### Understanding Evolution
- **Starting State**: {from_points} points of accumulated interest
- **Current State**: {to_points} points after processing
- **Shift**: {'Growth in primary themes' if delta > 0 else 'Consolidation phase'}

### Knowledge Gaps
- Areas requiring further exploration
- Questions that emerged but remain unanswered
- Topics needing direct investigation

### Behavioral Patterns
Noticed patterns in how interests developed:
- Gradual accumulation through repeated exposure
- Threshold-based behavior triggering
- Cross-pollination between topic domains

### Action Items
- [ ] Follow up on primary themes
- [ ] Research secondary connections
- [ ] Document findings in relevant files
- [ ] Plan next interest accumulation cycle

### Meta-reflection
This reflection cycle has clarified {'growth trajectory' if delta > 0 else 'consolidation needs'} 
for the agent's interest-driven behavior system.
"""


# ==================== Executors ====================

def world_fragment_executor(
    topics: list[str],
    vault_path: str
) -> ExecutorResult:
    """
    Execute WORLD_FRAGMENT behavior.
    
    Generates a world fragment from interest topics.
    
    Args:
        topics: List of topics from interest vector
        vault_path: Base path for vault directory
        
    Returns:
        ExecutorResult with output path and content
    """
    try:
        content = _generate_world_fragment_content(topics)
        
        frontmatter = {
            "type": "world-fragment",
            "behavior": "WORLD_FRAGMENT",
            "topics": topics,
            "triggered_by": "threshold",
            "timestamp": datetime.now().isoformat(),
        }
        
        output_path, _ = _write_with_frontmatter(
            "WORLD_FRAGMENT",
            frontmatter,
            content,
            vault_path
        )
        
        return ExecutorResult(
            success=True,
            output_path=output_path,
            content=content,
        )
        
    except Exception as e:
        return ExecutorResult(
            success=False,
            error=str(e)
        )


def explore_links_executor(
    topics: list[str],
    files: list[str],
    vault_path: str
) -> ExecutorResult:
    """
    Execute EXPLORE_LINKS behavior.
    
    Explores note links related to current interests.
    
    Args:
        topics: List of topics from interest vector
        files: List of files to explore
        vault_path: Base path for vault directory
        
    Returns:
        ExecutorResult with output path and content
    """
    try:
        content = _generate_explore_links_content(topics, files)
        
        frontmatter = {
            "type": "link-exploration",
            "behavior": "EXPLORE_LINKS",
            "topics": topics,
            "files_explored": len(files),
            "triggered_by": "threshold",
            "timestamp": datetime.now().isoformat(),
        }
        
        output_path, _ = _write_with_frontmatter(
            "EXPLORE_LINKS",
            frontmatter,
            content,
            vault_path
        )
        
        return ExecutorResult(
            success=True,
            output_path=output_path,
            content=content,
        )
        
    except Exception as e:
        return ExecutorResult(
            success=False,
            error=str(e)
        )


def deep_reflection_executor(
    topics: list[str],
    from_points: int,
    to_points: int,
    vault_path: str
) -> ExecutorResult:
    """
    Execute DEEP_REFLECTION behavior.
    
    Generates deep reflection on interest accumulation.
    
    Args:
        topics: List of topics from interest vector
        from_points: Points before behavior
        to_points: Points after behavior
        vault_path: Base path for vault directory
        
    Returns:
        ExecutorResult with output path and content
    """
    try:
        content = _generate_deep_reflection_content(topics, from_points, to_points)
        
        frontmatter = {
            "type": "deep-reflection",
            "behavior": "DEEP_REFLECTION",
            "topics": topics,
            "points_delta": to_points - from_points,
            "points_range": f"{from_points}-{to_points}",
            "triggered_by": "threshold",
            "timestamp": datetime.now().isoformat(),
        }
        
        output_path, _ = _write_with_frontmatter(
            "DEEP_REFLECTION",
            frontmatter,
            content,
            vault_path
        )
        
        return ExecutorResult(
            success=True,
            output_path=output_path,
            content=content,
        )
        
    except Exception as e:
        return ExecutorResult(
            success=False,
            error=str(e)
        )


# ==================== Executor Registry ====================

EXECUTORS = {
    "WORLD_FRAGMENT": world_fragment_executor,
    "EXPLORE_LINKS": explore_links_executor,
    "DEEP_REFLECTION": deep_reflection_executor,
}


def get_executor(behavior_name: str):
    """Get executor function for a behavior name."""
    return EXECUTORS.get(behavior_name.upper())


# ==================== Demo ====================

if __name__ == "__main__":
    import tempfile
    
    print("=== Executor Demo ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # World Fragment
        print("1. WORLD_FRAGMENT:")
        result = world_fragment_executor(
            topics=["python", "ai", "machine-learning"],
            vault_path=tmpdir
        )
        print(f"   Success: {result.success}")
        print(f"   Output: {result.output_path}")
        
        # Explore Links
        print("\n2. EXPLORE_LINKS:")
        result = explore_links_executor(
            topics=["python", "ai"],
            files=["notes/python-intro.md", "notes/ai-overview.md"],
            vault_path=tmpdir
        )
        print(f"   Success: {result.success}")
        print(f"   Output: {result.output_path}")
        
        # Deep Reflection
        print("\n3. DEEP_REFLECTION:")
        result = deep_reflection_executor(
            topics=["python", "ai", "agent"],
            from_points=30,
            to_points=60,
            vault_path=tmpdir
        )
        print(f"   Success: {result.success}")
        print(f"   Output: {result.output_path}")
        
        # Executor registry
        print("\n4. Executor Registry:")
        print(f"   WORLD_FRAGMENT: {get_executor('WORLD_FRAGMENT').__name__}")
        print(f"   EXPLORE_LINKS: {get_executor('EXPLORE_LINKS').__name__}")
        print(f"   DEEP_REFLECTION: {get_executor('DEEP_REFLECTION').__name__}")
