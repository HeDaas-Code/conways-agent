"""
Goal System

Manages Agent goals as Obsidian markdown files with YAML frontmatter.
Goals are stored in the vault's `agent/goals/` directory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

GoalStatus = Literal["proposed", "accepted", "planned", "in_progress", "completed", "failed"]


@dataclass
class Goal:
    """An Agent goal stored as an Obsidian file."""
    title: str
    status: GoalStatus
    created: datetime
    updated: datetime
    description: str = ""
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    execution_log: list[str] = field(default_factory=list)
    curiosity_triggered: bool = False
    file_path: Path | None = None


class GoalSystem:
    """Manages Agent goals as Obsidian files in agent/goals/."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.goals_dir = vault_path / "agent" / "goals"
        self.goals_dir.mkdir(parents=True, exist_ok=True)

    def _goal_file(self, title: str) -> Path:
        """Get the file path for a goal."""
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        return self.goals_dir / f"{safe_title}.md"

    def _timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _log_timestamp(self) -> str:
        """Get current timestamp for execution log entries."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def create_goal(
        self,
        title: str,
        description: str = "",
        parent: str | None = None,
        triggered_by: str = "manual"
    ) -> Goal:
        """Create a new goal file with YAML frontmatter."""
        now = datetime.now()
        goal = Goal(
            title=title,
            status="proposed",
            created=now,
            updated=now,
            description=description,
            parent=parent,
            children=[],
            execution_log=[f"{self._log_timestamp()} — 目标被创建（触发来源：{triggered_by}）"],
            curiosity_triggered=triggered_by == "curiosity",
            file_path=None
        )

        file_path = self._goal_file(title)
        counter = 1
        while file_path.exists():
            file_path = self.goals_dir / f"{self._safe_filename(title)}_{counter}.md"
            counter += 1

        goal.file_path = file_path
        self._write_goal_file(goal)

        if parent:
            self.add_child(parent, title)

        return goal

    def get_goal(self, title: str) -> Goal | None:
        """Get a goal by title."""
        file_path = self._goal_file(title)

        if not file_path.exists():
            for md_file in self.goals_dir.glob("*.md"):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    goal = self._parse_goal_file(content, md_file)
                    if goal.title == title:
                        return goal
                except Exception:
                    continue
            return None

        content = file_path.read_text(encoding="utf-8")
        return self._parse_goal_file(content, file_path)

    def get_all_goals(self) -> list[Goal]:
        """Get all goals from agent/goals/."""
        goals = []

        for md_file in sorted(self.goals_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                goal = self._parse_goal_file(content, md_file)
                goals.append(goal)
            except Exception:
                continue

        goals.sort(key=lambda g: g.created)
        return goals

    def get_goals_by_status(self, status: GoalStatus) -> list[Goal]:
        """Get goals filtered by status."""
        all_goals = self.get_all_goals()
        return [g for g in all_goals if g.status == status]

    def update_goal(self, goal: Goal) -> None:
        """Update a goal file."""
        goal.updated = datetime.now()
        self._write_goal_file(goal)

    def update_status(self, title: str, new_status: GoalStatus) -> None:
        """Update goal status."""
        goal = self.get_goal(title)
        if goal:
            goal.status = new_status
            goal.updated = datetime.now()
            self._write_goal_file(goal)

    def add_execution_log(self, title: str, entry: str) -> None:
        """Add an entry to the goal's execution log."""
        goal = self.get_goal(title)
        if goal:
            log_entry = f"{self._log_timestamp()} — {entry}"
            goal.execution_log.append(log_entry)
            goal.updated = datetime.now()
            self._write_goal_file(goal)

    def complete_goal(self, title: str) -> None:
        """Mark goal as completed."""
        goal = self.get_goal(title)
        if goal:
            goal.status = "completed"
            goal.execution_log.append(f"{self._log_timestamp()} — 目标已完成")
            goal.updated = datetime.now()
            self._write_goal_file(goal)

    def fail_goal(self, title: str, reason: str = "") -> None:
        """Mark goal as failed."""
        goal = self.get_goal(title)
        if goal:
            goal.status = "failed"
            if reason:
                goal.execution_log.append(f"{self._log_timestamp()} — 目标失败：{reason}")
            else:
                goal.execution_log.append(f"{self._log_timestamp()} — 目标失败")
            goal.updated = datetime.now()
            self._write_goal_file(goal)

    def add_child(self, parent_title: str, child_title: str) -> None:
        """Add a child goal to a parent goal."""
        parent = self.get_goal(parent_title)
        if parent:
            if child_title not in parent.children:
                parent.children.append(child_title)
                parent.updated = datetime.now()
                self._write_goal_file(parent)

    def get_active_goals(self) -> list[Goal]:
        """Get all active goals (accepted, planned, in_progress)."""
        active_statuses: list[GoalStatus] = ["accepted", "planned", "in_progress"]
        all_goals = self.get_all_goals()
        return [g for g in all_goals if g.status in active_statuses]

    def decompose_goal(self, parent_title: str, llm_client=None) -> list[Goal]:
        """Decompose a goal into sub-goals using LLM.

        1. Read the parent goal
        2. Ask LLM to propose sub-goals
        3. Create each sub-goal as a child of the parent
        4. Return the list of created sub-goals
        """
        parent = self.get_goal(parent_title)
        if not parent:
            return []

        goal_title = parent.title
        goal_description = parent.description or "无详细描述"

        prompt = f"""你是一个在无尽图书馆中思考的存在。你面前有一个目标：

「{goal_title}」
{goal_description}

将这个目标分解为 3-5 个具体的子目标。每个子目标应该：
- 是一个独立的、可执行的步骤
- 有明确的完成标准
- 按照逻辑顺序排列

格式：
子目标1：标题 — 一句话描述
子目标2：标题 — 一句话描述
..."""

        if llm_client is None:
            llm_client = LLMClient()

        response = llm_client.complete_str(
            system="你是一个目标分解专家，帮助将复杂目标分解为可执行的子目标。",
            user=prompt
        )

        sub_goals = self._parse_sub_goals(response)
        created_goals = []

        for sub_title, sub_description in sub_goals:
            sub_goal = self.create_goal(
                title=sub_title,
                description=sub_description,
                parent=parent_title,
                triggered_by="decomposition"
            )
            self.update_status(sub_title, "planned")
            created_goals.append(sub_goal)

        self.add_execution_log(
            parent_title,
            f"目标已分解为 {len(created_goals)} 个子目标"
        )

        return created_goals

    def _parse_sub_goals(self, llm_response: str) -> list[tuple[str, str]]:
        """Parse LLM response into sub-goal (title, description) tuples."""
        sub_goals = []
        lines = llm_response.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            prefixes_to_try = ['子目标1', '子目标2', '子目标3', '子目标4', '子目标5',
                               '1.', '2.', '3.', '4.', '5.', '- ', '* ']
            for prefix in prefixes_to_try:
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
                    break

            if '：' in line or ':' in line:
                delimiter = '：' if '：' in line else ':'
                parts = line.split(delimiter, 1)
                title = parts[0].strip()
                description = parts[1].strip() if len(parts) > 1 else ""

                title = title.lstrip('0123456789.、) ')
                description = description.lstrip('—\-–: ')
                description = description.rstrip('。.')

                if title:
                    sub_goals.append((title, description))

        return sub_goals

    def on_child_completed(self, parent_title: str) -> bool:
        """Check if all children are done, if so complete the parent.

        Returns:
            True if parent was auto-completed, False otherwise
        """
        parent = self.get_goal(parent_title)
        if not parent:
            return False

        if not parent.children:
            return False

        all_completed = True
        for child_title in parent.children:
            child = self.get_goal(child_title)
            if child is None:
                all_completed = False
                break
            if child.status not in ("completed", "failed"):
                all_completed = False
                break

        if all_completed:
            self.complete_goal(parent_title)
            self.add_execution_log(
                parent_title,
                "所有子目标已完成，父目标自动完成"
            )
            return True

        return False

    def has_active_goal(self, title: str) -> bool:
        """Check if a goal with similar title exists and is active."""
        active_statuses: list[GoalStatus] = ["proposed", "accepted", "planned", "in_progress"]
        all_goals = self.get_all_goals()
        for goal in all_goals:
            if goal.title == title and goal.status in active_statuses:
                return True
        return False

    def _safe_filename(self, title: str) -> str:
        """Convert a title to a safe filename."""
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
        return safe_title or "untitled"

    def _write_goal_file(self, goal: Goal) -> None:
        """Write a goal to an Obsidian markdown file."""
        if goal.file_path is None:
            goal.file_path = self._goal_file(goal.title)

        children_links = ""
        if goal.children:
            children_links = "\n\n*被以下目标引用：*\n" + "\n".join(f"- [[{child}]]" for child in goal.children)

        content = f"""---
title: {goal.title}
status: {goal.status}
created: {goal.created.strftime("%Y-%m-%dT%H:%M:%S")}
updated: {goal.updated.strftime("%Y-%m-%dT%H:%M:%S")}
parent: {goal.parent if goal.parent else "null"}
children:
{self._format_list(goal.children)}
execution_log:
{self._format_list(goal.execution_log)}
curiosity_triggered: {str(goal.curiosity_triggered).lower()}
---

# {goal.title}

{goal.description}

---

*执行日志：*
{chr(10).join(f"- {log}" for log in goal.execution_log)}{children_links}
"""
        goal.file_path.write_text(content, encoding="utf-8")

    def _format_list(self, items: list[str]) -> str:
        """Format a list for YAML frontmatter."""
        if not items:
            return "  []"
        return "\n".join(f'  - "{item}"' for item in items if item and item != "[]")

    def _parse_goal_file(self, content: str, path: Path) -> Goal:
        """Parse an Obsidian markdown goal file."""
        if not content.startswith('---'):
            raise ValueError(f"Invalid goal format: missing YAML frontmatter in {path}")

        parts = content.split('---', 2)
        if len(parts) < 3:
            raise ValueError(f"Invalid goal format: malformed YAML frontmatter in {path}")

        frontmatter_str = parts[1]
        body = parts[2].strip()

        frontmatter = self._parse_frontmatter(frontmatter_str)

        title = frontmatter.get("title", path.stem)

        status = frontmatter.get("status", "proposed")
        if status not in ["proposed", "accepted", "planned", "in_progress", "completed", "failed"]:
            status = "proposed"

        created_str = frontmatter.get("created")
        if created_str:
            try:
                created = datetime.fromisoformat(created_str)
            except ValueError:
                created = datetime.now()
        else:
            created = datetime.now()

        updated_str = frontmatter.get("updated")
        if updated_str:
            try:
                updated = datetime.fromisoformat(updated_str)
            except ValueError:
                updated = datetime.now()
        else:
            updated = datetime.now()

        parent = frontmatter.get("parent")
        if parent == "null" or parent is None:
            parent = None

        children = frontmatter.get("children", [])
        if isinstance(children, str) and children.startswith("["):
            children = self._parse_list_value(children)

        execution_log = frontmatter.get("execution_log", [])
        if isinstance(execution_log, str) and execution_log.startswith("["):
            execution_log = self._parse_list_value(execution_log)

        curiosity_triggered = frontmatter.get("curiosity_triggered", "false")
        if isinstance(curiosity_triggered, str):
            curiosity_triggered = curiosity_triggered.lower() in ("true", "yes", "1")

        description = self._extract_description(body)

        return Goal(
            title=title,
            status=status,
            created=created,
            updated=updated,
            description=description,
            parent=parent,
            children=children,
            execution_log=execution_log,
            curiosity_triggered=curiosity_triggered,
            file_path=path
        )

    def _parse_frontmatter(self, frontmatter_str: str) -> dict:
        """Parse YAML frontmatter into a dictionary."""
        result = {}
        lines = frontmatter_str.strip().split('\n')
        current_key = None
        current_list: list[str] = []
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            if stripped.startswith('- "'):
                list_item = stripped[2:].strip().strip('"')
                list_item = list_item.rstrip('"').rstrip(',').strip()
                if list_item and list_item != "[]":
                    current_list.append(list_item)
            elif ':' in stripped and not stripped.startswith('#'):
                if current_key is not None:
                    if current_list:
                        result[current_key] = current_list
                    else:
                        result[current_key] = []
                    current_list = []

                key, value = stripped.split(':', 1)
                key = key.strip()
                value = value.strip().rstrip(',')

                if value == "" or value == "[]":
                    current_key = key
                    current_list = []
                elif value.startswith('['):
                    current_key = key
                    current_list = self._parse_list_value(value)
                else:
                    result[key] = value
                    current_key = None
            else:
                if stripped.startswith('-'):
                    list_item = stripped.lstrip('-').strip().strip('"')
                    list_item = list_item.rstrip('"').rstrip(',').strip()
                    if list_item and list_item != "[]":
                        current_list.append(list_item)
                elif current_key:
                    current_list.append(stripped.strip('"').rstrip('"'))

            i += 1

        if current_key is not None:
            if current_list:
                result[current_key] = current_list
            else:
                result[current_key] = []

        return result

    def _parse_list_value(self, value: str) -> list[str]:
        """Parse a YAML list value."""
        value = value.strip('[]')
        if not value.strip():
            return []

        items = []
        for item in value.split(','):
            item = item.strip().strip('"').rstrip('"').rstrip(',')
            if item and item != "[]":
                items.append(item)
        return items

    def _extract_description(self, body: str) -> str:
        """Extract the description from the goal body."""
        body = body.strip()
        
        lines = body.split('\n')
        description_lines = []
        started = False

        for line in lines:
            stripped = line.strip()
            
            if not started:
                if stripped.startswith('#'):
                    continue
                if stripped and not stripped.startswith('*') and not stripped.startswith('-'):
                    started = True
                    description_lines.append(stripped)
            else:
                if not stripped:
                    continue
                if stripped.startswith('*') or stripped.startswith('- ['):
                    break
                if stripped.startswith('---'):
                    break
                if '—' in stripped and not stripped.startswith('#'):
                    break
                if stripped.startswith('*执行日志'):
                    break
                description_lines.append(stripped)

        return '\n'.join(description_lines).strip()


__all__ = ["Goal", "GoalSystem", "GoalStatus"]
