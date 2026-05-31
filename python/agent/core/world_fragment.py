"""
World Fragment

Represents a piece of worldview content created by the Agent through
the processing pipeline (either translation or collision path).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class WorldFragment:
    """
    A piece of 世界观 (worldview) content created by the Agent.
    
    This is the primary output of the processing pipeline, representing
    how the Agent has incorporated or clashed with new information.
    
    Attributes:
        title: Brief title for this fragment
        content: The prose narrative in Agent's voice
        links: [[wikilinks]] to related concepts
        source_trigger: What caused this fragment to be created
        fit_path: Which processing path was taken ("translation" or "collision")
        created_at: Timestamp when fragment was created
        source_file: Optional path to the source file that triggered this fragment
        collision_elements: Elements that were collided (only for collision path)
    """
    
    title: str
    content: str
    links: list[str] = field(default_factory=list)
    source_trigger: str = "unknown"
    fit_path: str = "translation"
    created_at: datetime = field(default_factory=datetime.now)
    source_file: Optional[str] = None
    collision_elements: list[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Validate fragment fields after initialization."""
        if self.fit_path not in ("translation", "collision"):
            self.fit_path = "translation"
    
    def to_markdown(self, backlinks: list[str] | None = None) -> str:
        """
        Convert fragment to Obsidian markdown format with YAML frontmatter.

        Args:
            backlinks: Optional list of fragment titles that link to this fragment.

        Returns:
            str: Obsidian markdown representation of the fragment
        """
        created_str = self.created_at.isoformat()

        source_line = ""
        if self.source_file:
            source_line = f"\nsource: {self.source_file}"

        collision_line = ""
        if self.collision_elements:
            collision_line = f"\ncollision-elements: {', '.join(self.collision_elements)}"

        frontmatter = f"""---
created: {created_str}
type: world-fragment
fit-path: {self.fit_path}{source_line}{collision_line}
---"""

        links_section = ""
        if self.links:
            links_list = ", ".join(f"[[{link}]]" for link in self.links)
            links_section = f"\n\n相关链接: {links_list}"

        collision_section = ""
        if self.fit_path == "collision" and self.collision_elements:
            elements_str = " × ".join(f"[[{elem}]]" for elem in self.collision_elements)
            collision_section = f"\n\n**碰撞元素:** {elements_str}"

        content_lines = self.content.strip().split("\n")
        quoted_content = "\n".join(f"> {line}" if line.strip() else ">" for line in content_lines)

        tag_line = f"\n\n标签: #{self.fit_path}"

        backlinks_section = ""
        if backlinks:
            bl_items = []
            for bl in backlinks:
                bl_items.append(f"- [[{bl}]]")
            backlink_list = "\n".join(bl_items)
            backlinks_section = f"\n\n---\n\n*被以下内容引用：*\n{backlink_list}"

        return f"""{frontmatter}

# {self.title}

{quoted_content}{links_section}{tag_line}{collision_section}{backlinks_section}"""
    
    def to_dict(self) -> dict:
        """
        Convert fragment to dictionary for serialization.
        
        Returns:
            dict: Fragment as dictionary
        """
        return {
            "title": self.title,
            "content": self.content,
            "links": self.links,
            "source_trigger": self.source_trigger,
            "fit_path": self.fit_path,
            "created_at": self.created_at.isoformat(),
            "source_file": self.source_file,
            "collision_elements": self.collision_elements,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> WorldFragment:
        """
        Create a WorldFragment from a dictionary.
        
        Args:
            data: Dictionary with fragment data
            
        Returns:
            WorldFragment: New fragment instance
        """
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "collision_elements" not in data:
            data["collision_elements"] = []
        if "source_file" not in data:
            data["source_file"] = None
        return cls(**data)


__all__ = ["WorldFragment"]
