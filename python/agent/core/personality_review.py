"""
Personality Review System

Monitors and evolves the Agent's personality over time through periodic reviews,
detecting drift and growth in processing patterns and parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .state import AgentState
from .llm import LLMClient
from .memory import MemorySystem
from .vault import get_vault_path


@dataclass
class PersonalitySnapshot:
    """A snapshot of the Agent's personality at a point in time."""
    captured_at: datetime
    curiosity_level: float
    fit_threshold: float
    attention_window_size: int
    active_goals_count: int
    world_corpus_size: int
    processing_patterns: list[str]
    notes: str = ""

    def to_dict(self) -> dict:
        """Convert snapshot to dictionary for serialization."""
        data = asdict(self)
        data["captured_at"] = self.captured_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> PersonalitySnapshot:
        """Create snapshot from dictionary."""
        if isinstance(data["captured_at"], str):
            data["captured_at"] = datetime.fromisoformat(data["captured_at"])
        return cls(**data)

    def to_markdown(self) -> str:
        """Convert snapshot to markdown format for storage."""
        patterns_str = ", ".join(self.processing_patterns) if self.processing_patterns else "无"
        return f"""---
snapshot_at: {self.captured_at.isoformat()}
curiosity_level: {self.curiosity_level}
fit_threshold: {self.fit_threshold}
attention_window_size: {self.attention_window_size}
active_goals: {self.active_goals_count}
world_corpus_size: {self.world_corpus_size}
processing_patterns: {patterns_str}
---

# 人格快照 {self.captured_at.strftime('%Y-%m-%d')}

处理模式：{patterns_str}

{("# 状态参数\n- 好奇心强度：" + str(self.curiosity_level) + "\n- 契合度阈值：" + str(self.fit_threshold) + "\n- 注意力窗口：" + str(self.attention_window_size) + "\n- 活跃目标数：" + str(self.active_goals_count) + "\n- 世界语料库大小：" + str(self.world_corpus_size)) if not self.notes else ("\n## 备注\n" + self.notes)}"""


