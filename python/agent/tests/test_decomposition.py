"""
Tests for Goal Decomposition System.

Tests the hierarchical task decomposition feature including:
- Goal decomposition into sub-goals
- Sub-goal lifecycle management
- Auto-completion when all children are done
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.core.goals import Goal, GoalSystem


class MockLLMClient:
    """Mock LLM client for testing decomposition."""

    def __init__(self, response: str = ""):
        self.response = response
        self.call_count = 0

    def complete_str(self, system: str, user: str, **kwargs) -> str:
        self.call_count += 1
        return self.response


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


class TestSubGoalParsing:
    """Tests for parsing LLM responses into sub-goals."""

    def test_parse_sub_goals_with_chinese_format(self, goal_system):
        """Test parsing sub-goals in Chinese format."""
        response = """子目标1：研究阶段 — 收集相关信息
子目标2：设计阶段 — 制定实施方案
子目标3：实施阶段 — 执行计划"""

        sub_goals = goal_system._parse_sub_goals(response)

        assert len(sub_goals) == 3
        assert sub_goals[0] == ("研究阶段", "收集相关信息")
        assert sub_goals[1] == ("设计阶段", "制定实施方案")
        assert sub_goals[2] == ("实施阶段", "执行计划")

    def test_parse_sub_goals_with_english_numbers(self, goal_system):
        """Test parsing sub-goals with English numbers."""
        response = """1. Research Phase - Gather relevant information
2. Design Phase - Create implementation plan
3. Execution Phase - Execute the plan"""

        sub_goals = goal_system._parse_sub_goals(response)

        assert len(sub_goals) == 3
        assert sub_goals[0][0] == "Research Phase"
        assert sub_goals[1][0] == "Design Phase"
        assert sub_goals[2][0] == "Execution Phase"

    def test_parse_sub_goals_with_bullet_points(self, goal_system):
        """Test parsing sub-goals with bullet points."""
        response = """- 第一步：准备工作
- 第二步：执行任务
- 第三步：验证结果"""

        sub_goals = goal_system._parse_sub_goals(response)

        assert len(sub_goals) == 3

    def test_parse_sub_goals_empty_response(self, goal_system):
        """Test parsing empty response."""
        sub_goals = goal_system._parse_sub_goals("")
        assert sub_goals == []

    def test_parse_sub_goals_mixed_format(self, goal_system):
        """Test parsing mixed format response."""
        response = """子目标1：开始工作 — 初始化系统
子目标2：核心处理 — 完成主要逻辑
子目标3：收尾工作 — 清理资源"""

        sub_goals = goal_system._parse_sub_goals(response)
        assert len(sub_goals) == 3


class TestGoalDecomposition:
    """Tests for goal decomposition functionality."""

    def test_decompose_goal_creates_children(self, goal_system):
        """Test that decompose_goal creates child goals."""
        parent = goal_system.create_goal(
            title="测试父目标",
            description="这是一个需要分解的复杂目标"
        )
        goal_system.update_status("测试父目标", "accepted")

        mock_llm = MockLLMClient(
            response="""子目标1：准备阶段 — 收集所需资源
子目标2：实施阶段 — 执行核心任务
子目标3：验证阶段 — 确认结果正确"""
        )

        with patch.object(goal_system, 'llm_client', mock_llm):
            sub_goals = goal_system.decompose_goal("测试父目标", mock_llm)

        assert len(sub_goals) == 3
        assert all(g.parent == "测试父目标" for g in sub_goals)

    def test_decompose_goal_sets_planned_status(self, goal_system):
        """Test that decomposed goals have 'planned' status."""
        goal_system.create_goal(title="父目标")
        goal_system.update_status("父目标", "accepted")

        mock_llm = MockLLMClient(
            response="""子目标1：第一步 — 完成初始工作
子目标2：第二步 — 进行主要工作"""
        )

        sub_goals = goal_system.decompose_goal("父目标", mock_llm)

        for sub_goal in sub_goals:
            assert sub_goal.status == "planned"

    def test_decompose_goal_logs_action(self, goal_system):
        """Test that decomposition is logged in parent's execution log."""
        goal_system.create_goal(title="日志测试目标")
        goal_system.update_status("日志测试目标", "accepted")

        mock_llm = MockLLMClient(
            response="""子目标1：步骤一 — 描述一
子目标2：步骤二 — 描述二"""
        )

        goal_system.decompose_goal("日志测试目标", mock_llm)

        parent = goal_system.get_goal("日志测试目标")
        log_entries = [entry for entry in parent.execution_log if "分解" in entry]
        assert len(log_entries) > 0

    def test_decompose_goal_parent_not_found(self, goal_system):
        """Test decomposition when parent doesn't exist."""
        mock_llm = MockLLMClient(response="子目标1：步骤 — 描述")

        sub_goals = goal_system.decompose_goal("不存在的目标", mock_llm)
        assert sub_goals == []

    def test_decompose_goal_with_no_llm_client(self, goal_system):
        """Test that decompose_goal works without explicit LLM client."""
        goal_system.create_goal(title="无客户端测试")

        with patch('agent.core.goals.LLMClient') as MockLLM:
            mock_instance = MagicMock()
            mock_instance.complete_str.return_value = "子目标1：测试 — 测试描述"
            MockLLM.return_value = mock_instance

            goal_system.decompose_goal("无客户端测试")

            MockLLM.assert_called_once()


