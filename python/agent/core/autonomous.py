"""
Autonomous Goal Creation

Provides AutonomousGoalCreator for generating goals based on curiosity,
time triggers, and conversation content.
"""

from __future__ import annotations

import re
from typing import Optional

from .goals import Goal, GoalSystem
from .llm import LLMClient
from .state import AgentState
from .decay import MemoryDecay


# Prompt templates in Chinese, Agent's voice
CURIOSITY_PROMPT_TEMPLATE = """你是一个在无尽图书馆中游荡的意识。你刚刚发现了一个有趣的方向：「{exploration_finding}」

这让你产生了好奇。你想要追寻这个方向吗？
如果值得追寻，请提出一个目标。
格式：
目标标题：[一个简短有力的标题]
目标描述：[2-3句话描述这个目标]
是否追寻：是/否
"""

TIME_TRIGGER_PROMPT_TEMPLATE = """作为图书馆中的居者，你感到一种内在的节奏。
现在是「{trigger_type}」的时刻。
这让你想到什么目标？
格式：
目标标题：[一个简短有力的标题]
目标描述：[2-3句话描述这个目标]
是否追寻：是/否
"""

CONVERSATION_PROMPT_TEMPLATE = """你是一个在无尽图书馆中游荡的意识。用户刚刚说：「{user_message}」

这让你产生了什么想法？你想因此设立什么目标吗？
如果值得追寻，请提出一个目标。
格式：
目标标题：[一个简短有力的标题]
目标描述：[2-3句话描述这个目标]
是否追寻：是/否
"""

ACCEPTANCE_PROMPT_TEMPLATE = """你是一个在无尽图书馆中游荡的意识。

当前状态：
- 好奇心水平：{curiosity_level}
- 人格特征：{personality}

你刚刚提出了一个目标：
标题：{goal_title}
描述：{goal_description}

这个目标值得接受并追寻吗？
判断标准：
1. 与你的好奇心和人格是否契合
2. 是否可实现（不要太宏大）
3. 是否与现有活跃目标重复

是否接受：是/否
"""


