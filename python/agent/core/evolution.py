"""
Evolution System

Provides self-modification capabilities for the Agent based on review results.
Agents can modify their own processing parameters while protecting core identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Any


class ProtectedParameters:
    """
    Parameters that cannot be modified by the Agent.
    
    These are the core identity markers and founding seeds that define
    who the Agent is — they are protected from self-modification.
    """
    
    PROTECTED: set[str] = {
        "seed",
        "core_identity",
    }
    
    @classmethod
    def can_modify(cls, param: str) -> bool:
        """
        Check if a parameter can be modified.
        
        Args:
            param: The parameter name to check
            
        Returns:
            bool: True if the parameter is not protected
        """
        return param not in cls.PROTECTED


@dataclass
class ParameterModification:
    """
    Record of a single parameter modification.
    
    Attributes:
        modified_at: Timestamp of the modification
        parameter: The parameter that was modified
        old_value: The value before modification
        new_value: The new value after modification
        reason: Why the modification was made
        review_id: Optional ID of the review that triggered this modification
    """
    
    modified_at: str
    parameter: str
    old_value: Any
    new_value: Any
    reason: str
    review_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "modified_at": self.modified_at,
            "parameter": self.parameter,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "review_id": self.review_id,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> ParameterModification:
        """Create from dictionary."""
        return cls(
            modified_at=data["modified_at"],
            parameter=data["parameter"],
            old_value=data["old_value"],
            new_value=data["new_value"],
            reason=data["reason"],
            review_id=data.get("review_id"),
        )


class EvolutionSystem:
    """
    Manages Agent self-modification based on review results.
    
    The Agent can adjust its own processing parameters (like curiosity_level,
    fit_threshold, attention_window_size) based on periodic reviews, while
    core identity parameters remain protected.
    
    All modifications are:
    - Gradual (max ±20% per review)
    - Logged with reasoning
    - Reversible via rollback
    
    Usage:
        evolution = EvolutionSystem(state)
        modifications = evolution.apply_review_insights(review_data)
        evolution.modify_parameter("curiosity_level", 0.6, "Too high")
    """
    
    MAX_CHANGE_RATE: float = 0.20
    
    def __init__(self, state: "AgentState", memory_system: "MemorySystem", llm_client: "LLMClient", state_path: Optional[Path] = None):
        """
        Initialize the evolution system.
        
        Args:
            state: The Agent's state
            memory_system: The memory system
            llm_client: The LLM client
            state_path: Path to agent state file.
        """
        if state_path is None:
            from .vault import get_state_path
            state_path = get_state_path()
        
        self.state = state
        self.memory = memory_system
        self.llm = llm_client
        self._state_path = state_path
        self._history_path = state_path.parent / "parameter-history.json"
        self._modifications: list[ParameterModification] = []
        self._load_history()
        self._last_review_at: Optional[datetime] = None
    
    def take_snapshot(self) -> PersonalitySnapshot:
        """Take a snapshot of current personality state."""
        return PersonalitySnapshot(
            captured_at=datetime.now(),
            curiosity_level=self.state.curiosity_level,
            fit_threshold=self.state.fit_threshold,
            attention_window_size=self.state.attention_window_size,
            active_goals_count=len(self.state.goals) if hasattr(self.state, "goals") else 0,
            world_corpus_size=len(self.memory.read_all_fragments()) if self.memory else 0,
            processing_patterns=[],
            notes="",
        )
    
    def review(self) -> dict:
        """Perform a periodic personality review.
        
        Compare current snapshot to previous ones.
        Detect drift and growth.
        Update personality state.
        """
        from .memory import MemorySystem
        
        current = self.take_snapshot()
        current_dict = current.to_dict()
        
        # LLM-based review
        prompt = f"""你是无尽图书馆的居者。你正在回顾自己的变化。

【当前状态】
好奇心强度：{current.curiosity_level}
契合度阈值：{current.fit_threshold}
注意力窗口：{current.attention_window_size}
世界语料库大小：{current.world_corpus_size}

请回顾自己：你发生了什么变化？有什么是你之前不理解、现在理解了？

