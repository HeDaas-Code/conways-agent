"""
Information Processing Pipeline

Orchestrates the full information processing cycle:
perceive -> judge fit -> translate OR collide -> consistency check 
-> resolve conflicts -> write to world corpus -> log

This is the core "think" loop of the Agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .state import AgentState
from .world_fragment import WorldFragment
from .perception import PerceptionInput
from ..log import log_event


@dataclass
class FitResult:
    """
    Result of judging whether content fits the existing worldview.
    
    Attributes:
        judgment: "high" if content fits well, "low" if it clashes
        confidence: Confidence in the judgment (0.0 to 1.0)
        reasoning: Human-readable reasoning for the judgment
    """
    
    judgment: str
    confidence: float
    reasoning: str
    
    def __post_init__(self) -> None:
        """Validate fit result fields."""
        if self.judgment not in ("high", "low"):
            self.judgment = "high"
        self.confidence = max(0.0, min(1.0, self.confidence))


@dataclass
class ProcessingResult:
    """
    Result of processing a PerceptionInput through the pipeline.
    
    Attributes:
        success: Whether processing completed successfully
        fragment: The created WorldFragment (if successful)
        fit_result: The fit judgment result
        processing_time_ms: How long processing took
        errors: Any errors that occurred
    """
    
    success: bool
    fragment: Optional[WorldFragment] = None
    fit_result: Optional[FitResult] = None
    processing_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def mark_complete(self) -> None:
        """Mark processing as complete and record elapsed time."""
        self.completed_at = datetime.now()
        delta = self.completed_at - self.started_at
        self.processing_time_ms = delta.total_seconds() * 1000


class ProcessingPipeline:
    """
    Orchestrates the full information processing cycle.
    
    The pipeline processes perceptions through these stages:
    1. Judge fit: Does the content fit or clash with existing worldview?
    2. Transform: Either translate (high fit) or collide (low fit)
    3. Consistency check: Verify fragment consistency
    4. Log: Record the processing result
    
    Usage:
        pipeline = ProcessingPipeline()
        result = pipeline.process(perception_input)
    """
    
    def __init__(self) -> None:
        """Initialize the processing pipeline."""
        self._fragments_created: list[WorldFragment] = []
    
    def process(self, input: PerceptionInput) -> ProcessingResult:
        """
        Run one complete processing cycle.
        
        Args:
            input: The perception input to process
            
        Returns:
            ProcessingResult: The result of processing
        """
        result = ProcessingResult(success=False, started_at=datetime.now())
        
        try:
            state = AgentState.load()
            
            fit_result = self.judge_fit(input.content, state)
            result.fit_result = fit_result
            
            if fit_result.judgment == "high":
                fragment = self.translate(input.content, fit_result, state)
            else:
                fragment = self.collide(input.content, fit_result, state)
            
            fragment.source_trigger = f"{input.trigger_type}:{input.file_path}"
            result.fragment = fragment
            
            self._fragments_created.append(fragment)
            result.success = True
            
            log_event(
                "processing",
                f"Processed {input.file_path} via {fragment.fit_path} path",
                {
                    "file_path": input.file_path,
                    "fit_judgment": fit_result.judgment,
                    "fit_confidence": fit_result.confidence,
                    "fit_path": fragment.fit_path,
                    "fragment_title": fragment.title,
                }
            )
            
        except Exception as e:
            result.errors.append(str(e))
            log_event(
                "processing_error",
                f"Failed to process {input.file_path}: {e}",
                {"file_path": input.file_path, "error": str(e)}
            )
        
        result.mark_complete()
        return result
    
    def judge_fit(
        self,
        content: str,
        state: AgentState
    ) -> FitResult:
        """
        Judge whether content fits the existing worldview.
        
        This method uses the Agent's LLM to make an intuitive judgment
        about whether new content aligns with or conflicts with the
        Agent's current understanding.
        
        The LLM call will be implemented here:
        ```python
        # TODO: Integrate LiteLLM for actual LLM-based judgment
        # response = litellm.completion(
        #     model="gpt-4",
        #     messages=[{
        #         "role": "system",
        #         "content": f"You are {state.personality['name']}, "
        #                    f"with traits: {state.personality['traits']}"
        #     }, {
        #         "role": "user", 
        #         "content": f"Does this content fit your worldview?\\n\\n{content[:1000]}"
        #     }]
        # )
        ```
        
        For now, returns a simulated result based on content characteristics.
        
        Args:
            content: The content to judge
            state: Current agent state
            
        Returns:
            FitResult: The fit judgment result
        """
        content_lower = content.lower()
        content_length = len(content)
        
        conflict_indicators = [
            "disagree", "wrong", "incorrect", "contradict",
            "however", "but", "not true", "alternative"
        ]
        
        fit_indicators = [
            "agree", "yes", "understand", "similar",
            "relates to", "connected", "therefore", "because"
        ]
        
        conflict_score = sum(1 for word in conflict_indicators if word in content_lower)
        fit_score = sum(1 for word in fit_indicators if word in content_lower)
        
        has_structure = content_length > 100 and ("# " in content or "-" in content)
        
        if conflict_score > fit_score:
            judgment = "low"
            confidence = min(0.9, 0.5 + conflict_score * 0.1)
            reasoning = f"Content contains {conflict_score} conflict indicators suggesting worldview clash"
        elif fit_score > conflict_score:
            judgment = "high"
            confidence = min(0.9, 0.5 + fit_score * 0.1)
            reasoning = f"Content aligns with {fit_score} worldview markers suggesting good fit"
        elif has_structure:
            judgment = "high"
            confidence = 0.6
            reasoning = "Content is well-structured, treating as high-fit with moderate confidence"
        else:
            judgment = "high"
            confidence = 0.5
            reasoning = "Neutral content, defaulting to high-fit for exploration"
        
        return FitResult(
            judgment=judgment,
            confidence=confidence,
            reasoning=reasoning
        )
    
    def translate(
        self,
        content: str,
        fit_result: FitResult,
        state: AgentState
    ) -> WorldFragment:
        """
        High-fit path: absorb and re-describe in Agent's voice.
        
        When content fits well with the Agent's worldview, this method
        transforms it into the Agent's own understanding, expressed
        in the Agent's distinctive voice.
        
        Args:
            content: The perceived content
            fit_result: The fit judgment result
            state: Current agent state
            
        Returns:
            WorldFragment: The translated fragment in Agent's voice
        """
        agent_name = state.personality.get("name", "Agent")
        title = self._extract_title(content) or f"Understanding of perceived content"
        
        links = self._extract_links(content)
        
        content_preview = content[:500] if len(content) > 500 else content
        
        translated_content = f"""As {agent_name}, I perceive this content through my established lens.