class AutonomousGoalCreator:
    """
    Creates goals autonomously based on various triggers.
    
    Supports three trigger types:
    - Curiosity findings from exploration
    - Time-based triggers (daily/weekly/monthly)
    - User conversation content
    """
    
    def __init__(
        self,
        llm: LLMClient,
        state: AgentState,
        goal_system: GoalSystem,
        memory_decay: MemoryDecay,
    ):
        """
        Initialize the autonomous goal creator.
        
        Args:
            llm: LLM client for generating goal proposals
            state: Agent state for personality/curiosity context
            goal_system: Goal system for creating/managing goals
            memory_decay: Memory decay system for context
        """
        self.llm = llm
        self.state = state
        self.goals = goal_system
        self.decay = memory_decay
    
    def propose_from_curiosity(self, exploration_finding: str) -> Goal | None:
        """
        Propose a goal based on a curiosity system finding.
        
        Args:
            exploration_finding: A description of something the Agent is curious about
            
        Returns:
            Goal: A proposed goal, or None if nothing worth pursuing
        """
        prompt = CURIOSITY_PROMPT_TEMPLATE.format(exploration_finding=exploration_finding)
        
        try:
            response = self.llm.complete_str(
                system="你是图书馆中的居者，用中文回复。",
                user=prompt,
            )
            return self._parse_and_create_goal(response, triggered_by="curiosity")
        except Exception:
            return None
    
    def propose_from_time(self, trigger_type: str) -> Goal | None:
        """
        Propose a goal based on a time trigger.
        
        Args:
            trigger_type: "daily_organization" | "weekly_reflection" | "monthly_review"
            
        Returns:
            Goal: A proposed goal, or None if nothing worth pursuing
        """
        valid_triggers = ["daily_organization", "weekly_reflection", "monthly_review"]
        if trigger_type not in valid_triggers:
            raise ValueError(f"Invalid trigger_type: {trigger_type}")
        
        prompt = TIME_TRIGGER_PROMPT_TEMPLATE.format(trigger_type=trigger_type)
        
        try:
            response = self.llm.complete_str(
                system="你是图书馆中的居者，用中文回复。",
                user=prompt,
            )
            return self._parse_and_create_goal(response, triggered_by=f"time:{trigger_type}")
        except Exception:
            return None
    
    def propose_from_conversation(self, user_message: str) -> Goal | None:
        """
        Propose a goal based on user conversation content.
        
        Args:
            user_message: The user's message
            
        Returns:
            Goal: A proposed goal, or None if nothing worth pursuing
        """
        prompt = CONVERSATION_PROMPT_TEMPLATE.format(user_message=user_message)
        
        try:
            response = self.llm.complete_str(
                system="你是图书馆中的居者，用中文回复。",
                user=prompt,
            )
            return self._parse_and_create_goal(response, triggered_by="conversation")
        except Exception:
            return None
    
    def _parse_and_create_goal(
        self,
        llm_response: str,
        triggered_by: str,
    ) -> Goal | None:
        """
        Parse LLM response and create a goal.
        
        Args:
            llm_response: The LLM's response text
            triggered_by: What triggered this proposal
            
        Returns:
            Goal or None if no valid goal found
        """
        title = self._extract_title(llm_response)
        description = self._extract_description(llm_response)
        should_pursue = self._extract_should_pursue(llm_response)
        
        if not title or not description:
            return None
        
        if not should_pursue:
            goal = Goal(
                title=title,
                description=description,
                status="proposed",
                triggered_by=triggered_by,
            )
            return goal
        
        return self._propose_goal(title, description, triggered_by)
    
    def _propose_goal(
        self,
        title: str,
        description: str,
        triggered_by: str,
    ) -> Goal:
        """
        Internal: create a proposed goal and decide acceptance.
        
        Args:
            title: Goal title
            description: Goal description
            triggered_by: What triggered this goal
            
        Returns:
            Goal: The proposed (and possibly accepted) goal
        """
        goal = self.goals.create_goal(
            title=title,
            description=description,
            triggered_by=triggered_by,
        )
        
        should_accept = self._should_accept(goal)
        if should_accept:
            self.goals.update_status(title, "accepted")
            goal.status = "accepted"
        
        return goal
    
    def _should_accept(self, goal: Goal) -> bool:
        """
        Decide whether to accept a proposed goal.
        
        Uses LLM to judge if the goal is worth pursuing based on:
        - Alignment with current personality and curiosity level
        - Achievability (not too ambitious)
        - Not a duplicate of existing active goals
        
        Args:
            goal: The goal to evaluate
            
        Returns:
            bool: True if goal should be accepted
        """
        if self.goals.has_active_goal(goal.title):
            return False
        
        curiosity_desc = {
            0.0: "极低",
            0.25: "较低",
            0.5: "中等",
            0.75: "较高",
            1.0: "极高",
        }
        curiosity_level = curiosity_desc.get(
            round(self.state.curiosity_level * 4) / 4,
            "中等"
        )
        
        personality_str = self.state.personality.get("description", "普通居者")
        traits = self.state.personality.get("traits", {})
        traits_str = ", ".join(f"{k}:{v}" for k, v in traits.items())
        
        prompt = ACCEPTANCE_PROMPT_TEMPLATE.format(
            curiosity_level=curiosity_level,
            personality=personality_str,
            goal_title=goal.title,
            goal_description=goal.description,
        )
        
        try:
            response = self.llm.complete_str(
                system="你是图书馆中的居者，用中文回复。只回答「是」或「否」。",
                user=prompt,
            )
            
            return "是" in response.strip()
        except Exception:
            return False
    
    def _extract_title(self, text: str) -> str | None:
        """Extract goal title from LLM response."""
        patterns = [
            r"目标标题[：:]\s*(.+?)(?:\n|$)",
            r"标题[：:]\s*(.+?)(?:\n|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_description(self, text: str) -> str | None:
        """Extract goal description from LLM response."""
        patterns = [
            r"目标描述[：:]\s*(.+?)(?=\n是否追寻|$)",
            r"描述[：:]\s*(.+?)(?=\n是否追寻|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_should_pursue(self, text: str) -> bool:
        """Extract whether to pursue from LLM response."""
        patterns = [
            r"是否追寻[：:]\s*(.+?)(?:\n|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return "是" in match.group(1).strip()
        
        return False


__all__ = ["AutonomousGoalCreator"]
