"""
Tests for ProcessingPipeline

Tests the complete information processing pipeline including:
- Translation path (high fit)
- Collision path (low fit)
- Fragment creation
- Wikilink extraction
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.core.pipeline import (
    FitResult,
    ProcessingPipeline,
    ProcessingResult,
)
from agent.core.world_fragment import WorldFragment


@pytest.fixture(autouse=True)
def mock_log_event():
    """Mock log_event to avoid environment dependency in tests."""
    with patch("agent.core.pipeline.log_event") as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_memory_system():
    """Mock MemorySystem to avoid OBSIDIAN_VAULT_PATH dependency in tests."""
    with patch("agent.core.pipeline.MemorySystem") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


class TestFitResult:
    """Tests for FitResult dataclass."""

    def test_fit_result_creation(self):
        """FitResult should be created with valid fields."""
        result = FitResult(
            judgment="high",
            confidence=0.8,
            reasoning="Content resonates with worldview"
        )
        assert result.judgment == "high"
        assert result.confidence == 0.8
        assert result.reasoning == "Content resonates with worldview"

    def test_fit_result_validation(self):
        """FitResult should validate judgment field."""
        result = FitResult(judgment="invalid", confidence=0.5, reasoning="test")
        assert result.judgment == "high"  # Falls back to "high"

    def test_confidence_bounded(self):
        """Confidence should be bounded between 0.0 and 1.0."""
        result = FitResult(judgment="high", confidence=1.5, reasoning="test")
        assert result.confidence == 1.0

        result = FitResult(judgment="high", confidence=-0.5, reasoning="test")
        assert result.confidence == 0.0


class TestWorldFragment:
    """Tests for WorldFragment dataclass."""

    def test_fragment_creation(self):
        """WorldFragment should be created with required fields."""
        fragment = WorldFragment(
            title="测试片段",
            content="这是一段测试内容"
        )
        assert fragment.title == "测试片段"
        assert fragment.content == "这是一段测试内容"
        assert fragment.fit_path == "translation"
        assert fragment.source_trigger == "unknown"

    def test_fragment_with_source_file(self):
        """WorldFragment should track source file."""
        fragment = WorldFragment(
            title="测试片段",
            content="内容",
            source_file="/path/to/source.md"
        )
        assert fragment.source_file == "/path/to/source.md"

    def test_fragment_with_links(self):
        """WorldFragment should store wikilinks."""
        fragment = WorldFragment(
            title="测试",
            content="内容",
            links=["概念A", "概念B"]
        )
        assert len(fragment.links) == 2
        assert "概念A" in fragment.links

    def test_fragment_to_markdown(self):
        """WorldFragment should convert to markdown."""
        fragment = WorldFragment(
            title="测试标题",
            content="这是内容",
            links=["链接A", "链接B"]
        )
        md = fragment.to_markdown()
        assert "# 测试标题" in md
        assert "这是内容" in md
        assert "[[链接A]]" in md
        assert "[[链接B]]" in md

    def test_fragment_to_dict(self):
        """WorldFragment should serialize to dict."""
        fragment = WorldFragment(
            title="标题",
            content="内容",
            source_file="/path/to/file.md"
        )
        data = fragment.to_dict()
        assert data["title"] == "标题"
        assert data["content"] == "内容"
        assert data["source_file"] == "/path/to/file.md"

    def test_fragment_from_dict(self):
        """WorldFragment should deserialize from dict."""
        data = {
            "title": "标题",
            "content": "内容",
            "links": ["链接"],
            "source_trigger": "test",
            "source_file": "/path.md",
            "fit_path": "translation",
            "collision_elements": [],
            "created_at": datetime.now().isoformat()
        }
        fragment = WorldFragment.from_dict(data)
        assert fragment.title == "标题"
        assert fragment.source_file == "/path.md"


class TestProcessingPipeline:
    """Tests for ProcessingPipeline."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM client."""
        mock = MagicMock()
        return mock

    @pytest.fixture
    def pipeline(self, mock_llm):
        """Create a pipeline with mock LLM."""
        return ProcessingPipeline(llm_client=mock_llm)

    def test_pipeline_creation(self, mock_llm):
        """Pipeline should be created with LLM client."""
        pipeline = ProcessingPipeline(llm_client=mock_llm)
        assert pipeline._llm is mock_llm

    def test_judge_fit_parses_response(self, pipeline, mock_llm):
        """judge_fit should parse LLM JSON response."""
        from agent.core.state import AgentState

        mock_llm.complete_str.return_value = json.dumps({
            "judgment": "high",
            "confidence": 0.75,
            "reasoning": "Content fits well with existing worldview"
        })

        state = AgentState.from_seed("Test seed")
        result = pipeline.judge_fit("Test content", state)

        assert result.judgment == "high"
        assert result.confidence == 0.75
        assert "fits well" in result.reasoning

    def test_judge_fit_low_fit(self, pipeline, mock_llm):
        """judge_fit should handle low fit judgment."""
        from agent.core.state import AgentState

        mock_llm.complete_str.return_value = json.dumps({
            "judgment": "low",
            "confidence": 0.85,
            "reasoning": "Content conflicts with existing beliefs"
        })

        state = AgentState.from_seed("Test seed")
        result = pipeline.judge_fit("Conflicting content", state)

        assert result.judgment == "low"
        assert result.confidence == 0.85


