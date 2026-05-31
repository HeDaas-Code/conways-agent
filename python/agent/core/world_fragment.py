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
    
    def to_markdown(self) -> str:
        """
        Convert fragment to markdown format.
        
        Returns:
            str: Markdown representation of the fragment
        """
        links_section = ""
        if self.links:
            links_section = "\n\n**Related:** " + " | ".join(f"[[{link}]]" for link in self.links)
        
        collision_section = ""
        if self.fit_path == "collision" and self.collision_elements:
            elements_str = " × ".join(f"[[{elem}]]" for elem in self.collision_elements)
            collision_section = f"\n\n**碰撞元素:** {elements_str}"
        
        return f"""# {self.title}

{self.content}

---
*Source: {self.source_trigger} | Path: {self.fit_path} | Created: {self.created_at.isoformat()}*{links_section}{collision_section}
"""
    
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