格式：
变化描述：2-3段反思
是否有漂移：是/否
漂移详情：说明
是否有成长：是/否
成长详情：说明
"""
        
        response = self.llm.complete_str(
            system="你是Agent的人格回顾助手。",
            user=prompt
        )
        
        review_result = {
            "snapshot": current_dict,
            "llm_review": response,
            "reviewed_at": datetime.now().isoformat(),
        }
        
        self._last_review_at = datetime.now()
        return review_result
    
    def detect_drift(self, old: PersonalitySnapshot, new: PersonalitySnapshot) -> dict:
        """Detect significant personality drift."""
        drift_detected = False
        details = []
        
        # Check curiosity drift
        if abs(new.curiosity_level - old.curiosity_level) > 0.3:
            drift_detected = True
            details.append(f"好奇心强度从{old.curiosity_level}变为{new.curiosity_level}")
        
        # Check fit threshold drift
        if abs(new.fit_threshold - old.fit_threshold) > 0.2:
            drift_detected = True
            details.append(f"契合度阈值从{old.fit_threshold}变为{new.fit_threshold}")
        
        return {"detected": drift_detected, "details": "; ".join(details) if details else "无明显漂移"}
    
    def detect_growth(self, old: PersonalitySnapshot, new: PersonalitySnapshot) -> dict:
        """Detect personality growth."""
        growth_detected = False
        details = []
        
        # More corpus = growth
        if new.world_corpus_size > old.world_corpus_size * 1.2:
            growth_detected = True
            details.append(f"世界语料库从{old.world_corpus_size}增加到{new.world_corpus_size}")
        
        return {"detected": growth_detected, "details": "; ".join(details) if details else "无明显成长"}
    
    def should_review(self) -> bool:
        """Check if it's time for a review.
        
        Review triggered by:
        - Time threshold (every 100 processing cycles)
        - Significant corpus growth
        - Manual trigger
        """
        if self._last_review_at is None:
            return True
        
        # Review every 100 cycles
        from .state import AgentState
        if hasattr(self.state, "total_cycles"):
            if self.state.total_cycles % 100 == 0:
                return True
        
        # Review if more than 7 days since last review
        elapsed = datetime.now() - self._last_review_at
        if elapsed.days >= 7:
            return True
        
        return False
    
    def _load_history(self) -> None:
        """Load modification history from file."""
        if self._history_path.exists():
            try:
                content = self._history_path.read_text(encoding="utf-8")
                data = json.loads(content)
                self._modifications = [
                    ParameterModification.from_dict(m) for m in data.get("modifications", [])
                ]
            except (json.JSONDecodeError, KeyError):
                self._modifications = []
        else:
            self._modifications = []
    
    def _save_history(self) -> None:
        """Save modification history to file."""
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_updated": datetime.now().isoformat(),
            "modifications": [m.to_dict() for m in self._modifications],
        }
        self._history_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def apply_review_insights(self, review: dict) -> list[str]:
        """
        Apply insights from a review to modify parameters.
        
        Args:
            review: Dictionary containing review insights with keys like:
                - curiosity_assessment: "too_high" | "too_low" | "balanced"
                - fit_threshold_assessment: "too_strict" | "too_lenient" | "balanced"
                - attention_assessment: "too_small" | "too_large" | "balanced"
                - overall_notes: str
                - review_id: Optional[str]
        
        Returns:
            list[str]: List of modified parameter names
        """
        from .state import AgentState
        
        state = AgentState.load(self._state_path)
        modified: list[str] = []
        review_id = review.get("review_id", datetime.now().strftime("%Y-%m-%d-review"))
        
        curiosity_assessment = review.get("curiosity_assessment", "balanced")
        if curiosity_assessment == "too_high":
            new_value = self._calculate_gradual_change(
                state.curiosity_level,
                state.curiosity_level * 0.85,
                "curiosity_level"
            )
            if self.modify_parameter("curiosity_level", new_value, 
                                     "Review showed curiosity too high", review_id):
                modified.append("curiosity_level")
        elif curiosity_assessment == "too_low":
            new_value = self._calculate_gradual_change(
                state.curiosity_level,
                state.curiosity_level * 1.15,
                "curiosity_level"
            )
            if self.modify_parameter("curiosity_level", new_value,
                                     "Review showed curiosity too low", review_id):
                modified.append("curiosity_level")
        
        fit_assessment = review.get("fit_threshold_assessment", "balanced")
        if fit_assessment == "too_strict":
            new_value = self._calculate_gradual_change(
                state.fit_threshold,
                state.fit_threshold * 1.15,
                "fit_threshold"
            )
            if self.modify_parameter("fit_threshold", new_value,
                                     "Review showed threshold too strict", review_id):
                modified.append("fit_threshold")
        elif fit_assessment == "too_lenient":
            new_value = self._calculate_gradual_change(
                state.fit_threshold,
                state.fit_threshold * 0.85,
                "fit_threshold"
            )
            if self.modify_parameter("fit_threshold", new_value,
                                     "Review showed threshold too lenient", review_id):
                modified.append("fit_threshold")
        
        attention_assessment = review.get("attention_assessment", "balanced")
        if attention_assessment == "too_small":
            new_value = self._calculate_gradual_change(
                float(state.attention_window_size),
                float(state.attention_window_size) * 1.20,
                "attention_window_size"
            )
            if self.modify_parameter("attention_window_size", int(new_value),
                                     "Review showed attention window too small", review_id):
                modified.append("attention_window_size")
        elif attention_assessment == "too_large":
            new_value = self._calculate_gradual_change(
                float(state.attention_window_size),
                float(state.attention_window_size) * 0.80,
                "attention_window_size"
            )
            if self.modify_parameter("attention_window_size", int(new_value),
                                     "Review showed attention window too large", review_id):
                modified.append("attention_window_size")
        
        return modified
    
    def _calculate_gradual_change(
        self,
        current_value: float,
        target_value: float,
        param_name: str
    ) -> float:
        """
        Calculate a gradual change that respects the max change rate.
        
        Args:
            current_value: Current parameter value
            target_value: Desired new value
            param_name: Parameter name for validation
            
        Returns:
            float: The new value, clamped to max change rate
        """
        if current_value == 0:
            return target_value
        
        change_ratio = target_value / current_value
        
        if change_ratio > (1 + self.MAX_CHANGE_RATE):
            change_ratio = 1 + self.MAX_CHANGE_RATE
        elif change_ratio < (1 - self.MAX_CHANGE_RATE):
            change_ratio = 1 - self.MAX_CHANGE_RATE
        
        new_value = current_value * change_ratio
        
        if param_name == "curiosity_level" or param_name == "fit_threshold":
            new_value = max(0.0, min(1.0, new_value))
        elif param_name == "attention_window_size":
            new_value = max(1, min(20, round(new_value)))
        
        return new_value
    
    def modify_parameter(
        self,
        name: str,
        value: Any,
        reason: str,
        review_id: Optional[str] = None
    ) -> bool:
        """
        Modify a single parameter.
        
        Protected parameters cannot be modified. All modifications are logged
        with reasoning and timestamp.
        
        Args:
            name: Parameter name to modify
            value: New value for the parameter
            reason: Why this modification is being made
            review_id: Optional ID of the review that triggered this
            
        Returns:
            bool: True if modification was successful, False if blocked
        """
        if not ProtectedParameters.can_modify(name):
            return False
        
        from .state import AgentState
        
        state = AgentState.load(self._state_path)
        
        if not hasattr(state, name):
            return False
        
        old_value = getattr(state, name)
        
        modification = ParameterModification(
            modified_at=datetime.now().isoformat(),
            parameter=name,
            old_value=old_value,
            new_value=value,
            reason=reason,
            review_id=review_id,
        )
        self._modifications.append(modification)
        self._save_history()
        
        state.update(**{name: value})
        state.save(self._state_path)
        
        return True
    
    def get_modification_history(self) -> list[dict]:
        """Get history of parameter modifications."""
        return [m.to_dict() for m in self._modifications]
    
    def rollback_parameter(self, name: str) -> bool:
        """
        Rollback a parameter to its previous value.
        
        Finds the most recent modification of the given parameter and
        reverts it.
        
        Args:
            name: Parameter name to rollback
            
        Returns:
            bool: True if rollback was successful, False if no history found
        """
        for mod in reversed(self._modifications):
            if mod.parameter == name:
                from .state import AgentState
                
                state = AgentState.load(self._state_path)
                current_value = getattr(state, name, None)
                
                if current_value != mod.old_value:
                    state.update(**{name: mod.old_value})
                    state.save(self._state_path)
                    
                    rollback_mod = ParameterModification(
                        modified_at=datetime.now().isoformat(),
                        parameter=name,
                        old_value=current_value,
                        new_value=mod.old_value,
                        reason=f"Rollback of modification from {mod.modified_at}",
                    )
                    self._modifications.append(rollback_mod)
                    self._save_history()
                    
                    return True
                
                return True
        
        return False
    
    def get_current_value(self, name: str) -> Any:
        """
        Get the current value of a parameter.
        
        Args:
            name: Parameter name
            
        Returns:
            The current value, or None if parameter doesn't exist
        """
        from .state import AgentState
        
        try:
            state = AgentState.load(self._state_path)
            return getattr(state, name, None)
        except FileNotFoundError:
            return None
    
    def get_recent_modifications(self, limit: int = 10) -> list[dict]:
        """
        Get the most recent parameter modifications.
        
        Args:
            limit: Maximum number of modifications to return
            
        Returns:
            list[dict]: Most recent modifications as dictionaries
        """
        history = self.get_modification_history()
        return history[-limit:] if len(history) > limit else history
    
    def suggest_modifications(self, review: dict) -> list[dict]:
        """
        Suggest what parameters should be modified based on review.
        
        Unlike apply_review_insights, this only suggests changes without
        applying them. Useful for previewing before committing.
        
        Args:
            review: Review dictionary (same format as apply_review_insights)
            
        Returns:
            list[dict]: Suggested modifications with parameter, current, and suggested values
        """
        from .state import AgentState
        
        suggestions = []
        
        try:
            state = AgentState.load(self._state_path)
        except FileNotFoundError:
            return suggestions
        
        curiosity_assessment = review.get("curiosity_assessment", "balanced")
        if curiosity_assessment in ("too_high", "too_low"):
            direction = -1 if curiosity_assessment == "too_high" else 1
            target = state.curiosity_level * (1 + direction * 0.15)
            suggested = self._calculate_gradual_change(
                state.curiosity_level, target, "curiosity_level"
            )
            suggestions.append({
                "parameter": "curiosity_level",
                "current": state.curiosity_level,
                "suggested": suggested,
                "direction": "decrease" if direction < 0 else "increase",
                "reason": f"Review assessment: curiosity {curiosity_assessment}",
            })
        
        fit_assessment = review.get("fit_threshold_assessment", "balanced")
        if fit_assessment in ("too_strict", "too_lenient"):
            direction = 1 if fit_assessment == "too_strict" else -1
            target = state.fit_threshold * (1 + direction * 0.15)
            suggested = self._calculate_gradual_change(
                state.fit_threshold, target, "fit_threshold"
            )
            suggestions.append({
                "parameter": "fit_threshold",
                "current": state.fit_threshold,
                "suggested": suggested,
                "direction": "increase" if direction > 0 else "decrease",
                "reason": f"Review assessment: fit_threshold {fit_assessment}",
            })
        
        attention_assessment = review.get("attention_assessment", "balanced")
        if attention_assessment in ("too_small", "too_large"):
            direction = 1 if attention_assessment == "too_small" else -1
            target = float(state.attention_window_size) * (1 + direction * 0.20)
            suggested = self._calculate_gradual_change(
                float(state.attention_window_size), target, "attention_window_size"
            )
            suggestions.append({
                "parameter": "attention_window_size",
                "current": state.attention_window_size,
                "suggested": int(suggested),
                "direction": "expand" if direction > 0 else "contract",
                "reason": f"Review assessment: attention_window {attention_assessment}",
            })
        
        return suggestions


@dataclass
class PersonalitySnapshot:
    """Snapshot of personality state at a point in time."""
    captured_at: datetime
    curiosity_level: float
    fit_threshold: float
    attention_window_size: int
    active_goals_count: int
    world_corpus_size: int
    processing_patterns: list
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "captured_at": self.captured_at.isoformat(),
            "curiosity_level": self.curiosity_level,
            "fit_threshold": self.fit_threshold,
            "attention_window_size": self.attention_window_size,
            "active_goals_count": self.active_goals_count,
            "world_corpus_size": self.world_corpus_size,
            "processing_patterns": self.processing_patterns,
            "notes": self.notes,
        }


__all__ = [
    "EvolutionSystem",
    "ProtectedParameters",
    "ParameterModification",
    "PersonalitySnapshot",
]
