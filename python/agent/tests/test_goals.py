"""
Tests for the Goal System.

These tests verify that goals are properly stored and managed as Obsidian
markdown files with YAML frontmatter.
"""

from __future__ import annotations

import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from agent.core.goals import Goal, GoalSystem, GoalStatus


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault directory for testing."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    goals_dir = vault_path / "agent" / "goals"
    goals_dir.mkdir(parents=True)
    return vault_path


@pytest.fixture
def goal_system(temp_vault):
    """Create a GoalSystem instance for testing."""
    return GoalSystem(temp_vault)


class TestGoalCreation:
    """Tests for goal creation."""

    def test_create_goal_basic(self, goal_system):
        """Test creating a basic goal."""
        goal = goal_system.create_goal(
            title="测试目标",
            description="这是一个测试目标"
        )

        assert goal.title == "测试目标"
        assert goal.status == "proposed"
        assert goal.description == "这是一个测试目标"
        assert goal.parent is None
        assert len(goal.execution_log) == 1
        assert goal.file_path is not None
        assert goal.file_path.exists()

    def test_create_goal_with_parent(self, goal_system):
        """Test creating a goal with a parent."""
        parent = goal_system.create_goal(title="父目标")
        child = goal_system.create_goal(
            title="子目标",
            parent="父目标"
        )

        parent_check = goal_system.get_goal("父目标")
        assert "子目标" in parent_check.children

    def test_create_goal_triggered_by_curiosity(self, goal_system):
        """Test creating a goal triggered by curiosity."""
        goal = goal_system.create_goal(
            title="好奇心目标",
            triggered_by="curiosity"
        )

        assert goal.curiosity_triggered is True

    def test_create_goal_with_special_characters(self, goal_system):
        """Test creating a goal with special characters in title."""
        goal = goal_system.create_goal(
            title="测试: 目标/含特殊*字符?",
            description="测试描述"
        )

        assert goal.title == "测试: 目标/含特殊*字符?"
        assert goal.file_path.exists()

    def test_create_duplicate_title_creates_unique_file(self, goal_system):
        """Test that duplicate titles create unique files."""
        goal1 = goal_system.create_goal(title="相同标题")
        goal2 = goal_system.create_goal(title="相同标题")

        assert goal1.file_path != goal2.file_path
        assert goal1.file_path.exists()
        assert goal2.file_path.exists()


class TestGoalRetrieval:
    """Tests for goal retrieval."""

    def test_get_goal_by_title(self, goal_system):
        """Test retrieving a goal by its title."""
        created_goal = goal_system.create_goal(
            title="检索测试目标",
            description="用于检索测试"
        )

        retrieved_goal = goal_system.get_goal("检索测试目标")

        assert retrieved_goal is not None
        assert retrieved_goal.title == created_goal.title
        assert retrieved_goal.description == created_goal.description
        assert retrieved_goal.status == created_goal.status

    def test_get_nonexistent_goal(self, goal_system):
        """Test retrieving a goal that doesn't exist."""
        result = goal_system.get_goal("不存在的目标")
        assert result is None

    def test_get_all_goals(self, goal_system):
        """Test retrieving all goals."""
        goal_system.create_goal(title="目标1")
        goal_system.create_goal(title="目标2")
        goal_system.create_goal(title="目标3")

        all_goals = goal_system.get_all_goals()

        assert len(all_goals) == 3
        titles = [g.title for g in all_goals]
        assert "目标1" in titles
        assert "目标2" in titles
        assert "目标3" in titles

    def test_get_goals_by_status(self, goal_system):
        """Test filtering goals by status."""
        goal_system.create_goal(title="提议中")
        accepted = goal_system.create_goal(title="已接受")
        goal_system.update_status("已接受", "accepted")

        proposed_goals = goal_system.get_goals_by_status("proposed")
        accepted_goals = goal_system.get_goals_by_status("accepted")

        assert len(proposed_goals) == 1
        assert proposed_goals[0].title == "提议中"
        assert len(accepted_goals) == 1
        assert accepted_goals[0].title == "已接受"

    def test_get_active_goals(self, goal_system):
        """Test getting active goals."""
        goal_system.create_goal(title="提议中")
        planned = goal_system.create_goal(title="已计划")
        goal_system.update_status("已计划", "planned")
        in_progress = goal_system.create_goal(title="进行中")
        goal_system.update_status("进行中", "in_progress")
        completed = goal_system.create_goal(title="已完成")
        goal_system.complete_goal("已完成")

        active_goals = goal_system.get_active_goals()

        assert len(active_goals) == 2
        titles = [g.title for g in active_goals]
        assert "已计划" in titles
        assert "进行中" in titles
        assert "提议中" not in titles
        assert "已完成" not in titles


