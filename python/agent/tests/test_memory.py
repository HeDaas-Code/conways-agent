"""
Tests for the Memory System

Tests fragment persistence, Obsidian markdown format, and bidirectional links.
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from agent.core.memory import MemorySystem
from agent.core.world_fragment import WorldFragment


@pytest.fixture
def temp_world_dir():
    """Create a temporary world directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def memory_system(temp_world_dir):
    """Create a MemorySystem with a temporary directory."""
    return MemorySystem(world_dir=temp_world_dir)


@pytest.fixture
def sample_fragment():
    """Create a sample WorldFragment for testing."""
    return WorldFragment(
        title="无尽图书馆中的量子",
        content="这是一段用 Agent 声音重写的关于量子力学的描述...",
        links=["既有概念A", "既有概念B"],
        source_trigger="translation:notes/quantum.md",
        fit_path="translation",
        created_at=datetime(2026, 5, 31, 16, 0, 0),
        source_file="notes/quantum.md",
    )


def test_write_and_read_roundtrip(memory_system, sample_fragment):
    """Writing and reading a fragment should produce equivalent data."""
    path = memory_system.write_fragment(sample_fragment)

    assert path.exists()
    assert path.suffix == ".md"

    read_fragment = memory_system.read_fragment(path)

    assert read_fragment.title == sample_fragment.title
    assert read_fragment.content == sample_fragment.content
    assert read_fragment.fit_path == sample_fragment.fit_path
    assert read_fragment.source_file == sample_fragment.source_file

    assert set(read_fragment.links) == set(sample_fragment.links)


def test_fragment_file_format(memory_system, sample_fragment):
    """Fragment file should have valid YAML frontmatter and wikilinks."""
    path = memory_system.write_fragment(sample_fragment)

    content = path.read_text(encoding="utf-8")

    assert content.startswith("---")

    frontmatter_end = content.find("---", 3)
    assert frontmatter_end > 0

    frontmatter = content[3:frontmatter_end].strip()
    assert "created: 2026-05-31T16:00:00" in frontmatter
    assert "type: world-fragment" in frontmatter
    assert "fit-path: translation" in frontmatter
    assert "source: notes/quantum.md" in frontmatter

    assert "# 无尽图书馆中的量子" in content

    for link in sample_fragment.links:
        assert f"[[{link}]]" in content

    assert "#translation" in content


def test_write_multiple_fragments(memory_system):
    """Writing multiple fragments should create separate files."""
    fragments = [
        WorldFragment(
            title=f"Fragment {i}",
            content=f"Content {i}",
            links=["相关概念"],
            fit_path="translation",
            created_at=datetime.now(),
        )
        for i in range(3)
    ]

    paths = [memory_system.write_fragment(f) for f in fragments]

    assert len(set(paths)) == 3

    for path in paths:
        assert path.exists()


def test_read_all_fragments(memory_system):
    """read_all_fragments should return all fragments sorted by creation date."""
    fragment1 = WorldFragment(
        title="First Fragment",
        content="Content 1",
        fit_path="translation",
        created_at=datetime(2026, 1, 1),
    )
    fragment2 = WorldFragment(
        title="Second Fragment",
        content="Content 2",
        fit_path="collision",
        created_at=datetime(2026, 6, 1),
    )

    memory_system.write_fragment(fragment1)
    memory_system.write_fragment(fragment2)

    all_fragments = memory_system.read_all_fragments()

    assert len(all_fragments) == 2
    assert all_fragments[0].title == "First Fragment"
    assert all_fragments[1].title == "Second Fragment"


def test_get_fragment_by_title(memory_system):
    """get_fragment_by_title should find fragments case-insensitively."""
    fragment = WorldFragment(
        title="量子力学概论",
        content="Content",
        fit_path="translation",
        created_at=datetime.now(),
    )
    memory_system.write_fragment(fragment)

    found = memory_system.get_fragment_by_title("量子力学概论")
    assert found is not None
    assert found.title == fragment.title

    found_case = memory_system.get_fragment_by_title("量子力学概论".upper())
    assert found_case is not None
    assert found_case.title == fragment.title

    not_found = memory_system.get_fragment_by_title("不存在的标题")
    assert not_found is None


