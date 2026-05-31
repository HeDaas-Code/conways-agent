"""
Tests for BehaviorExecutors - actual behavior execution functions.

Issue #39:
- world_fragment_executor: Generate world fragment from topics
- explore_links_executor: Explore note links
- deep_reflection_executor: Deep reflection on interests
"""

import pytest
import os
import tempfile
import yaml
from datetime import datetime


class TestWorldFragmentExecutor:
    """Tests for world_fragment_executor."""

    def test_world_fragment_creates_file(self):
        """world_fragment_executor should create a markdown file."""
        from agent.core.behavior_executors import world_fragment_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = world_fragment_executor(topics=["python", "ai"], vault_path=tmpdir)
            
            assert result.success is True
            assert result.output_path is not None
            assert os.path.exists(result.output_path)

    def test_world_fragment_file_has_correct_type(self):
        """Generated file should have type: world-fragment in frontmatter."""
        from agent.core.behavior_executors import world_fragment_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = world_fragment_executor(topics=["python", "ai"], vault_path=tmpdir)
            
            with open(result.output_path, "r") as f:
                content = f.read()
            
            # Extract frontmatter
            parts = content.split("---")
            frontmatter = yaml.safe_load(parts[1])
            
            assert frontmatter["type"] == "world-fragment"
            assert frontmatter["behavior"] == "WORLD_FRAGMENT"

    def test_world_fragment_includes_topics(self):
        """Generated file should include topics in frontmatter."""
        from agent.core.behavior_executors import world_fragment_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            topics = ["python", "ai", "machine-learning"]
            result = world_fragment_executor(topics=topics, vault_path=tmpdir)
            
            with open(result.output_path, "r") as f:
                content = f.read()
            
            parts = content.split("---")
            frontmatter = yaml.safe_load(parts[1])
            
            assert "topics" in frontmatter
            for topic in topics:
                assert topic in frontmatter["topics"]

    def test_world_fragment_content_has_structure(self):
        """Content should have expected sections."""
        from agent.core.behavior_executors import world_fragment_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = world_fragment_executor(topics=["test"], vault_path=tmpdir)
            
            with open(result.output_path, "r") as f:
                content = f.read()
            
            # Should have some content after frontmatter
            body = content.split("---")[2] if len(content.split("---")) > 2 else ""
            assert len(body.strip()) > 0

    def test_world_fragment_filename_pattern(self):
        """Filename should follow pattern."""
        from agent.core.behavior_executors import world_fragment_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = world_fragment_executor(topics=["test"], vault_path=tmpdir)
            
            filename = os.path.basename(result.output_path)
            assert filename.startswith("world-fragment_")
            assert filename.endswith(".md")


class TestExploreLinksExecutor:
    """Tests for explore_links_executor."""

    def test_explore_links_creates_file(self):
        """explore_links_executor should create a markdown file."""
        from agent.core.behavior_executors import explore_links_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = explore_links_executor(
                topics=["python"],
                files=["notes/a.md", "notes/b.md"],
                vault_path=tmpdir
            )
            
            assert result.success is True
            assert result.output_path is not None
            assert os.path.exists(result.output_path)

    def test_explore_links_file_has_correct_type(self):
        """Generated file should have type: link-exploration in frontmatter."""
        from agent.core.behavior_executors import explore_links_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = explore_links_executor(
                topics=["python"],
                files=["notes/a.md"],
                vault_path=tmpdir
            )
            
            with open(result.output_path, "r") as f:
                content = f.read()
            
            parts = content.split("---")
            frontmatter = yaml.safe_load(parts[1])
            
            assert frontmatter["type"] == "link-exploration"
            assert frontmatter["behavior"] == "EXPLORE_LINKS"

    def test_explore_links_includes_files_explored(self):
        """Generated file should track files explored."""
        from agent.core.behavior_executors import explore_links_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            files = ["notes/a.md", "notes/b.md", "notes/c.md"]
            result = explore_links_executor(
                topics=["python"],
                files=files,
                vault_path=tmpdir
            )
            
            with open(result.output_path, "r") as f:
                content = f.read()
            
            parts = content.split("---")
            frontmatter = yaml.safe_load(parts[1])
            
            assert "files_explored" in frontmatter
            assert frontmatter["files_explored"] == len(files)

    def test_explore_links_filename_pattern(self):
        """Filename should follow pattern."""
        from agent.core.behavior_executors import explore_links_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = explore_links_executor(
                topics=["test"],
                files=["a.md"],
                vault_path=tmpdir
            )
            
            filename = os.path.basename(result.output_path)
            assert filename.startswith("explore-links_")
            assert filename.endswith(".md")