class TestGoalUpdate:
    """Tests for goal updates."""

    def test_update_status(self, goal_system):
        """Test updating a goal's status."""
        goal_system.create_goal(title="状态测试")
        goal_system.update_status("状态测试", "in_progress")

        goal = goal_system.get_goal("状态测试")
        assert goal.status == "in_progress"

    def test_update_goal(self, goal_system):
        """Test updating a goal's data."""
        goal = goal_system.create_goal(
            title="更新测试",
            description="原始描述"
        )

        goal.description = "新描述"
        goal_system.update_goal(goal)

        updated = goal_system.get_goal("更新测试")
        assert updated.description == "新描述"

    def test_add_execution_log(self, goal_system):
        """Test adding an execution log entry."""
        goal_system.create_goal(title="日志测试")
        goal_system.add_execution_log("日志测试", "执行了某个操作")

        goal = goal_system.get_goal("日志测试")
        assert len(goal.execution_log) == 2
        assert "执行了某个操作" in goal.execution_log[-1]


class TestGoalLifecycle:
    """Tests for goal lifecycle methods."""

    def test_complete_goal(self, goal_system):
        """Test marking a goal as completed."""
        goal_system.create_goal(title="完成测试")
        goal_system.complete_goal("完成测试")

        goal = goal_system.get_goal("完成测试")
        assert goal.status == "completed"
        assert any("完成" in log for log in goal.execution_log)

    def test_fail_goal_without_reason(self, goal_system):
        """Test failing a goal without a reason."""
        goal_system.create_goal(title="失败测试")
        goal_system.fail_goal("失败测试")

        goal = goal_system.get_goal("失败测试")
        assert goal.status == "failed"

    def test_fail_goal_with_reason(self, goal_system):
        """Test failing a goal with a reason."""
        goal_system.create_goal(title="失败原因测试")
        goal_system.fail_goal("失败原因测试", "资源不足")

        goal = goal_system.get_goal("失败原因测试")
        assert goal.status == "failed"
        assert any("资源不足" in log for log in goal.execution_log)


class TestGoalHierarchy:
    """Tests for goal hierarchy (parent/child relationships)."""

    def test_add_child_to_parent(self, goal_system):
        """Test adding a child goal to a parent."""
        goal_system.create_goal(title="父目标")
        goal_system.create_goal(title="子目标")
        goal_system.add_child("父目标", "子目标")

        parent = goal_system.get_goal("父目标")
        assert "子目标" in parent.children

    def test_create_goal_with_parent_auto_links(self, goal_system):
        """Test that creating a goal with parent auto-links them."""
        goal_system.create_goal(title="自动父目标")
        child = goal_system.create_goal(title="自动子目标", parent="自动父目标")

        parent = goal_system.get_goal("自动父目标")
        assert "自动子目标" in parent.children


class TestGoalFileFormat:
    """Tests for the Obsidian markdown file format."""

    def test_goal_file_has_yaml_frontmatter(self, goal_system):
        """Test that goal files have proper YAML frontmatter."""
        goal_system.create_goal(title="格式测试")
        goal = goal_system.get_goal("格式测试")

        assert goal.file_path is not None
        content = goal.file_path.read_text(encoding="utf-8")

        assert content.startswith("---\n")
        assert "title: 格式测试" in content
        assert "status: proposed" in content
        assert "---" in content

    def test_goal_file_has_title_in_markdown(self, goal_system):
        """Test that goal files have markdown title."""
        goal_system.create_goal(title="Markdown标题测试")
        goal = goal_system.get_goal("Markdown标题测试")

        content = goal.file_path.read_text(encoding="utf-8")
        assert "# Markdown标题测试" in content

    def test_goal_file_includes_execution_log(self, goal_system):
        """Test that goal files include execution log."""
        goal_system.create_goal(title="日志格式测试")
        goal_system.add_execution_log("日志格式测试", "测试操作")

        goal = goal_system.get_goal("日志格式测试")
        content = goal.file_path.read_text(encoding="utf-8")

        assert "执行日志" in content or "—" in content


class TestGoalPersistence:
    """Tests for goal persistence across system instances."""

    def test_goal_persists_after_reinit(self, temp_vault):
        """Test that goals persist after creating a new GoalSystem instance."""
        system1 = GoalSystem(temp_vault)
        system1.create_goal(title="持久化测试")

        system2 = GoalSystem(temp_vault)
        goal = system2.get_goal("持久化测试")

        assert goal is not None
        assert goal.title == "持久化测试"

    def test_goal_updates_persist(self, temp_vault):
        """Test that goal updates persist across system instances."""
        system1 = GoalSystem(temp_vault)
        system1.create_goal(title="更新持久化测试")
        system1.update_status("更新持久化测试", "in_progress")

        system2 = GoalSystem(temp_vault)
        goal = system2.get_goal("更新持久化测试")

        assert goal.status == "in_progress"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_description(self, goal_system):
        """Test creating a goal with empty description."""
        goal = goal_system.create_goal(title="无描述目标")

        assert goal.description == ""
        assert goal.file_path.exists()

    def test_goal_with_unicode_characters(self, goal_system):
        """Test handling of unicode characters in goals."""
        goal = goal_system.create_goal(
            title="Unicode目标 🎯 émojis",
            description="描述 with unicode émojis 🎨"
        )

        retrieved = goal_system.get_goal("Unicode目标 🎯 émojis")
        assert retrieved is not None
        assert retrieved.title == "Unicode目标 🎯 émojis"

    def test_long_title(self, goal_system):
        """Test handling of very long titles."""
        long_title = "A" * 200
        goal = goal_system.create_goal(title=long_title)

        assert goal.title == long_title
        assert goal.file_path.exists()