def test_update_fragment(memory_system):
    """update_fragment should modify an existing fragment."""
    original = WorldFragment(
        title="Original Title",
        content="Original content",
        fit_path="translation",
        created_at=datetime.now(),
    )
    path = memory_system.write_fragment(original)

    updated = WorldFragment(
        title="Updated Title",
        content="Updated content",
        fit_path="translation",
        created_at=original.created_at,
    )
    memory_system.update_fragment(path, updated)

    read_back = memory_system.read_fragment(path)
    assert read_back.title == "Updated Title"
    assert read_back.content == "Updated content"


def test_delete_fragment(memory_system):
    """delete_fragment should remove the fragment file."""
    fragment = WorldFragment(
        title="To Be Deleted",
        content="Content",
        fit_path="translation",
        created_at=datetime.now(),
    )
    path = memory_system.write_fragment(fragment)

    assert path.exists()

    memory_system.delete_fragment(path)

    assert not path.exists()


def test_backlinks(memory_system):
    """Fragments linking to each other should have backlinks in file content."""
    fragment_a = WorldFragment(
        title="概念A",
        content="这是概念A的内容",
        links=[],
        fit_path="translation",
        created_at=datetime(2026, 1, 1),
    )
    path_a = memory_system.write_fragment(fragment_a)

    fragment_b = WorldFragment(
        title="概念B",
        content="这是概念B的内容，它链接到A",
        links=["概念A"],
        fit_path="translation",
        created_at=datetime(2026, 1, 2),
    )
    memory_system.write_fragment(fragment_b)

    content_a = path_a.read_text(encoding="utf-8")
    assert "概念B" in content_a


def test_sanitize_filename(memory_system):
    """Special characters in titles should be sanitized in filenames."""
    fragment = WorldFragment(
        title="测试: 标题 / 带 | 特殊? 字符",
        content="Content",
        fit_path="translation",
        created_at=datetime.now(),
    )
    path = memory_system.write_fragment(fragment)

    filename = path.stem
    assert ":" not in filename
    assert "/" not in filename
    assert "|" not in filename
    assert "?" not in filename
    assert "*" not in filename


def test_to_markdown_obsidian_format():
    """to_markdown should produce valid Obsidian markdown."""
    fragment = WorldFragment(
        title="测试片段",
        content="这是一段测试内容",
        links=["链接A", "链接B"],
        fit_path="translation",
        created_at=datetime(2026, 5, 31, 10, 30, 0),
        source_file="test.md",
    )

    markdown = fragment.to_markdown()

    lines = markdown.split("\n")
    assert lines[0] == "---"
    assert lines[1] == "created: 2026-05-31T10:30:00"
    assert lines[2] == "type: world-fragment"
    assert lines[3] == "fit-path: translation"
    assert lines[4] == "source: test.md"
    assert lines[5] == "---"

    assert "# 测试片段" in markdown
    assert "> 这是一段测试内容" in markdown
    assert "[[链接A]]" in markdown
    assert "[[链接B]]" in markdown
    assert "#translation" in markdown


def test_to_markdown_with_backlinks():
    """to_markdown should include backlinks section when provided."""
    fragment = WorldFragment(
        title="主片段",
        content="内容",
        links=["链接"],
        fit_path="translation",
        created_at=datetime.now(),
    )

    markdown = fragment.to_markdown(backlinks=["引用者A", "引用者B"])

    assert "*被以下内容引用：*" in markdown
    assert "[[引用者A]]" in markdown
    assert "[[引用者B]]" in markdown


def test_to_markdown_collision_path():
    """to_markdown should include collision elements for collision path."""
    fragment = WorldFragment(
        title="碰撞产物",
        content="碰撞产生的新概念",
        links=["元素A"],
        fit_path="collision",
        collision_elements=["元素A", "元素B"],
        created_at=datetime.now(),
    )

    markdown = fragment.to_markdown()

    assert "fit-path: collision" in markdown
    assert "**碰撞元素:**" in markdown
    assert "[[元素A]]" in markdown
    assert "[[元素B]]" in markdown


def test_collision_roundtrip(memory_system):
    """Collision fragments should survive write-read roundtrip."""
    fragment = WorldFragment(
        title="碰撞产物",
        content="两个概念碰撞产生的第三个概念",
        links=["虚无", "无尽"],
        fit_path="collision",
        collision_elements=["虚无", "无尽"],
        created_at=datetime.now(),
    )

    path = memory_system.write_fragment(fragment)
    read_back = memory_system.read_fragment(path)

    assert read_back.title == fragment.title
    assert read_back.fit_path == "collision"
    assert "虚无" in read_back.collision_elements
    assert "无尽" in read_back.collision_elements