class TestDeepReflectionExecutor:
    """Tests for deep_reflection_executor."""

    def test_deep_reflection_creates_file(self):
        """deep_reflection_executor should create a markdown file."""
        from agent.core.behavior_executors import deep_reflection_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = deep_reflection_executor(
                topics=["python", "ai"],
                from_points=30,
                to_points=60,
                vault_path=tmpdir
            )
            
            assert result.success is True
            assert result.output_path is not None
            assert os.path.exists(result.output_path)

    def test_deep_reflection_file_has_correct_type(self):
        """Generated file should have type: deep-reflection in frontmatter."""
        from agent.core.behavior_executors import deep_reflection_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = deep_reflection_executor(
                topics=["test"],
                from_points=30,
                to_points=60,
                vault_path=tmpdir
            )
            
            with open(result.output_path, "r") as f:
                content = f.read()
            
            parts = content.split("---")
            frontmatter = yaml.safe_load(parts[1])
            
            assert frontmatter["type"] == "deep-reflection"
            assert frontmatter["behavior"] == "DEEP_REFLECTION"

    def test_deep_reflection_includes_points_delta(self):
        """Generated file should track points delta."""
        from agent.core.behavior_executors import deep_reflection_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = deep_reflection_executor(
                topics=["test"],
                from_points=30,
                to_points=60,
                vault_path=tmpdir
            )
            
            with open(result.output_path, "r") as f:
                content = f.read()
            
            parts = content.split("---")
            frontmatter = yaml.safe_load(parts[1])
            
            assert "points_delta" in frontmatter
            assert frontmatter["points_delta"] == 30

    def test_deep_reflection_filename_pattern(self):
        """Filename should follow pattern."""
        from agent.core.behavior_executors import deep_reflection_executor
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = deep_reflection_executor(
                topics=["test"],
                from_points=30,
                to_points=60,
                vault_path=tmpdir
            )
            
            filename = os.path.basename(result.output_path)
            assert filename.startswith("deep-reflection_")
            assert filename.endswith(".md")


class TestExecutorRegistry:
    """Test executor registry functions."""

    def test_get_executor_returns_correct_function(self):
        """get_executor should return correct executor for each behavior."""
        from agent.core.behavior_executors import get_executor
        
        wf = get_executor("WORLD_FRAGMENT")
        assert wf is not None
        assert wf.__name__ == "world_fragment_executor"
        
        el = get_executor("EXPLORE_LINKS")
        assert el is not None
        assert el.__name__ == "explore_links_executor"
        
        dr = get_executor("DEEP_REFLECTION")
        assert dr is not None
        assert dr.__name__ == "deep_reflection_executor"

    def test_get_executor_case_insensitive(self):
        """get_executor should be case insensitive."""
        from agent.core.behavior_executors import get_executor
        
        wf_upper = get_executor("WORLD_FRAGMENT")
        wf_lower = get_executor("world_fragment")
        wf_mixed = get_executor("World_Fragment")
        
        assert wf_upper is wf_lower is wf_mixed

    def test_get_executor_invalid_returns_none(self):
        """get_executor with invalid name should return None."""
        from agent.core.behavior_executors import get_executor
        
        result = get_executor("INVALID_BEHAVIOR")
        
        assert result is None


class TestVaultPathCompliance:
    """Test Vault path specification compliance."""

    def test_all_executors_write_to_vault_agent_world(self):
        """All executors should write to vault/agent/world/."""
        from agent.core.behavior_executors import (
            world_fragment_executor,
            explore_links_executor,
            deep_reflection_executor,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # World Fragment
            result1 = world_fragment_executor(topics=["test"], vault_path=tmpdir)
            assert "vault/agent/world" in result1.output_path
            
            # Explore Links
            result2 = explore_links_executor(
                topics=["test"],
                files=["a.md"],
                vault_path=tmpdir
            )
            assert "vault/agent/world" in result2.output_path
            
            # Deep Reflection
            result3 = deep_reflection_executor(
                topics=["test"],
                from_points=30,
                to_points=60,
                vault_path=tmpdir
            )
            assert "vault/agent/world" in result3.output_path


class TestExecutorIntegration:
    """Integration tests for executors with BehaviorPool."""

    def test_executor_registered_in_pool(self):
        """Executors should be usable via pool registration."""
        from agent.core.behavior_pool import BehaviorPool
        from agent.core.behavior_executors import get_executor
        
        pool = BehaviorPool()
        
        # All preset behaviors should have executors
        for name in ["WORLD_FRAGMENT", "EXPLORE_LINKS", "DEEP_REFLECTION"]:
            executor = get_executor(name)
            pool.register_behavior(
                pool.get_behavior(name),
                executor=executor
            )
        
        # Pool should now have executors attached
        assert pool.get_behavior("WORLD_FRAGMENT").executor is not None
        assert pool.get_behavior("EXPLORE_LINKS").executor is not None
        assert pool.get_behavior("DEEP_REFLECTION").executor is not None