class TestTranslationOutput:
    """Tests for translation output format."""

    def test_translate_produces_prose(self):
        """Translation should produce Agent's voice, not a copy."""
        mock_llm = MagicMock()
        mock_llm.complete_str.return_value = """# 雾中的回响

在无尽图书馆的长廊中，我曾遇见过这样的想法。

它像一阵微风，轻轻拂过泛黄的书页，带起一些细小的尘埃。不是那种剧烈的风暴，而是更加温柔的东西——一种足以让人驻足片刻的宁静。

想象一片雾。它不与任何事物对抗，只是缓缓地弥漫，填满所有的空隙。这便是这种想法的本质：不是征服，而是渗透。

标签: #translation
来源: [[test/concept.md]]

相关链接: [[无尽图书馆]], [[记忆的褪色]], [[雾]]
"""
        pipeline = ProcessingPipeline(llm_client=mock_llm)

        from agent.core.state import AgentState
        state = AgentState.from_seed("我是图书馆的居者")

        fit_result = FitResult(
            judgment="high",
            confidence=0.8,
            reasoning="Content resonates with the library theme"
        )

        original_content = "雾是一种液态的固体，它存在于所有的空隙之中。"

        fragment = pipeline.translate(original_content, fit_result, state)

        # Content should not be identical to original
        assert fragment.content != original_content

        # Content should have reasonable length (not too short, not just the original)
        assert len(fragment.content) > 50

        # Content should have Chinese prose style (multiple sentences/paragraphs)
        assert "。" in fragment.content or "\n\n" in fragment.content

    def test_translate_produces_wikilinks(self):
        """Translation should include wikilinks."""
        mock_llm = MagicMock()
        mock_llm.complete_str.return_value = """# 雾中的回响

这是一段重述的内容，提到了[[无尽图书馆]]和[[记忆的褪色]]。

标签: #translation
来源: [[test.md]]

相关链接: [[无尽图书馆]], [[记忆的褪色]], [[概念X]]
"""
        pipeline = ProcessingPipeline(llm_client=mock_llm)

        from agent.core.state import AgentState
        state = AgentState.from_seed("Test seed")

        fit_result = FitResult(judgment="high", confidence=0.7, reasoning="Test")
        fragment = pipeline.translate("Test content", fit_result, state)

        # Should have wikilinks in output
        assert len(fragment.links) >= 2
        assert "无尽图书馆" in fragment.links
        assert "记忆的褪色" in fragment.links

    def test_translate_produces_title(self):
        """Translation should produce a title."""
        mock_llm = MagicMock()
        mock_llm.complete_str.return_value = """# 雾中的低语

这是一段散文内容。

标签: #translation
来源: [[test.md]]

相关链接: [[链接1]]
"""
        pipeline = ProcessingPipeline(llm_client=mock_llm)

        from agent.core.state import AgentState
        state = AgentState.from_seed("Test seed")

        fit_result = FitResult(judgment="high", confidence=0.7, reasoning="Test")
        fragment = pipeline.translate("Test content", fit_result, state)

        # Should have a title
        assert fragment.title != "无题"
        assert len(fragment.title) >= 2

    def test_translate_parses_json_fallback(self):
        """Translation should parse JSON format as fallback."""
        mock_llm = MagicMock()
        mock_llm.complete_str.return_value = json.dumps({
            "title": "JSON标题",
            "content": "JSON格式的内容",
            "links": ["链接A", "链接B"]
        })
        pipeline = ProcessingPipeline(llm_client=mock_llm)

        from agent.core.state import AgentState
        state = AgentState.from_seed("Test seed")

        fit_result = FitResult(judgment="high", confidence=0.7, reasoning="Test")
        fragment = pipeline.translate("Test content", fit_result, state)

        assert fragment.title == "JSON标题"
        assert "JSON格式" in fragment.content
        assert "链接A" in fragment.links