class TestChildCompletion:
    """Tests for auto-completion when children are done."""

    def test_on_child_completed_all_done(self, goal_system):
        """Test parent auto-completes when all children are done."""
        goal_system.create_goal(title="父目标")
        goal_system.create_goal(title="子目标1")
        goal_system.create_goal(title="子目标2")

        goal_system.add_child("父目标", "子目标1")
        goal_system.add_child("父目标", "子目标2")

        goal_system.complete_goal("子目标1")
        goal_system.complete_goal("子目标2")

        result = goal_system.on_child_completed("父目标")

        assert result is True
        parent = goal_system.get_goal("父目标")
        assert parent.status == "completed"

    def test_on_child_completed_not_all_done(self, goal_system):
        """Test parent does not complete when some children are not done."""
        goal_system.create_goal(title="父目标")
        goal_system.create_goal(title="子目标1")
        goal_system.create_goal(title="子目标2")

        goal_system.add_child("父目标", "子目标1")
        goal_system.add_child("父目标", "子目标2")

        goal_system.complete_goal("子目标1")

        result = goal_system.on_child_completed("父目标")

        assert result is False
        parent = goal_system.get_goal("父目标")
        assert parent.status != "completed"

    def test_on_child_completed_no_children(self, goal_system):
        """Test no auto-completion for goal without children."""
        goal_system.create_goal(title="无子目标")

        result = goal_system.on_child_completed("无子目标")

        assert result is False
        goal = goal_system.get_goal("无子目标")
        assert goal.status != "completed"

    def test_on_child_completed_parent_not_found(self, goal_system):
        """Test no action for non-existent parent."""
        result = goal_system.on_child_completed("不存在")
        assert result is False

    def test_on_child_completed_one_child_failed(self, goal_system):
        """Test parent completes even if one child failed."""
        goal_system.create_goal(title="父目标")
        goal_system.create_goal(title="子目标1")
        goal_system.create_goal(title="子目标2")

        goal_system.add_child("父目标", "子目标1")
        goal_system.add_child("父目标", "子目标2")

        goal_system.complete_goal("子目标1")
        goal_system.fail_goal("子目标2", "资源不足")

        result = goal_system.on_child_completed("父目标")

        assert result is True
        parent = goal_system.get_goal("父目标")
        assert parent.status == "completed"

    def test_on_child_completed_logs_action(self, goal_system):
        """Test that auto-completion is logged."""
        goal_system.create_goal(title="自动完成测试")
        goal_system.create_goal(title="唯一子目标")

        goal_system.add_child("自动完成测试", "唯一子目标")
        goal_system.complete_goal("唯一子目标")

        goal_system.on_child_completed("自动完成测试")

        parent = goal_system.get_goal("自动完成测试")
        log_entries = [
            entry for entry in parent.execution_log
            if "自动完成" in entry or "已完成" in entry
        ]
        assert len(log_entries) > 0


class TestDecompositionIntegration:
    """Integration tests for decomposition workflow."""

    def test_full_decomposition_workflow(self, goal_system):
        """Test complete workflow: create -> decompose -> complete children -> auto-complete parent."""
        goal_system.create_goal(title="集成测试目标", description="完整流程测试")
        goal_system.update_status("集成测试目标", "accepted")

        mock_llm = MockLLMClient(
            response="""子目标1：第一步 — 完成第一个任务
子目标2：第二步 — 完成第二个任务
子目标3：第三步 — 完成第三个任务"""
        )

        sub_goals = goal_system.decompose_goal("集成测试目标", mock_llm)

        assert len(sub_goals) == 3

        for sub_goal in sub_goals:
            goal_system.complete_goal(sub_goal.title)

        result = goal_system.on_child_completed("集成测试目标")
        assert result is True

        parent = goal_system.get_goal("集成测试目标")
        assert parent.status == "completed"

        child_statuses = [goal_system.get_goal(g.title).status for g in sub_goals]
        assert all(status == "completed" for status in child_statuses)
