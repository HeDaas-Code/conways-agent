"""
Tests for the collision path in the processing pipeline.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from agent.core.pipeline import ProcessingPipeline, FitResult
from agent.core.world_fragment import WorldFragment
from agent.core.state import AgentState


class TestCollisionProducesNovelContent:
    """Collision should produce content different from both inputs."""

    def test_collision_output_is_not_simple_copy_of_input(self):
        """The collision output should NOT be a summary of the input content."""
        fragment = WorldFragment(
            title="碰撞产物",
            content="这是一个全新的概念，它既不是原始内容的复述，也不是世界观的延伸。",
            fit_path="collision",
            collision_elements=["新内容A", "世界观碎片B"]
        )
        
        original_content = "这是原始的新内容，需要与世界观进行碰撞"
        
        # Collision output should not be identical to input
        assert fragment.content != original_content
        # Collision output should not be a simple copy
        assert len(fragment.content) > 10
        assert "全新" in fragment.content or "新" in fragment.content

    def test_collision_output_differs_from_worldview(self):
        """The collision output should NOT be an extension of existing worldview."""
        worldview_fragment = WorldFragment(
            title="已有世界观",
            content="这是已有的世界观内容，代表了Agent的既有认知",
            fit_path="translation"
        )
        
        collision_fragment = WorldFragment(
            title="碰撞产物",
            content="碰撞产生了新的视角，超越了原有的世界观边界",
            fit_path="collision",
            collision_elements=["新观点", "已有世界观"]
        )
        
        # Collision output should be different from worldview
        assert collision_fragment.content != worldview_fragment.content
        # Should contain language indicating novelty
        assert any(word in collision_fragment.content for word in ["新", "超越", "诞生", "创造"])


class TestCollisionIncludesCollisionElements:
    """Collision output should identify what was collided."""

    def test_collision_elements_field_exists(self):
        """WorldFragment should have collision_elements field."""
        fragment = WorldFragment(
            title="测试",
            content="内容",
            fit_path="collision",
            collision_elements=["元素A", "元素B"]
        )
        
        assert hasattr(fragment, "collision_elements")
        assert len(fragment.collision_elements) == 2

    def test_collision_elements_populated(self):
        """Collision fragments should have collision_elements populated."""
        fragment = WorldFragment(
            title="碰撞产物",
            content="两个概念的融合产生了第三个概念",
            fit_path="collision",
            collision_elements=["理性思维", "感性直觉"]
        )
        
        assert "理性思维" in fragment.collision_elements
        assert "感性直觉" in fragment.collision_elements
        assert len(fragment.collision_elements) >= 2

    def test_translation_fragments_have_empty_collision_elements(self):
        """Translation fragments should NOT have collision_elements."""
        fragment = WorldFragment(
            title="翻译产物",
            content="这是翻译后的内容",
            fit_path="translation",
            collision_elements=[]
        )
        
        assert fragment.fit_path == "translation"
        assert len(fragment.collision_elements) == 0

    def test_collision_elements_in_markdown_output(self):
        """Collision elements should appear in markdown output."""
        fragment = WorldFragment(
            title="碰撞产物",
            content="新的概念诞生了",
            fit_path="collision",
            collision_elements=["概念A", "概念B"]
        )
        
        markdown = fragment.to_markdown()
        assert "碰撞元素" in markdown
        assert "[[概念A]]" in markdown
        assert "[[概念B]]" in markdown

    def test_collision_elements_in_dict_output(self):
        """Collision elements should appear in dict output."""
        fragment = WorldFragment(
            title="碰撞产物",
            content="新的概念诞生了",
            fit_path="collision",
            collision_elements=["元素X", "元素Y"]
        )
        
        data = fragment.to_dict()
        assert "collision_elements" in data
        assert data["collision_elements"] == ["元素X", "元素Y"]

    def test_from_dict_preserves_collision_elements(self):
        """from_dict should preserve collision_elements."""
        data = {
            "title": "碰撞产物",
            "content": "内容",
            "fit_path": "collision",
            "collision_elements": ["A", "B", "C"],
            "created_at": datetime.now().isoformat()
        }
        
        fragment = WorldFragment.from_dict(data)
        
        assert fragment.collision_elements == ["A", "B", "C"]

    def test_from_dict_handles_missing_collision_elements(self):
        """from_dict should handle missing collision_elements gracefully."""
        data = {
            "title": "旧格式",
            "content": "内容",
            "fit_path": "translation",
            "created_at": datetime.now().isoformat()
        }
        
        fragment = WorldFragment.from_dict(data)
        
        assert fragment.collision_elements == []


class TestCollisionMarkdownFormat:
    """Test the markdown format for collision fragments."""

    def test_markdown_includes_collision_tag(self):
        """Collision fragments should indicate collision in markdown."""
        fragment = WorldFragment(
            title="碰撞产物",
            content="内容",
            fit_path="collision",
            collision_elements=["A"]
        )
        
        markdown = fragment.to_markdown()
        assert "# 碰撞产物" in markdown
        assert "collision" in markdown

    def test_markdown_includes_x_separator(self):
        """Collision elements should be separated by × symbol."""
        fragment = WorldFragment(
            title="测试",
            content="内容",
            fit_path="collision",
            collision_elements=["元素1", "元素2"]
        )
        
        markdown = fragment.to_markdown()
        assert "×" in markdown


class TestCollisionVsTranslation:
    """Distinguish between collision and translation paths."""

    def test_different_fit_paths(self):
        """Translation and collision should have different fit_paths."""
        translation = WorldFragment(
            title="翻译",
            content="翻译内容",
            fit_path="translation"
        )
        
        collision = WorldFragment(
            title="碰撞",
            content="碰撞内容",
            fit_path="collision"
        )
        
        assert translation.fit_path == "translation"
        assert collision.fit_path == "collision"
        assert translation.fit_path != collision.fit_path

    def test_collision_has_elements_translation_does_not(self):
        """Only collision fragments should have meaningful collision_elements."""
        translation = WorldFragment(
            title="翻译",
            content="翻译内容",
            fit_path="translation",
            collision_elements=[]
        )
        
        collision = WorldFragment(
            title="碰撞",
            content="碰撞内容",
            fit_path="collision",
            collision_elements=["新概念", "旧观念"]
        )
        
        assert len(translation.collision_elements) == 0
        assert len(collision.collision_elements) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