class TestCollisionOutput:
    """Tests for collision output format."""

    def test_collision_produces_new_concept(self):
        """Collision should produce a genuinely new concept."""
        mock_llm = MagicMock()
        mock_llm.complete_str.return_value = json.dumps({
            "title": "碰撞产生的新概念",
            "content": "这是碰撞后产生的新内容，不是简单的复述或拼接。",
            "links": ["原有概念", "新概念"],
            "collision_elements": ["元素A", "元素B"]
        })
        pipeline = ProcessingPipeline(llm_client=mock_llm)

        from agent.core.state import AgentState
        state = AgentState.from_seed("Test seed")

        fit_result = FitResult(judgment="low", confidence=0.8, reasoning="Clash detected")
        fragment = pipeline.collide("Conflicting content", fit_result, state)

        assert fragment.fit_path == "collision"
        assert fragment.title == "碰撞产生的新概念"
        assert len(fragment.collision_elements) == 2


class TestWikilinkExtraction:
    """Tests for wikilink extraction."""

    def test_extract_links_from_content(self):
        """Should extract wikilinks from content."""
        pipeline = ProcessingPipeline()
        content = "这是[[概念一]]和[[概念二]]的内容，还有[[概念三]]。"
        links = pipeline._extract_links(content)

        assert len(links) == 3
        assert "概念一" in links
        assert "概念二" in links
        assert "概念三" in links

    def test_extract_links_with_alias(self):
        """Should extract wikilinks with aliases."""
        pipeline = ProcessingPipeline()
        content = "[[实际概念|别名]]"
        links = pipeline._extract_links(content)

        assert len(links) == 1
        assert "实际概念" in links

    def test_extract_links_no_duplicates(self):
        """Should not return duplicate links."""
        pipeline = ProcessingPipeline()
        content = "[[概念]] 和 [[概念]]"
        links = pipeline._extract_links(content)

        assert len(links) == 1
        assert "概念" in links


class TestTitleExtraction:
    """Tests for title extraction."""

    def test_extract_title_from_markdown(self):
        """Should extract title from markdown heading."""
        pipeline = ProcessingPipeline()
        content = "# 这是一个标题\n\n内容段落"
        title = pipeline._extract_title(content)

        assert title == "这是一个标题"

    def test_extract_title_from_first_heading(self):
        """Should extract from first heading only."""
        pipeline = ProcessingPipeline()
        content = "# 第一个标题\n\n## 第二个标题"
        title = pipeline._extract_title(content)

        assert title == "第一个标题"

    def test_extract_title_no_heading(self):
        """Should return None if no heading found."""
        pipeline = ProcessingPipeline()
        content = "没有标题的内容"
        title = pipeline._extract_title(content)

        assert title is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