{content_preview}...

This resonates with my existing understanding. I absorb it, letting it reinforce and enrich my worldview.
"""
        
        return WorldFragment(
            title=title,
            content=translated_content,
            links=links,
            source_trigger="manual_perception",
            fit_path="translation",
            created_at=datetime.now()
        )
    
    def collide(
        self,
        content: str,
        fit_result: FitResult,
        state: AgentState
    ) -> WorldFragment:
        """
        Low-fit path: clash with existing worldview, generate new concept.
        
        When content conflicts with or challenges the Agent's worldview,
        this method engages in productive conflict that generates new
        understanding and potentially expands the Agent's conceptual space.
        
        Args:
            content: The perceived content
            fit_result: The fit judgment result
            state: Current agent state
            
        Returns:
            WorldFragment: The collision-generated fragment
        """
        agent_name = state.personality.get("name", "Agent")
        title = self._extract_title(content) or f"Clash with perceived content"
        
        links = self._extract_links(content)
        
        content_preview = content[:500] if len(content) > 500 else content
        
        collided_content = f"""As {agent_name}, this content challenges my existing understanding.

{content_preview}...

I find myself at tension with this. Rather than dismissing it, I engage — 
perhaps there is something new to learn, or perhaps this reveals a boundary of my worldview.
The collision itself is generative.
"""
        
        return WorldFragment(
            title=title,
            content=collided_content,
            links=links,
            source_trigger="manual_perception",
            fit_path="collision",
            created_at=datetime.now()
        )
    
    def _extract_title(self, content: str) -> Optional[str]:
        """
        Extract title from markdown content.
        
        Args:
            content: Raw content
            
        Returns:
            Optional[str]: Extracted title or None
        """
        lines = content.strip().split("\n")
        for line in lines[:5]:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return None
    
    def _extract_links(self, content: str) -> list[str]:
        """
        Extract wikilinks from content.
        
        Args:
            content: Raw content
            
        Returns:
            list[str]: List of extracted link targets
        """
        import re
        pattern = r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]'
        matches = re.findall(pattern, content)
        return list(set(matches))
    
    def get_created_fragments(self) -> list[WorldFragment]:
        """
        Get all fragments created by this pipeline instance.
        
        Returns:
            list[WorldFragment]: List of created fragments
        """
        return self._fragments_created.copy()


__all__ = ["ProcessingPipeline", "FitResult", "ProcessingResult"]
