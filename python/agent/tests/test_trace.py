"""
Tests for Trace System

Tests the Trace and TraceInjector classes including:
- Callout formatting
- Permission checking
- Trace injection
- Trace removal
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from agent.core.trace import Trace, TraceInjector, CALLOUT_TYPES


class TestTrace:
    """Tests for Trace dataclass."""

    def test_trace_creation(self):
        """Trace should be created with required fields."""
        trace = Trace(
            content="Test trace content",
            callout_type="note"
        )
        assert trace.content == "Test trace content"
        assert trace.callout_type == "note"
        assert isinstance(trace.created_at, datetime)

    def test_trace_with_reflection(self):
        """Trace should store agent reflection."""
        trace = Trace(
            content="Content",
            callout_type="tip",
            agent_reflection="Agent thought process..."
        )
        assert trace.agent_reflection == "Agent thought process..."

    def test_trace_callout_type_validation(self):
        """Trace should validate callout_type."""
        trace = Trace(content="Test", callout_type="invalid")
        assert trace.callout_type == "note"  # Falls back to "note"

    def test_trace_valid_callout_types(self):
        """Trace should accept all valid callout types."""
        for callout_type in CALLOUT_TYPES:
            trace = Trace(content="Test", callout_type=callout_type)
            assert trace.callout_type == callout_type


class TestTraceInjector:
    """Tests for TraceInjector."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def injector(self, temp_vault):
        """Create a TraceInjector with temp vault."""
        return TraceInjector(temp_vault)

    def test_injector_creation(self, temp_vault):
        """TraceInjector should be created with vault path."""
        injector = TraceInjector(temp_vault)
        assert injector.vault_path == temp_vault

    def test_can_inject_regular_file(self, injector, temp_vault):
        """Should allow injection into regular files."""
        test_file = temp_vault / "test.md"
        test_file.write_text("# Test\n\nContent")
        
        assert injector.can_inject(str(test_file)) is True

    def test_can_inject_agent_directory(self, injector, temp_vault):
        """Should block injection into agent/ directory."""
        agent_dir = temp_vault / "agent"
        agent_dir.mkdir()
        test_file = agent_dir / "goal.md"
        test_file.write_text("# Goal\n\nContent")
        
        assert injector.can_inject(str(test_file)) is False

    def test_can_inject_obsidian_directory(self, injector, temp_vault):
        """Should block injection into .obsidian/ directory."""
        obsidian_dir = temp_vault / ".obsidian"
        obsidian_dir.mkdir()
        test_file = obsidian_dir / "workspace.json"
        test_file.write_text("{}")
        
        assert injector.can_inject(str(test_file)) is False

    def test_can_inject_trace_false_frontmatter(self, injector, temp_vault):
        """Should block injection when frontmatter has trace: false."""
        test_file = temp_vault / "protected.md"
        test_file.write_text("""---
trace: false
---

# Protected

Content
""")
        
        assert injector.can_inject(str(test_file)) is False

    def test_can_inject_trace_true_frontmatter(self, injector, temp_vault):
        """Should allow injection when frontmatter has trace: true."""
        test_file = temp_vault / "allowed.md"
        test_file.write_text("""---
trace: true
---

# Allowed

Content
""")
        
        assert injector.can_inject(str(test_file)) is True

    def test_can_inject_no_frontmatter(self, injector, temp_vault):
        """Should allow injection when no frontmatter exists."""
        test_file = temp_vault / "no_frontmatter.md"
        test_file.write_text("# No Frontmatter\n\nContent")
        
        assert injector.can_inject(str(test_file)) is True


class TestFormatCallout:
    """Tests for callout formatting."""

    @pytest.fixture
    def injector(self, tmp_path):
        """Create a TraceInjector."""
        return TraceInjector(tmp_path)

    def test_format_note_callout(self, injector):
        """Should format note callout correctly."""
        trace = Trace(
            content="This is a note",
            callout_type="note"
        )
        callout = injector.format_callout(trace)
        
        assert "> [!note] Agent 的痕迹" in callout
        assert "> This is a note" in callout
        assert callout.startswith(">")

    def test_format_callout_with_reflection(self, injector):
        """Should format callout with agent reflection."""
        trace = Trace(
            content="Content",
            callout_type="tip",
            agent_reflection="My thought process..."
        )
        callout = injector.format_callout(trace)
        
        assert "> [!tip] Agent 的痕迹" in callout
        assert "*My thought process...*" in callout

    def test_format_all_callout_types(self, injector):
        """Should format all valid callout types."""
        for callout_type in CALLOUT_TYPES:
            trace = Trace(content="Test", callout_type=callout_type)
            callout = injector.format_callout(trace)
            
            assert f"> [!{callout_type}]" in callout


