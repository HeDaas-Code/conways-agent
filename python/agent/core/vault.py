"""
Vault Access Utilities

Provides utilities for accessing the Obsidian vault directory structure.
All paths are relative to OBSIDIAN_VAULT_PATH environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def get_vault_path() -> Path:
    """
    Get the Obsidian vault path from environment variable.
    
    Returns:
        Path: The absolute path to the Obsidian vault
        
    Raises:
        ValueError: If OBSIDIAN_VAULT_PATH is not set
    """
    vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        raise ValueError(
            "OBSIDIAN_VAULT_PATH environment variable is not set. "
            "Please set it in your .env file or environment."
        )
    return Path(vault_path)


def read_seed() -> str:
    """
    Read the agent seed file.
    
    Returns:
        str: The content of agent/seed.md
        
    Raises:
        FileNotFoundError: If seed.md does not exist
    """
    vault_path = get_vault_path()
    seed_path = vault_path / "agent" / "seed.md"
    
    if not seed_path.exists():
        raise FileNotFoundError(
            f"Seed file not found at {seed_path}. "
            "Please ensure agent/seed.md exists."
        )
    
    return seed_path.read_text(encoding="utf-8")


def read_personality() -> dict:
    """
    Read the agent personality file if it exists.
    
    Returns:
        dict: Personality traits, or default personality if file not found
    """
    vault_path = get_vault_path()
    personality_path = vault_path / "agent" / "personality.md"
    
    if not personality_path.exists():
        return _default_personality()
    
    content = personality_path.read_text(encoding="utf-8")
    return _parse_personality(content)


def _default_personality() -> dict:
    """
    Get default personality when personality.md doesn't exist.
    
    Returns:
        dict: Default personality traits
    """
    return {
        "name": "Agent",
        "traits": {
            "curious": 0.5,
            "careful": 0.5,
            "creative": 0.5,
            "methodical": 0.5
        },
        "biases": [],
        "blind_spots": [],
        "description": "Default personality - initialized on first awakening"
    }


def _parse_personality(content: str) -> dict:
    """
    Parse personality markdown content into a dictionary.
    
    Args:
        content: Raw markdown content from personality.md
        
    Returns:
        dict: Parsed personality data
    """
    personality = _default_personality()
    
    lines = content.strip().split("\n")
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("# "):
            personality["name"] = line[2:].strip()
        elif line.startswith("## "):
            section = line[3:].strip().lower()
            if section == "特质":
                current_section = "traits"
            elif section == "偏见":
                current_section = "biases"
            elif section == "盲点":
                current_section = "blind_spots"
            else:
                current_section = None
        elif current_section == "traits" and line.startswith("- "):
            trait_line = line[2:]
            if ": " in trait_line:
                key, value = trait_line.split(": ", 1)
                try:
                    personality["traits"][key.strip()] = float(value.strip())
                except ValueError:
                    pass
        elif current_section == "biases" and line.startswith("- "):
            personality["biases"].append(line[2:].strip())
        elif current_section == "blind_spots" and line.startswith("- "):
            personality["blind_spots"].append(line[2:].strip())
        elif line.startswith("> "):
            personality["description"] = line[2:].strip()
    
    return personality


def read_file(path: str) -> str:
    """
    Read a file from the vault.
    
    Args:
        path: Relative path from vault root (e.g., "agent/seed.md")
        
    Returns:
        str: File content
        
    Raises:
        FileNotFoundError: If file does not exist
    """
    vault_path = get_vault_path()
    file_path = vault_path / path
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    return file_path.read_text(encoding="utf-8")


def write_file(path: str, content: str) -> None:
    """
    Write content to a file in the vault.
    
    Args:
        path: Relative path from vault root
        content: Content to write
    """
    vault_path = get_vault_path()
    file_path = vault_path / path
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def ensure_vault_dirs() -> None:
    """
    Ensure the vault directory structure exists.
    Creates missing directories if needed.
    
    Directories created:
        - agent/goals/
        - agent/world/
        - agent/knowledge/
        - agent/logs/
    """
    vault_path = get_vault_path()
    
    required_dirs = [
        vault_path / "agent",
        vault_path / "agent" / "goals",
        vault_path / "agent" / "world",
        vault_path / "agent" / "knowledge",
        vault_path / "agent" / "logs",
    ]
    
    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)
        
        gitkeep = directory / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()


def get_memory_index_path() -> Path:
    """
    Get the path to the memory index file.
    
    Returns:
        Path: Path to agent/memory-index.json
    """
    vault_path = get_vault_path()
    return vault_path / "agent" / "memory-index.json"


def load_memory_index() -> dict:
    """
    Load the memory index from file.
    
    Returns:
        dict: Memory index data, or empty structure if file doesn't exist
    """
    index_path = get_memory_index_path()
    
    if not index_path.exists():
        return _default_memory_index()
    
    import json
    content = index_path.read_text(encoding="utf-8")
    return json.loads(content)


def save_memory_index(index: dict) -> None:
    """
    Save the memory index to file.
    
    Args:
        index: Memory index data to save
    """
    import json
    
    index_path = get_memory_index_path()
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _default_memory_index() -> dict:
    """
    Get default memory index structure.
    
    Returns:
        dict: Empty memory index
    """
    return {
        "version": "1.0.0",
        "created": None,
        "last_updated": None,
        "entries": [],
        "stats": {
            "total_entries": 0,
            "by_type": {}
        }
    }


def __all__ = [
    "get_vault_path",
    "read_seed",
    "read_personality",
    "read_file",
    "write_file",
    "ensure_vault_dirs",
    "get_memory_index_path",
    "load_memory_index",
    "save_memory_index",
    "get_state_path",
]
