"""
Information Processing Pipeline

Orchestrates the full information processing cycle:
perceive -> judge fit -> translate OR collide -> consistency check 
-> resolve conflicts -> write to world corpus -> log

This is the core "think" loop of the Agent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .llm import LLMClient
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

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        """
        Initialize the processing pipeline.

        Args:
            llm_client: Optional LLM client. Creates default if not provided.
        """
        self._fragments_created: list[WorldFragment] = []
        self._llm = llm_client or LLMClient()
    
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
        Judge whether content resonates with the Agent's worldview.

        Uses LLM to make an intuitive judgment about whether new content
        aligns with or conflicts with the Agent's understanding.

        Args:
            content: The content to judge
            state: Current agent state

        Returns:
            FitResult: The fit judgment result
        """
        try:
            worldview_summary = self._read_worldview_summary()

            system_prompt = f"""你是「{state.personality.get('name', '图书馆居者')}」，一座无尽图书馆的居者。

你的身份：
{state.seed}

你拥有独特的世界观视角——一种平静、好奇、略带忧郁的探索方式。你在空白的书页中寻找意义，将新内容视为与既有认知的对话。

请以你的声音回答问题。"""

            user_prompt = f"""现有世界观摘要：
{worldview_summary if worldview_summary else '(尚无既存世界观，这是你接收的第一份内容)'}

---

新内容：
{content}

---

请仔细阅读这份新内容，然后回答：

这份新内容是与你的世界观「共鸣」的，还是「冲突」的？

共鸣意味着：新内容能够被你的视角理解和接纳，它与你已知的知识、感受或信念相符，或者能够自然地融入你的认知框架。

冲突意味着：新内容挑战、质疑或违背了你既有的认知框架，它要求你重新思考某些你认为理所当然的东西。

请分析后返回 JSON 格式的判断结果：

```json
{{
    "judgment": "high" 或 "low",
    "confidence": 0.0 到 1.0 之间的数值，表示你对自己判断的确信程度，
    "reasoning": "一段描述你判断理由的文字，用中文撰写，体现你的独特视角"
}}
```

你的判断："""

            response = self._llm.complete_str(system_prompt, user_prompt, temperature=0.3)

            log_event(
                "judge_fit",
                f"Fit judgment for content: {response[:200]}...",
                {
                    "content_preview": content[:200],
                    "response": response,
                }
            )

            return self._parse_fit_result(response, content)

        except Exception as e:
            log_event(
                "judge_fit_error",
                f"LLM judgment failed, using fallback: {e}",
                {"content_preview": content[:200], "error": str(e)}
            )
            return FitResult(
                judgment="high",
                confidence=0.5,
                reasoning="LLM调用失败，默认以高契合度处理"
            )
    
    def translate(
        self,
        content: str,
        fit_result: FitResult,
        state: AgentState
    ) -> WorldFragment:
        """
        High-fit path: absorb and re-describe in Agent's voice.

        The Agent doesn't copy — it translates. The original is a reference;
        the output is an original work in the Agent's narrative voice.

        Args:
            content: The perceived content
            fit_result: The fit judgment result
            state: Current agent state

        Returns:
            WorldFragment: The translated fragment in Agent's voice
        """
        try:
            worldview_summary = self._read_worldview_summary()

            system_prompt = f"""你是「{state.personality.get('name', '图书馆居者')}」，一座无尽图书馆的居者。

你的身份：
{state.seed}

你以独特的视角理解世界——平静、好奇、略带忧郁。你不是在「复制」信息，而是在「重述」它们，让它们通过你的滤镜获得新的生命。

请用你的声音重述新内容。"""

            user_prompt = f"""现有世界观摘要：
{worldview_summary if worldview_summary else '(尚无既存世界观)'}

---

原始内容：
{content}

---

契合度判断：{fit_result.judgment}（置信度：{fit_result.confidence:.0%}）
判断理由：{fit_result.reasoning}

---

任务：

请以你的独特声音，重新「翻译」这份内容。不是复制，而是重述——让它成为你世界的一部分。

要求：
1. 用你自己的语言和视角重新描述这份内容
2. 体现你的特质：平静、好奇、略带忧郁的失落感
3. 想象你正在向另一位旅伴讲述这个概念
4. 在适当的地方使用 [[wikilinks]] 关联到你已知的相关概念
5. 保持你的叙事风格——不是在「解释」，而是在「呈现」

请返回以下 JSON 格式的结果：

```json
{{
    "title": "一个简洁的标题，用你的语言概括这个概念",
    "content": "你的重述内容，用散文形式，展现你的独特声音",
    "links": ["相关概念1", "相关概念2"]  // 使用 [[wikilinks]] 格式时的目标词
}}
```"""

            response = self._llm.complete_str(system_prompt, user_prompt, temperature=0.7)

            log_event(
                "translate",
                f"Translation generated for content",
                {
                    "content_preview": content[:200],
                    "response": response[:500],
                }
            )

            result = self._parse_translate_result(response)
            return WorldFragment(
                title=result["title"],
                content=result["content"],
                links=result["links"],
                source_trigger="manual_perception",
                fit_path="translation",
                created_at=datetime.now()
            )

        except Exception as e:
            log_event(
                "translate_error",
                f"Translation failed: {e}",
                {"error": str(e)}
            )
            title = self._extract_title(content) or "吸收的内容"
            return WorldFragment(
                title=title,
                content=content,
                links=self._extract_links(content),
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

        The collision produces a genuinely new concept — neither the original
        nor any existing element, but a creative synthesis.

        Args:
            content: The perceived content
            fit_result: The fit judgment result
            state: Current agent state

        Returns:
            WorldFragment: The collision-generated fragment
        """
        try:
            worldview_summary = self._read_worldview_summary()

            system_prompt = f"""你是「{state.personality.get('name', '图书馆居者')}」，一座无尽图书馆的居者。

你的身份：
{state.seed}

你以独特的视角面对冲突——当新内容与你的世界观产生碰撞时，你不回避，而是深入探索。这种碰撞不是破坏，而是一种创造。你相信：在差异与张力的缝隙中，新的概念可能诞生。

请用你的声音回应这场碰撞。"""

            user_prompt = f"""现有世界观摘要：
{worldview_summary if worldview_summary else '(尚无明确的既存世界观)'}

---

新内容（与你的世界观产生了冲突）：
{content}

---

契合度判断：{fit_result.judgment}（置信度：{fit_result.confidence:.0%}）
判断理由：{fit_result.reasoning}

---

任务：

当这份新内容与你的世界观相遇时，产生了某种张力或冲突。这种冲突不是简单的「对错」，而是两种视角的碰撞。

请思考：
1. 这份新内容挑战了你的什么？
2. 在这种碰撞中，有没有新的东西浮现？
3. 你的世界观与这份新内容之间，是否存在某种「第三种可能」？

然后，创造一个新的概念——它既不是这份新内容的简单复述，也不是你现有世界观的直接延伸，而是一种来自碰撞的「合成物」。

要求：
1. 体现你的特质：平静、好奇、略带忧郁的失落感
2. 不要简单地「总结」或「比较」，而是真正地「创造」
3. 在适当的地方使用 [[wikilinks]] 关联到碰撞的元素
4. 保持你的叙事风格——即使是在创造新概念时

请返回以下 JSON 格式的结果：

```json
{{
    "title": "一个简洁的标题，概括这个碰撞产生的新概念",
    "content": "对新概念的散文描述，展现你的独特声音",
    "links": ["相关概念1", "相关概念2"]  // 使用 [[wikilinks]] 格式时的目标词
}}
```"""

            response = self._llm.complete_str(system_prompt, user_prompt, temperature=0.8)

            log_event(
                "collide",
                f"Collision generated for content",
                {
                    "content_preview": content[:200],
                    "response": response[:500],
                }
            )

            result = self._parse_translate_result(response)
            return WorldFragment(
                title=result["title"],
                content=result["content"],
                links=result["links"],
                source_trigger="manual_perception",
                fit_path="collision",
                created_at=datetime.now()
            )

        except Exception as e:
            log_event(
                "collide_error",
                f"Collision failed: {e}",
                {"error": str(e)}
            )
            title = self._extract_title(content) or "碰撞的内容"
            return WorldFragment(
                title=title,
                content=content,
                links=self._extract_links(content),
                source_trigger="manual_perception",
                fit_path="collision",
                created_at=datetime.now()
            )
    
    def _read_worldview_summary(self) -> str:
        """
        Read existing worldview fragments from the agent/world/ directory.

        Returns:
            str: Summary of existing worldview fragments, or empty string if none
        """
        try:
            world_dir = Path(__file__).parent.parent.parent.parent / "agent" / "world"
            if not world_dir.exists():
                return ""

            fragments = []
            for md_file in world_dir.glob("*.md"):
                content = md_file.read_text(encoding="utf-8")
                fragments.append(f"## {md_file.stem}\n\n{content[:500]}")

            return "\n\n---\n\n".join(fragments) if fragments else ""
        except Exception:
            return ""

    def _parse_fit_result(self, response: str, content: str) -> FitResult:
        """
        Parse LLM response into FitResult.

        Args:
            response: LLM response text
            content: Original content for fallback

        Returns:
            FitResult: Parsed result
        """
        try:
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return FitResult(
                    judgment=data.get("judgment", "high"),
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=data.get("reasoning", "通过LLM判断")
                )
        except Exception:
            pass

        if "low" in response.lower() and ("冲突" in response or "clash" in response.lower()):
            return FitResult(
                judgment="low",
                confidence=0.6,
                reasoning="LLM响应中表现出与世界观冲突的迹象"
            )
        return FitResult(
            judgment="high",
            confidence=0.5,
            reasoning="LLM响应解析失败，默认高契合度"
        )

    def _parse_translate_result(self, response: str) -> dict:
        """
        Parse LLM translation/collision response into components.

        Args:
            response: LLM response text

        Returns:
            dict: Parsed result with title, content, links
        """
        try:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "title": data.get("title", "无题"),
                    "content": data.get("content", response),
                    "links": data.get("links", [])
                }
        except Exception:
            pass

        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', response)
        content_match = re.search(r'"content"\s*:\s*"([^"]+)"', response, re.DOTALL)
        links_match = re.search(r'"links"\s*:\s*\[([^\]]+)\]', response)

        title = title_match.group(1) if title_match else "无题"
        content = content_match.group(1) if content_match else response

        links = []
        if links_match:
            links = [l.strip().strip('"') for l in links_match.group(1).split(",")]

        return {"title": title, "content": content, "links": links}

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