class TestInjectTrace:
    """Tests for trace injection."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def injector(self, temp_vault):
        """Create a TraceInjector with temp vault."""
        return TraceInjector(temp_vault)

    def test_inject_at_end(self, injector, temp_vault):
        """Should inject trace at end of file."""
        test_file = temp_vault / "test.md"
        test_file.write_text("# Test\n\nOriginal content")
        
        trace = Trace(content="Injected trace", callout_type="note")
        result = injector.inject_trace(str(test_file), trace, position="end")
        
        assert result is True
        content = test_file.read_text()
        assert "Injected trace" in content
        assert "Original content" in content

    def test_inject_at_start(self, injector, temp_vault):
        """Should inject trace at start of file."""
        test_file = temp_vault / "test.md"
        test_file.write_text("# Test\n\nOriginal content")
        
        trace = Trace(content="First trace", callout_type="note")
        result = injector.inject_trace(str(test_file), trace, position="start")
        
        assert result is True
        content = test_file.read_text()
        assert "First trace" in content
        # Original content should come after the callout
        assert content.index("First trace") < content.index("Original content")

    def test_inject_after_heading(self, injector, temp_vault):
        """Should inject trace after first heading."""
        test_file = temp_vault / "test.md"
        test_file.write_text("# Title\n\nContent")
        
        trace = Trace(content="After heading", callout_type="note")
        result = injector.inject_trace(str(test_file), trace, position="after_heading")
        
        assert result is True
        content = test_file.read_text()
        # Should have heading, then callout, then content
        lines = content.split("\n")
        title_line = [i for i, l in enumerate(lines) if "# Title" in l][0]
        after_heading_line = [i for i, l in enumerate(lines) if "After heading" in l][0]
        content_line = [i for i, l in enumerate(lines) if "Content" in l and "#" not in l][0]
        
        assert title_line < after_heading_line < content_line

    def test_inject_blocked_by_permission(self, injector, temp_vault):
        """Should fail to inject when can_inject returns False."""
        agent_dir = temp_vault / "agent"
        agent_dir.mkdir()
        test_file = agent_dir / "goal.md"
        test_file.write_text("# Goal\n\nContent")
        
        trace = Trace(content="Blocked", callout_type="note")
        result = injector.inject_trace(str(test_file), trace)
        
        assert result is False

    def test_inject_nonexistent_file(self, injector, temp_vault):
        """Should fail to inject into nonexistent file."""
        trace = Trace(content="Test", callout_type="note")
        result = injector.inject_trace(str(temp_vault / "nonexistent.md"), trace)
        
        assert result is False


class TestRemoveTrace:
    """Tests for trace removal."""

    @pytest.fixture
    def temp_vault(self):
        """Create a temporary vault directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def injector(self, temp_vault):
        """Create a TraceInjector with temp vault."""
        return TraceInjector(temp_vault)

    def test_remove_trace(self, injector, temp_vault):
        """Should remove trace from file."""
        test_file = temp_vault / "test.md"
        content = """# Test

> [!note] Agent 的痕迹
> *2026-05-31 14:00*
> 
> Trace content

Original content
"""
        test_file.write_text(content)
        
        result = injector.remove_trace(str(test_file), "Trace content")
        
        assert result is True
        remaining = test_file.read_text()
        assert "Trace content" not in remaining
        assert "Original content" in remaining
        assert "> [!note]" not in remaining

    def test_remove_nonexistent_trace(self, injector, temp_vault):
        """Should return False when trace not found."""
        test_file = temp_vault / "test.md"
        test_file.write_text("# Test\n\nContent")
        
        result = injector.remove_trace(str(test_file), "Nonexistent")
        
        assert result is False


class TestGenerateTrace:
    """Tests for trace generation from fragments."""

    @pytest.fixture
    def injector(self, tmp_path):
        """Create a TraceInjector."""
        return TraceInjector(tmp_path)

    def test_generate_trace_basic(self, injector):
        """Should generate trace from fragment."""
        from agent.core.world_fragment import WorldFragment
        
        fragment = WorldFragment(
            title="测试片段",
            content="这是测试内容",
            fit_path="translation"
        )
        
        trace = injector.generate_trace(fragment)
        
        assert trace.content == "已将「测试片段」纳入图书馆收藏"
        assert trace.callout_type == "note"

    def test_generate_trace_collision(self, injector):
        """Should generate trace with reflection for collision."""
        from agent.core.world_fragment import WorldFragment
        
        fragment = WorldFragment(
            title="碰撞概念",
            content="碰撞产生的新内容",
            fit_path="collision"
        )
        
        trace = injector.generate_trace(fragment)
        
        assert "碰撞概念" in trace.agent_reflection


class TestCalloutFormat:
    """Tests for Obsidian callout format compliance."""

    @pytest.fixture
    def injector(self, tmp_path):
        """Create a TraceInjector."""
        return TraceInjector(tmp_path)

    def test_callout_format_structure(self, injector):
        """Should produce valid Obsidian callout format."""
        trace = Trace(
            content="Test content",
            callout_type="note",
            agent_reflection="Agent thought"
        )
        callout = injector.format_callout(trace)
        
        lines = callout.split("\n")
        
        # First line should be callout header
        assert lines[0] == "> [!note] Agent 的痕迹"
        
        # Second line should be timestamp
        assert lines[1].startswith("> *20")  # Timestamp like *2026-05-31*
        
        # Content lines should be quoted
        for line in lines[2:]:
            if line.strip():
                assert line.startswith(">")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
