"""
Memory System

Manages the Agent's world corpus — reading, writing, and organizing worldview
fragments as Obsidian markdown files with bidirectional links.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .world_fragment import WorldFragment
from .vault import get_vault_path


class MemorySystem:
    """
    Manages the Agent's world corpus — reading, writing, and organizing worldview fragments.

    The world corpus is stored in the vault's `agent/world/` directory as Obsidian
    markdown files with YAML frontmatter. This class provides CRUD operations for
    fragments and ensures bidirectional linking.
    """

    def __init__(self, world_dir: Optional[Path] = None, enable_index: bool = True) -> None:
        """
        Initialize the memory system.

        Args:
            world_dir: Optional custom world directory. Defaults to vault/agent/world/.
            enable_index: Whether to update the memory index on write/update/delete.
        """
        if world_dir is None:
            vault_path = get_vault_path()
            self._world_dir = vault_path / "agent" / "world"
            self._use_vault_index = True
        else:
            self._world_dir = world_dir
            self._use_vault_index = False

        self._enable_index = enable_index and self._use_vault_index
        self._world_dir.mkdir(parents=True, exist_ok=True)

    def write_fragment(self, fragment: WorldFragment) -> Path:
        """
        Write a WorldFragment to the world corpus as an Obsidian markdown file.

        Creates a markdown file with YAML frontmatter, checks for existing fragments
        to generate backlinks, and ensures the file has a semantic filename.

        Args:
            fragment: The WorldFragment to persist

        Returns:
            Path: Path to the created file
        """
        backlinks = self._find_backlinks(fragment.title)

        for linked_title in fragment.links:
            self._add_backlink_to_fragment(linked_title, fragment.title)

        content = fragment.to_markdown(backlinks=backlinks)

        filename = self._sanitize_filename(fragment.title)
        file_path = self._world_dir / f"{filename}.md"

        counter = 1
        while file_path.exists():
            file_path = self._world_dir / f"{filename}_{counter}.md"
            counter += 1

        file_path.write_text(content, encoding="utf-8")
        self._update_memory_index(fragment, file_path)

        return file_path

    def read_fragment(self, path: Path) -> WorldFragment:
        """
        Parse a world corpus markdown file back into a WorldFragment.

        Args:
            path: Path to the markdown file

        Returns:
            WorldFragment: Parsed fragment

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file format is invalid
        """
        if not path.exists():
            raise FileNotFoundError(f"Fragment file not found: {path}")

        content = path.read_text(encoding="utf-8")
        return self._parse_fragment_file(content, path)

    def read_all_fragments(self) -> list[WorldFragment]:
        """
        Read all fragments from the world corpus.

        Returns:
            list[WorldFragment]: List of all fragments, sorted by creation date
        """
        fragments = []

        for md_file in sorted(self._world_dir.glob("*.md")):
            try:
                fragment = self.read_fragment(md_file)
                fragments.append(fragment)
            except Exception:
                continue

        fragments.sort(key=lambda f: f.created_at)
        return fragments

    def get_fragment_by_title(self, title: str) -> WorldFragment | None:
        """
        Find a fragment by title (case-insensitive).

        Args:
            title: Fragment title to search for

        Returns:
            WorldFragment | None: Found fragment or None
        """
        fragments = self.read_all_fragments()
        title_lower = title.lower()

        for fragment in fragments:
            if fragment.title.lower() == title_lower:
                return fragment

        return None

    def update_fragment(self, path: Path, fragment: WorldFragment) -> None:
        """
        Update an existing fragment.

        Args:
            path: Path to the existing fragment file
            fragment: Updated fragment data

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Fragment file not found: {path}")

        old_title = self._extract_title_from_path(path)

        backlinks = self._find_backlinks(fragment.title)

        if old_title and old_title != fragment.title:
            self._update_links_to_fragment(old_title, fragment.title)

        content = fragment.to_markdown(backlinks=backlinks)
        path.write_text(content, encoding="utf-8")
        self._update_memory_index(fragment, path)

    def delete_fragment(self, path: Path) -> None:
        """
        Delete a fragment from the world corpus.

        Args:
            path: Path to the fragment file

        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Fragment file not found: {path}")

        fragment = self.read_fragment(path)
        path.unlink()

        self._remove_from_memory_index(fragment.title)

    def get_fragment_path(self, title: str) -> Path | None:
        """
        Get the file path for a fragment by title.

        Args:
            title: Fragment title

        Returns:
            Path | None: Path to the fragment file or None if not found
        """
        fragments = self.read_all_fragments()
        title_lower = title.lower()

        for fragment in fragments:
            if fragment.title.lower() == title_lower:
                filename = self._sanitize_filename(fragment.title)
                path = self._world_dir / f"{filename}.md"
                if path.exists():
                    return path

        return None

    def _find_backlinks(self, title: str) -> list[str]:
        """
        Find fragments that link to the given title.

        Args:
            title: Fragment title to find backlinks for

        Returns:
            list[str]: List of fragment titles that link to this fragment
        """
        backlinks = []
        title_lower = title.lower()

        for md_file in self._world_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
                for link in links:
                    if link.lower() == title_lower:
                        fragment_title = self._extract_title_from_content(content)
                        if fragment_title and fragment_title.lower() != title_lower:
                            backlinks.append(fragment_title)
                        break
            except Exception:
                continue

        return backlinks

    def _add_backlink_to_fragment(self, target_title: str, backlink_title: str) -> None:
        """
        Add a backlink reference to an existing fragment.

        Args:
            target_title: Title of the fragment to add backlink to
            backlink_title: Title of the fragment linking to target
        """
        target_lower = target_title.lower()

        for md_file in self._world_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                fragment_title = self._extract_title_from_content(content)

                if fragment_title and fragment_title.lower() == target_lower:
                    if f"[[{backlink_title}]]" not in content:
                        if content.rstrip().endswith("---"):
                            content = content + f"\n\n*被以下内容引用：*\n- [[{backlink_title}]]"
                        else:
                            content = content + f"\n\n---\n\n*被以下内容引用：*\n- [[{backlink_title}]]"
                        md_file.write_text(content, encoding="utf-8")
                    break
            except Exception:
                continue

    def _update_links_to_fragment(self, old_title: str, new_title: str) -> None:
        """
        Update wikilinks when a fragment is renamed.

        Args:
            old_title: Original fragment title
            new_title: New fragment title
        """
        title_lower = old_title.lower()

        for md_file in self._world_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if f"[[{old_title}]]" in content or f"[[{old_title}|" in content:
                    updated = re.sub(
                        rf'\[\[{re.escape(old_title)}(\|[^\]]+)?\]\]',
                        f'[[{new_title}\\1]]',
                        content
                    )
                    md_file.write_text(updated, encoding="utf-8")
            except Exception:
                continue

    def _sanitize_filename(self, title: str) -> str:
        """
        Convert a fragment title to a safe filename.

        Args:
            title: Fragment title

        Returns:
            str: Safe filename (without extension)
        """
        filename = title
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'\s+', '-', filename)
        filename = filename.strip('-')
        if len(filename) > 100:
            filename = filename[:100].rsplit('-', 1)[0]

        return filename or "untitled"

    def _extract_title_from_path(self, path: Path) -> Optional[str]:
        """
        Extract fragment title from file path by reading the file.

        Args:
            path: Path to the fragment file

        Returns:
            Optional[str]: Title or None if not found
        """
        try:
            content = path.read_text(encoding="utf-8")
            return self._extract_title_from_content(content)
        except Exception:
            return None

    def _extract_title_from_content(self, content: str) -> Optional[str]:
        """
        Extract fragment title from markdown content.

        Args:
            content: Markdown content

        Returns:
            Optional[str]: Title or None if not found
        """
        match = re.search(r'^#\s+(.+?)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return None

    def _parse_fragment_file(self, content: str, path: Path) -> WorldFragment:
        """
        Parse an Obsidian markdown file into a WorldFragment.

        Args:
            content: Raw file content
            path: File path (for error messages)

        Returns:
            WorldFragment: Parsed fragment

        Raises:
            ValueError: If the file format is invalid
        """
        if not content.startswith('---'):
            raise ValueError(f"Invalid fragment format: missing YAML frontmatter in {path}")

        parts = content.split('---', 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid fragment format: malformed YAML frontmatter in {path}")

        frontmatter_str = parts[1]
        body = parts[2].strip()

        frontmatter = self._parse_frontmatter(frontmatter_str)

        title = self._extract_title_from_content(body)
        if not title:
            title = path.stem

        created_str = frontmatter.get("created")
        if created_str:
            try:
                created_at = datetime.fromisoformat(created_str)
            except ValueError:
                created_at = datetime.now()
        else:
            created_at = datetime.now()

        fit_path = frontmatter.get("fit-path", "translation")
        source_file = frontmatter.get("source")

        collision_elements_str = frontmatter.get("collision-elements", "")
        collision_elements = []
        if collision_elements_str:
            collision_elements = [e.strip() for e in collision_elements_str.split(",") if e.strip()]

        links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', body)

        content_match = re.search(r'^#\s+.+?\n(.*?)(?=\n(?:相关链接:|标签:|$))', body, re.DOTALL)
        if content_match:
            prose = content_match.group(1)
            prose_lines = []
            for line in prose.split('\n'):
                if line.startswith('> '):
                    prose_lines.append(line[2:])
                elif line == '>':
                    prose_lines.append('')
            content_text = '\n'.join(prose_lines).strip()
        else:
            title_match = re.search(r'^#\s+.+?\n(.*)', body, re.DOTALL)
            if title_match:
                prose = title_match.group(1)
                prose_lines = []
                for line in prose.split('\n'):
                    if line.startswith('> '):
                        prose_lines.append(line[2:])
                    elif line == '>':
                        prose_lines.append('')
                content_text = '\n'.join(prose_lines).strip()
            else:
                content_text = body

        return WorldFragment(
            title=title,
            content=content_text,
            links=links,
            source_trigger=f"file:{path.name}",
            fit_path=fit_path,
            created_at=created_at,
            source_file=source_file,
            collision_elements=collision_elements,
        )

    def _parse_frontmatter(self, frontmatter_str: str) -> dict:
        """
        Parse YAML frontmatter into a dictionary.

        Args:
            frontmatter_str: YAML frontmatter content

        Returns:
            dict: Parsed frontmatter
        """
        result = {}
        current_key = None
        lines = frontmatter_str.strip().split('\n')

        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                result[key] = value
                current_key = key
            elif current_key and line.strip().startswith('-'):
                pass

        return result

    def _update_memory_index(self, fragment: WorldFragment, path: Path) -> None:
        """
        Update the memory index when a fragment is written.

        Args:
            fragment: The fragment that was written
            path: Path to the fragment file
        """
        if not self._enable_index:
            return

        from .vault import load_memory_index, save_memory_index

        index = load_memory_index()

        existing_entries = [
            e for e in index.get("entries", [])
            if e.get("title", "").lower() != fragment.title.lower()
        ]

        new_entry = {
            "title": fragment.title,
            "path": str(path.relative_to(get_vault_path())),
            "created_at": fragment.created_at.isoformat(),
            "fit_path": fragment.fit_path,
            "source_file": fragment.source_file,
            "links": fragment.links,
        }

        existing_entries.append(new_entry)
        index["entries"] = existing_entries
        index["last_updated"] = datetime.now().isoformat()

        stats = index.get("stats", {})
        stats["total_entries"] = len(existing_entries)

        by_type = {}
        for entry in existing_entries:
            fit_path = entry.get("fit_path", "translation")
            by_type[fit_path] = by_type.get(fit_path, 0) + 1
        stats["by_type"] = by_type
        index["stats"] = stats

        save_memory_index(index)

    def _remove_from_memory_index(self, title: str) -> None:
        """
        Remove a fragment from the memory index.

        Args:
            title: Title of the fragment to remove
        """
        if not self._enable_index:
            return

        from .vault import load_memory_index, save_memory_index

        index = load_memory_index()

        existing_entries = [
            e for e in index.get("entries", [])
            if e.get("title", "").lower() != title.lower()
        ]

        index["entries"] = existing_entries
        index["last_updated"] = datetime.now().isoformat()

        stats = index.get("stats", {})
        stats["total_entries"] = len(existing_entries)

        by_type = {}
        for entry in existing_entries:
            fit_path = entry.get("fit_path", "translation")
            by_type[fit_path] = by_type.get(fit_path, 0) + 1
        stats["by_type"] = by_type
        index["stats"] = stats

        save_memory_index(index)


__all__ = ["MemorySystem"]
