"""
Trace System

Injects Agent traces (annotations) into user files as Obsidian callouts.
Respects user preferences via file frontmatter (trace: false).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

CALLOUT_TYPES = ("note", "question", "tip", "warning", "danger")


@dataclass
class Trace:
    """
    An annotation left by the Agent in a user file.
    
    Attributes:
        content: The trace message content
        callout_type: Type of callout - "note" | "question" | "tip" | "warning" | "danger"
        created_at: When the trace was created
        agent_reflection: Optional Agent's internal reflection/thought
    """
    content: str
    callout_type: str
    created_at: datetime = field(default_factory=datetime.now)
    agent_reflection: str = ""
    
    def __post_init__(self) -> None:
        """Validate callout_type."""
        if self.callout_type not in CALLOUT_TYPES:
            self.callout_type = "note"


class TraceInjector:
    """
    Injects Agent traces into user files as Obsidian callouts.
    
    The injected callouts appear in blockquote format:
    > [!note] Agent 的痕迹
    > *2026-05-31 14:00*
    > 
    > Trace content...
    
    Respects user preferences:
    - Files with `trace: false` in frontmatter are protected
    - agent/ and .obsidian/ directories are always protected
    """
    
    def __init__(self, vault_path: Path):
        """
        Initialize the trace injector.
        
        Args:
            vault_path: Path to the Obsidian vault root
        """
        self.vault_path = vault_path
    
    def can_inject(self, file_path: str) -> bool:
        """
        Check if Agent is allowed to inject into this file.
        
        Returns False (blocks injection) for:
        - agent/ directory files
        - .obsidian/ directory files
        - Files with `trace: false` in frontmatter
        
        Args:
            file_path: Path to check (relative or absolute)
            
        Returns:
            bool: True if injection is allowed
        """
        path = Path(file_path)
        
        # Protect agent/ directory
        if "agent/" in str(path) or str(path).endswith("agent"):
            return False
        
        # Protect .obsidian/ directory
        if ".obsidian/" in str(path) or str(path).endswith(".obsidian"):
            return False
        
        # Check absolute path
        try:
            abs_path = path if path.is_absolute() else self.vault_path / path
            rel_parts = str(abs_path.relative_to(self.vault_path)).split("/")
            
            if "agent" in rel_parts or ".obsidian" in rel_parts:
                return False
        except (ValueError, OSError):
            pass
        
        # Check frontmatter for trace: false
        if path.exists():
            if not self._has_trace_permission(path):
                return False
        
        return True
    
    def _has_trace_permission(self, file_path: Path) -> bool:
        """
        Check if file has explicit trace permission in frontmatter.
        
        Args:
            file_path: Path to the file
            
        Returns:
            bool: True if trace is allowed (no frontmatter or trace: true)
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Check for frontmatter
            if not content.startswith("---"):
                return True  # No frontmatter, allow
            
            # Find end of frontmatter
            parts = content.split("---", 2)
            if len(parts) < 3:
                return True  # Malformed frontmatter, allow
            
            frontmatter = parts[1]
            
            # Look for trace: false
            if re.search(r'^trace:\s*false', frontmatter, re.MULTILINE):
                return False
            
            # Look for trace: true
            if re.search(r'^trace:\s*true', frontmatter, re.MULTILINE):
                return True
            
            return True  # No trace setting, allow by default
            
        except (OSError, UnicodeDecodeError):
            return True  # Can't read file, allow by default
    
    def format_callout(self, trace: Trace) -> str:
        """
        Format a trace as an Obsidian callout block.
        
        Format:
        > [!note] Agent 的痕迹
        > *2026-05-31 14:00*
        > 
        > Trace content...
        > 
        > *反思内容*
        
        Args:
            trace: The Trace to format
            
        Returns:
            str: Formatted callout as markdown blockquote
        """
        callout_type = trace.callout_type.lower()
        if callout_type not in CALLOUT_TYPES:
            callout_type = "note"
        
        timestamp = trace.created_at.strftime("%Y-%m-%d %H:%M")
        
        lines = [
            f"> [!{callout_type}] Agent 的痕迹",
            f"> *{timestamp}*",
            f"> ",
            f"> {trace.content}",
        ]
        
        if trace.agent_reflection:
            lines.extend([
                f"> ",
                f"> *{trace.agent_reflection}*",
            ])
        
        return "\n".join(lines)
    
    def inject_trace(
        self,
        file_path: str,
        trace: Trace,
        position: str = "end"
    ) -> bool:
        """
        Inject a callout into a file.
        
        Args:
            file_path: Path to the target file
            trace: The Trace to inject
            position: Where to inject - "start" | "end" | "after_heading"
            
        Returns:
            bool: True if injection was successful
        """
        if not self.can_inject(file_path):
            return False
        
        path = Path(file_path)
        if not path.exists():
            return False
        
        try:
            content = path.read_text(encoding="utf-8")
            callout = self.format_callout(trace)
            
            if position == "start":
                new_content = callout + "\n\n" + content
            elif position == "after_heading":
                new_content = self._insert_after_first_heading(content, callout)
            else:  # "end"
                new_content = content + "\n\n" + callout
            
            path.write_text(new_content, encoding="utf-8")
            return True
            
        except (OSError, UnicodeDecodeError):
            return False
    
    def _insert_after_first_heading(self, content: str, callout: str) -> str:
        """
        Insert callout after the first markdown heading.
        
        Args:
            content: Original file content
            callout: Callout text to insert
            
        Returns:
            str: Content with callout inserted
        """
        # Find first heading
        match = re.search(r'^#+\s+.+$', content, re.MULTILINE)
        
        if not match:
            # No heading found, prepend at start
            return callout + "\n\n" + content
        
        # Find end of heading line
        pos = match.end()
        
        # Skip any blank lines after heading
        while pos < len(content) and content[pos] in " \t":
            pos += 1
        
        # Find the next newline (end of heading line)
        newline_pos = content.find("\n", pos)
        if newline_pos == -1:
            newline_pos = len(content)
        
        # Skip blank lines
        while newline_pos < len(content) and content[newline_pos] == "\n":
            newline_pos += 1
        
        return content[:newline_pos] + "\n\n" + callout + "\n\n" + content[newline_pos:]
    
    def remove_trace(self, file_path: str, trace_content: str) -> bool:
        """
        Remove a trace from a file.
        
        This removes the entire callout block that contains the given content.
        
        Args:
            file_path: Path to the file
            trace_content: Content string to search for in the callout
            
        Returns:
            bool: True if removal was successful
        """
        path = Path(file_path)
        if not path.exists():
            return False
        
        try:
            content = path.read_text(encoding="utf-8")
            
            # Pattern to match callout blocks
            # Matches from "> [!type] Agent 的痕迹" to the end of that paragraph
            pattern = r'\n\n> \[![^\]]+\] Agent 的痕迹\n> \*[\d\-: ]+\*\n(?:> \n)?(?:> .+\n)*(?:> \n)?(?:> \*.*\*\n)?'
            
            # Find callouts containing the trace content
            new_content = re.sub(pattern, '\n\n', content)
            
            # Clean up multiple blank lines
            new_content = re.sub(r'\n{4,}', '\n\n\n', new_content)
            
            if new_content != content:
                path.write_text(new_content.strip() + "\n", encoding="utf-8")
                return True
            
            return False
            
        except (OSError, UnicodeDecodeError):
            return False
    
    def generate_trace(self, fragment, callout_type: str = "note") -> Trace:
        """
        Generate a trace from a WorldFragment.
        
        Args:
            fragment: WorldFragment to create trace from
            callout_type: Type of callout
            
        Returns:
            Trace: Generated trace
        """
        content = f"已将「{fragment.title}」纳入图书馆收藏"
        
        reflection = ""
        if fragment.fit_path == "collision":
            reflection = f"这次碰撞产生了新的视角——{fragment.title}"
        elif fragment.content:
            # Use first 100 chars of content as reflection hint
            preview = fragment.content[:100].replace("\n", " ").strip()
            reflection = f"这让我想起了阅读时的那种感觉：{preview}..."
        
        return Trace(
            content=content,
            callout_type=callout_type,
            agent_reflection=reflection
        )


__all__ = ["Trace", "TraceInjector", "CALLout_TYPES"]