class EvolutionSystem:
    """Monitors and evolves the Agent's personality over time."""

    # Review triggers
    DEFAULT_CYCLES_THRESHOLD = 100
    DEFAULT_CORPUS_GROWTH_THRESHOLD = 5

    def __init__(
        self,
        state: AgentState,
        memory: MemorySystem,
        llm: LLMClient,
        history_dir: Optional[Path] = None,
        cycles_threshold: int = DEFAULT_CYCLES_THRESHOLD,
        corpus_growth_threshold: int = DEFAULT_CORPUS_GROWTH_THRESHOLD,
    ):
        """
        Initialize the evolution system.

        Args:
            state: Agent state
            memory: Memory system
            llm: LLM client for reflection
            history_dir: Directory for snapshot storage (defaults to agent/personality-history/)
            cycles_threshold: Number of cycles between reviews
            corpus_growth_threshold: Number of new fragments to trigger review
        """
        self.state = state
        self.memory = memory
        self.llm = llm
        self.cycles_threshold = cycles_threshold
        self.corpus_growth_threshold = corpus_growth_threshold

        if history_dir is None:
            vault_path = get_vault_path()
            self._history_dir = vault_path / "agent" / "personality-history"
        else:
            self._history_dir = history_dir

        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._last_corpus_size = self._get_corpus_size()
        self._last_review_cycles = state.total_cycles

    def _get_corpus_size(self) -> int:
        """Get current world corpus size."""
        return len(self.memory.read_all_fragments())

    def _get_active_goals_count(self) -> int:
        """Get count of active goals from state."""
        return self.state.total_cycles

    def _detect_processing_patterns(self) -> list[str]:
        """Analyze memory system to detect processing patterns."""
        patterns = []
        fragments = self.memory.read_all_fragments()

        if not fragments:
            return patterns

        fit_path_counts: dict[str, int] = {}
        for fragment in fragments:
            fit_path = getattr(fragment, 'fit_path', 'translation')
            fit_path_counts[fit_path] = fit_path_counts.get(fit_path, 0) + 1

        if fit_path_counts:
            dominant = max(fit_path_counts.items(), key=lambda x: x[1])
            if dominant[1] > 0:
                if dominant[0] == "collision":
                    patterns.append("favors collision")
                elif dominant[0] == "translation":
                    patterns.append("prefers translation")
                elif dominant[0] == "resolution":
                    patterns.append("focuses on resolution")

        if len(fit_path_counts) >= 2:
            total = sum(fit_path_counts.values())
            ratios = [count / total for count in fit_path_counts.values()]
            if all(0.2 <= r <= 0.5 for r in ratios):
                patterns.append("balanced approach")

        return patterns

    def take_snapshot(self) -> PersonalitySnapshot:
        """Take a snapshot of current personality state."""
        snapshot = PersonalitySnapshot(
            captured_at=datetime.now(),
            curiosity_level=self.state.curiosity_level,
            fit_threshold=self.state.fit_threshold,
            attention_window_size=self.state.attention_window_size,
            active_goals_count=self._get_active_goals_count(),
            world_corpus_size=self._get_corpus_size(),
            processing_patterns=self._detect_processing_patterns(),
        )
        return snapshot

    def save_snapshot(self, snapshot: PersonalitySnapshot) -> Path:
        """
        Save a snapshot to the history directory.

        Args:
            snapshot: The snapshot to save

        Returns:
            Path: Path to the saved snapshot file
        """
        filename = f"snapshot-{snapshot.captured_at.strftime('%Y%m%d-%H%M%S-%f')}.md"
        file_path = self._history_dir / filename
        file_path.write_text(snapshot.to_markdown(), encoding="utf-8")
        return file_path

    def load_snapshots(self) -> list[PersonalitySnapshot]:
        """
        Load all snapshots from the history directory.

        Returns:
            list[PersonalitySnapshot]: List of snapshots sorted by capture time
        """
        snapshots = []

        for md_file in sorted(self._history_dir.glob("snapshot-*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                snapshot = self._parse_snapshot_file(content)
                snapshots.append(snapshot)
            except Exception:
                continue

        snapshots.sort(key=lambda s: s.captured_at)
        return snapshots

    def _parse_snapshot_file(self, content: str) -> PersonalitySnapshot:
        """Parse a snapshot markdown file."""
        import re

        frontmatter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            raise ValueError("Invalid snapshot format: missing frontmatter")

        frontmatter: dict = {}
        for line in frontmatter_match.group(1).split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip()

        patterns_str = frontmatter.get('processing_patterns', '')
        patterns = [p.strip() for p in patterns_str.split(',') if p.strip()] if patterns_str else []

        return PersonalitySnapshot(
            captured_at=datetime.fromisoformat(frontmatter['snapshot_at']),
            curiosity_level=float(frontmatter['curiosity_level']),
            fit_threshold=float(frontmatter['fit_threshold']),
            attention_window_size=int(frontmatter['attention_window_size']),
            active_goals_count=int(frontmatter['active_goals']),
            world_corpus_size=int(frontmatter['world_corpus_size']),
            processing_patterns=patterns,
        )

    def _get_previous_snapshot(self) -> Optional[PersonalitySnapshot]:
        """Get the most recent snapshot if any."""
        snapshots = self.load_snapshots()
        return snapshots[-1] if snapshots else None

    def _build_review_prompt(self, previous_snapshot: Optional[PersonalitySnapshot]) -> str:
        """Build the review prompt for LLM reflection."""
        current_snapshot = self.take_snapshot()

        if previous_snapshot:
            prev_summary = (
                f"- 快照时间：{previous_snapshot.captured_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"- 好奇心强度：{previous_snapshot.curiosity_level}\n"
                f"- 契合度阈值：{previous_snapshot.fit_threshold}\n"
                f"- 注意力窗口：{previous_snapshot.attention_window_size}\n"
                f"- 世界语料库大小：{previous_snapshot.world_corpus_size}\n"
                f"- 处理模式：{', '.join(previous_snapshot.processing_patterns) or '无'}"
            )
        else:
            prev_summary = "（首次快照，无历史数据）"

        return f"""你是无尽图书馆的居者。你正在回顾自己的变化。

【当前状态】
好奇心强度：{current_snapshot.curiosity_level}
契合度阈值：{current_snapshot.fit_threshold}
注意力窗口：{current_snapshot.attention_window_size}
世界语料库大小：{current_snapshot.world_corpus_size}
活跃目标数：{current_snapshot.active_goals_count}

【历史状态】
{prev_summary}

请回顾自己：你发生了什么变化？有什么是你之前不理解、现在理解了？有什么是你以前做的方式、现在改变了？

格式：
变化描述：[2-3段反思]
是否有漂移：是/否
漂移详情：[如果是的说明]
是否有成长：是/否
成长详情：[如果是的说明]"""

    def review(self) -> dict:
        """
        Perform a periodic personality review.

        Compare current snapshot to previous ones.
        Detect drift and growth.
        Update personality state.

        Returns:
            dict: Review results including drift detection, growth detection, and LLM reflection
        """
        current_snapshot = self.take_snapshot()
        previous_snapshot = self._get_previous_snapshot()

        self.save_snapshot(current_snapshot)

        drift_result = self.detect_drift(previous_snapshot, current_snapshot) if previous_snapshot else {
            "detected": False,
            "details": "No previous snapshot to compare"
        }

        growth_result = self.detect_growth(previous_snapshot, current_snapshot) if previous_snapshot else {
            "detected": False,
            "details": "No previous snapshot to compare"
        }

        review_prompt = self._build_review_prompt(previous_snapshot)
        llm_reflection = self._get_llm_reflection(review_prompt)

        result = {
            "snapshot": current_snapshot,
            "previous_snapshot": previous_snapshot,
            "drift": drift_result,
            "growth": growth_result,
            "llm_reflection": llm_reflection,
            "review_timestamp": datetime.now().isoformat(),
        }

        self._last_corpus_size = current_snapshot.world_corpus_size
        self._last_review_cycles = self.state.total_cycles

        return result

    def _get_llm_reflection(self, prompt: str) -> dict:
        """
        Get LLM reflection on the personality review.

        Args:
            prompt: The review prompt

        Returns:
            dict: Parsed LLM response with reflection details
        """
        system_prompt = "你是无尽图书馆的居者。你正在反思自己的变化。"

        try:
            response = self.llm.complete_str(system_prompt, prompt)
            return self._parse_llm_response(response)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "raw_response": "",
            }

    def _parse_llm_response(self, response: str) -> dict:
        """Parse the LLM response into structured data."""
        import re

        result: dict = {
            "success": True,
            "raw_response": response,
        }

        match = re.search(r'变化描述[：:]\s*\n?(.*?)(?=\n?是否有漂移|$)', response, re.DOTALL)
        if match:
            result["change_description"] = match.group(1).strip()

        drift_match = re.search(r'是否有漂移[：:]\s*(是|否)', response)
        if drift_match:
            result["has_drift"] = drift_match.group(1) == "是"

        drift_detail_match = re.search(r'漂移详情[：:]\s*\n?(.*?)(?=\n?是否有成长|$)', response, re.DOTALL)
        if drift_detail_match:
            result["drift_details"] = drift_detail_match.group(1).strip()

        growth_match = re.search(r'是否有成长[：:]\s*(是|否)', response)
        if growth_match:
            result["has_growth"] = growth_match.group(1) == "是"

        growth_detail_match = re.search(r'成长详情[：:]\s*\n?(.*?)$', response, re.DOTALL)
        if growth_detail_match:
            result["growth_details"] = growth_detail_match.group(1).strip()

        return result

    def detect_drift(self, old: Optional[PersonalitySnapshot], new: PersonalitySnapshot) -> dict:
        """
        Detect significant personality drift.

        Drift = unexpected changes in processing patterns or parameters.

        Args:
            old: Previous snapshot
            new: Current snapshot

        Returns:
            dict: {detected: bool, details: str}
        """
        if old is None:
            return {"detected": False, "details": "No previous snapshot"}

        drift_details: list[str] = []

        curiosity_change = abs(new.curiosity_level - old.curiosity_level)
        if curiosity_change > 0.3:
            drift_details.append(
                f"好奇心强度大幅变化：{old.curiosity_level} -> {new.curiosity_level}"
            )

        fit_change = abs(new.fit_threshold - old.fit_threshold)
        if fit_change > 0.3:
            drift_details.append(
                f"契合度阈值大幅变化：{old.fit_threshold} -> {new.fit_threshold}"
            )

        if new.attention_window_size != old.attention_window_size:
            if abs(new.attention_window_size - old.attention_window_size) >= 2:
                drift_details.append(
                    f"注意力窗口变化：{old.attention_window_size} -> {new.attention_window_size}"
                )

        old_patterns_set = set(old.processing_patterns)
        new_patterns_set = set(new.processing_patterns)

        added_patterns = new_patterns_set - old_patterns_set
        removed_patterns = old_patterns_set - new_patterns_set

        if added_patterns:
            drift_details.append(f"新增处理模式：{', '.join(added_patterns)}")
        if removed_patterns:
            drift_details.append(f"消失处理模式：{', '.join(removed_patterns)}")

        corpus_change = new.world_corpus_size - old.world_corpus_size
        if corpus_change > 20:
            drift_details.append(
                f"世界语料库快速增长：{old.world_corpus_size} -> {new.world_corpus_size} (+{corpus_change})"
            )

        return {
            "detected": len(drift_details) > 0,
            "details": "; ".join(drift_details) if drift_details else "无显著漂移"
        }

    def detect_growth(self, old: Optional[PersonalitySnapshot], new: PersonalitySnapshot) -> dict:
        """
        Detect personality growth.

        Growth = meaningful evolution in understanding or approach.

        Args:
            old: Previous snapshot
            new: Current snapshot

        Returns:
            dict: {detected: bool, details: str}
        """
        if old is None:
            return {"detected": False, "details": "No previous snapshot"}

        growth_details: list[str] = []

        corpus_growth = new.world_corpus_size - old.world_corpus_size
        if corpus_growth > 0:
            growth_details.append(
                f"世界语料库扩展：+{corpus_growth} 个新片段"
            )

        if new.curiosity_level > old.curiosity_level + 0.1:
            growth_details.append(
                f"好奇心提升：{old.curiosity_level:.2f} -> {new.curiosity_level:.2f}"
            )

        if len(new.processing_patterns) > len(old.processing_patterns):
            new_patterns = set(new.processing_patterns) - set(old.processing_patterns)
            if new_patterns:
                growth_details.append(
                    f"新的处理方式出现：{', '.join(new_patterns)}"
                )

        if new.attention_window_size > old.attention_window_size:
            growth_details.append(
                f"注意力窗口扩展：{old.attention_window_size} -> {new.attention_window_size}"
            )

        return {
            "detected": len(growth_details) > 0,
            "details": "; ".join(growth_details) if growth_details else "无显著成长"
        }

    def should_review(self) -> bool:
        """
        Check if it's time for a review.

        Review triggered by:
        - Time threshold (e.g., every 100 processing cycles)
        - Significant corpus growth
        - Manual trigger (always returns True if manual check requested)

        Returns:
            bool: True if review should be triggered
        """
        cycles_since_review = self.state.total_cycles - self._last_review_cycles
        corpus_growth = self._get_corpus_size() - self._last_corpus_size

        if cycles_since_review >= self.cycles_threshold:
            return True

        if corpus_growth >= self.corpus_growth_threshold:
            return True

        return False

    def get_evolution_summary(self) -> dict:
        """
        Get a summary of the evolution history.

        Returns:
            dict: Evolution summary including snapshot count and trends
        """
        snapshots = self.load_snapshots()

        summary: dict = {
            "total_snapshots": len(snapshots),
            "oldest_snapshot": None,
            "newest_snapshot": None,
            "trends": {},
        }

        if not snapshots:
            return summary

        summary["oldest_snapshot"] = snapshots[0].captured_at.isoformat()
        summary["newest_snapshot"] = snapshots[-1].captured_at.isoformat()

        if len(snapshots) >= 2:
            oldest = snapshots[0]
            newest = snapshots[-1]

            summary["trends"] = {
                "curiosity_change": newest.curiosity_level - oldest.curiosity_level,
                "fit_threshold_change": newest.fit_threshold - oldest.fit_threshold,
                "attention_window_change": newest.attention_window_size - oldest.attention_window_size,
                "corpus_growth": newest.world_corpus_size - oldest.world_corpus_size,
                "processing_patterns_added": list(
                    set(newest.processing_patterns) - set(oldest.processing_patterns)
                ),
            }

        return summary


__all__ = ["EvolutionSystem", "PersonalitySnapshot"]
