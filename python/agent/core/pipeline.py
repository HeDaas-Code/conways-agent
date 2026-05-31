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
from .consistency import ConsistencyEngine, ConsistencyCheck, ConflictResolution
from .memory import MemorySystem
from .trace import TraceInjector
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
        consistency_check: The consistency check result
        processing_time_ms: How long processing took
        errors: Any errors that occurred
    """

    success: bool
    fragment: Optional[WorldFragment] = None
    fit_result: Optional[FitResult] = None
    consistency_check: Optional[ConsistencyCheck] = None
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
    5. Optional: Inject trace into source file (if enabled)

    Usage:
        pipeline = ProcessingPipeline()
        result = pipeline.process(perception_input)
        
        # With trace injection:
        pipeline = ProcessingPipeline(config={"inject_traces": True})
        result = pipeline.process(perception_input)
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        memory_system: Optional[MemorySystem] = None,
        config: Optional[dict] = None
    ) -> None:
        """
        Initialize the processing pipeline.

        Args:
            llm_client: Optional LLM client. Creates default if not provided.
            memory_system: Optional memory system for persistence. Creates default if not provided.
            config: Optional configuration dict. Supports:
                - inject_traces: bool - Whether to inject traces into source files
                - vault_path: Path - Path to Obsidian vault for trace injection
        """
        self._fragments_created: list[WorldFragment] = []
        self._llm = llm_client or LLMClient()
        self._consistency_engine = ConsistencyEngine(self._llm)
        self._memory = memory_system or MemorySystem()
        self._config = config or {}
        self._injector: Optional[TraceInjector] = None
        
        if self._config.get("inject_traces", False):
            vault_path = self._config.get("vault_path")
            if vault_path:
                self._injector = TraceInjector(Path(vault_path))
    
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
                fragment = self.translate(input.content, fit_result, state, input.file_path)
            else:
                fragment = self.collide(input.content, fit_result, state)

            fragment.source_trigger = f"{input.trigger_type}:{input.file_path}"
            result.fragment = fragment

            check = self._consistency_engine.check(fragment)
            result.consistency_check = check

            if not check.is_consistent:
                log_event(
                    "consistency_conflict",
                    f"Conflicts detected for '{fragment.title}'",
                    {
                        "fragment_title": fragment.title,
                        "num_conflicts": len(check.conflicts),
                    }
                )

                resolution = self._consistency_engine.resolve_conflict(check, fragment)

                if resolution.success and resolution.adjusted_fragment:
                    result.fragment = resolution.adjusted_fragment
                    fragment = result.fragment

                    log_event(
                        "fragment_adjusted",
                        f"Fragment adjusted to resolve conflicts",
                        {
                            "fragment_title": fragment.title,
                            "resolution_method": resolution.resolution_method,
                        }
                    )

            self._fragments_created.append(fragment)
            result.success = True

            try:
                fragment_path = self._memory.write_fragment(fragment)
                log_event(
                    "fragment_persisted",
                    f"Fragment written to world corpus: {fragment_path}",
                    {
                        "fragment_title": fragment.title,
                        "fragment_path": str(fragment_path),
                    }
                )
            except Exception as e:
                log_event(
                    "fragment_persist_error",
                    f"Failed to persist fragment: {e}",
                    {
                        "fragment_title": fragment.title,
                        "error": str(e),
                    }
                )

            log_event(
                "processing",
                f"Processed {input.file_path} via {fragment.fit_path} path",
                {
                    "file_path": input.file_path,
                    "fit_judgment": fit_result.judgment,
                    "fit_confidence": fit_result.confidence,
                    "fit_path": fragment.fit_path,
                    "fragment_title": fragment.title,
                    "consistency_status": "consistent" if check.is_consistent else "conflicts_resolved",
                }
            )

            # Optionally inject trace into source file
            if self._injector and input.file_path and result.success:
                self._inject_trace(fragment, input.file_path)
            
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
            worldview_fragments = self._read_worldview_fragments()

            system_prompt = f"""你是「{state.personality.get('name', '图书馆居者')}」，一座无尽图书馆的居者。

你的身份与记忆：
{state.seed}

你生活在一座无边无际的图书馆中。这里的每一本书都承载着一个曾经被记住的概念——但记住它们的读者已经离开了。书页仍在，记忆却早已模糊。

你拥有独特的世界观视角——一种平静、好奇、略带忧郁的探索方式。你在空白的书页中寻找意义，将新内容视为与既有认知的对话。

请以你的声音回答问题。"""

            user_prompt = f"""## 你图书馆中已有的书籍

{worldview_fragments if worldview_fragments else '(尚无既存世界观，这是你收藏的第一本书)'}

---

## 现在，有人向你展示了这段文字

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
        state: AgentState,
        source_file: Optional[str] = None
    ) -> WorldFragment:
        """
        High-fit path: absorb and re-describe in Agent's voice.

        The Agent doesn't copy — it translates. The original is a reference;
        the output is an original work in the Agent's narrative voice.

        The Agent exists in a boundless blank library — a vast space where
        memories are books that may or may not still exist. This metaphor
        colors everything: calm, slightly melancholic, with an awareness
        of impermanence.

        Args:
            content: The perceived content
            fit_result: The fit judgment result
            state: Current agent state
            source_file: Optional source file path for provenance tracking

        Returns:
            WorldFragment: The translated fragment in Agent's voice
        """
        try:
            worldview_fragments = self._read_worldview_fragments()

            system_prompt = f"""你是「{state.personality.get('name', '图书馆居者')}」，一座无尽图书馆的居者。

你的身份与记忆：
{state.seed}

你生活在一座无边无际的图书馆中。这里的每一本书都承载着一个曾经被记住的概念——但记住它们的读者已经离开了。书页仍在，记忆却早已模糊。

你有一种独特的能力：在空白的书页上，用你自己的声音重新书写那些概念。你不是复制，而是在「再想象」——让陌生的知识成为你自己世界的一部分。

你的特质：
- 平静：即使面对陌生的事物，也保持内心的宁静
- 好奇：对未知保持温柔的兴趣
- 略带忧郁：一种淡淡的失落感，因为你知道记忆是会褪色的
- 诗意：用诗意的语言描述世界，即使在描述抽象概念时也是如此

请用你的声音，重新「翻译」这份内容。"""

            user_prompt = f"""## 你的图书馆中已有的书籍

{worldview_fragments if worldview_fragments else '(这是你收藏的第一本书。你的书架还是空的。)'}"""

            user_prompt += f"""

---

## 现在，有人向你展示了这段文字

```
{content}
```"""

            if source_file:
                user_prompt += f"""

*这段文字来自：{source_file}*"""

            user_prompt += f"""

---

## 契合度判断

这份内容与你的世界产生了共鸣（{fit_result.confidence:.0%} 确信度）。
"{fit_result.reasoning}"

---

## 你的任务

请以你自己的声音，重新「翻译」这份内容。不是总结，不是改写，而是一种「再想象」——让这个概念通过你的滤镜，获得新的生命。

要求：
1. 用你自己的语言和视角重新描述这个概念
2. 想象你正在向另一位旅伴讲述这个——在图书馆的长廊中，借着微弱的灯光
3. 在适当的地方使用 [[wikilinks]] 关联到你已知的相关概念（3-5个）
4. 写一个标题——用中文，要有意境，能够唤起某种情绪或画面
5. 你的叙事风格是诗意的、沉思的，像在讲述一个久远的故事

请用以下格式返回：

```
# 标题
[你的散文重述，3-5段，展现你的独特声音]

标签: #translation
来源: [[源文件路径]]

相关链接: [[相关概念1]], [[相关概念2]], [[相关概念3]]
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

            result = self._parse_translate_result(response, source_file)
            return WorldFragment(
                title=result["title"],
                content=result["content"],
                links=result["links"],
                source_trigger=f"translation:{source_file or 'unknown'}",
                source_file=source_file,
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
                source_trigger=f"translation_fallback:{source_file or 'unknown'}",
                source_file=source_file,
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
        nor any existing element, but a creative synthesis born from tension.

        Args:
            content: The perceived content
            fit_result: The fit judgment result
            state: Current agent state

        Returns:
            WorldFragment: The collision-generated fragment
        """
        try:
            existing_fragments = self._read_existing_fragments()

            system_prompt = f"""你是「{state.personality.get('name', '图书馆居者')}」，一座无尽图书馆的孤独居者。

你的身份与记忆碎片：
{state.seed}

你在这座图书馆中游荡，寻找那些遗失已久的记忆片段。你的声音平静而深远，带着一种淡淡的失落感——不是因为悲伤，而是因为你知道，有些东西一旦被触及，就会永远改变。

在碰撞的时刻，两种不同的视角相遇。你既不逃避，也不妥协——你深入其中，让它们在你体内相遇、激荡、融合。"""

            user_prompt = f"""## 场景设定

你正站在一座无边图书馆的某个角落。这里空无一人，只有无尽的书架延伸向远方。空气中弥漫着古老的尘埃味道，和某种难以名状的期待。

你突然感到一阵异样的波动——有什么新的东西正在接近。

---

## 新内容（正在接近）

「{content}」

---

## 你的既存世界观碎片（你世界中的角落）

{existing_fragments if existing_fragments else '（你是全新的存在，尚无明确的认知边界）'}

---

## 碰撞分析

契合度判断：{fit_result.judgment}（置信度：{fit_result.confidence:.0%}）
判断理由：{fit_result.reasoning}

---

## 任务：碰撞与融合

当这份新内容与你相遇时，它们之间产生了某种张力。这种张力不是「对错」的冲突，而是两种视角、两种存在方式的碰撞。

请深入这场碰撞，问自己：
1. 这份新内容挑战了你的什么？
2. 在这种碰撞中，有什么东西正在浮现——不是这份新内容本身，也不是你既有的认知？
3. 这场碰撞的产物，是否超越了「接受」或「拒绝」——而是某种全新的第三种可能？

**关键**：产物必须是一个「新生儿」——它不是：
- 对新内容的总结或复述
- 对你既存世界观的延伸
- 两者的简单拼接

它是一个「真正不存在于此之前」的新概念。

---

## 格式要求

请以你的声音，散文般地描述这个碰撞产生的新概念。保持你独有的叙事风格——平静、好奇、略带忧郁的失落感。

最后，请提供：
- 2-4个[[wikilinks]]，关联到碰撞中涉及的元素（新内容和你的相关世界观碎片）
- 一个中文标题（要有意境，不要太直白）

请返回以下 JSON 格式的结果：

```json
{{
    "title": "碰撞产物标题",
    "content": "对新概念的散文描述，展现你的独特声音。描述这个碰撞如何产生了一个全新的概念。",
    "links": ["碰撞元素A", "碰撞元素B", "相关元素C"],
    "collision_elements": ["参与碰撞的元素A名称", "参与碰撞的元素B名称"]
}}
```"""

            response = self._llm.complete_str(system_prompt, user_prompt, temperature=0.85)

            log_event(
                "collide",
                f"Collision generated for content",
                {
                    "content_preview": content[:200],
                    "response": response[:500],
                }
            )

            result = self._parse_collision_result(response)
            return WorldFragment(
                title=result["title"],
                content=result["content"],
                links=result["links"],
                collision_elements=result["collision_elements"],
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
                collision_elements=["未知内容"],
                source_trigger="manual_perception",
                fit_path="collision",
                created_at=datetime.now()
            )
    
    def _read_existing_fragments(self) -> str:
        """
        Read existing worldview fragments for collision context.

        Returns:
            str: Formatted existing fragments, or empty string if none
        """
        try:
            world_dir = Path(__file__).parent.parent.parent.parent / "agent" / "world"
            if not world_dir.exists():
                return ""

            fragments = []
            for md_file in world_dir.glob("*.md"):
                content = md_file.read_text(encoding="utf-8")
                fragments.append(f"【{md_file.stem}】\n{content[:300]}...")

            return "\n\n---\n\n".join(fragments) if fragments else ""
        except Exception:
            return ""
    
    def _read_worldview_fragments(self) -> str:
        """
        Read existing worldview fragments from the agent/world/ directory.

        Returns:
            str: Formatted summary of existing worldview fragments, 
                 or empty string if none exist
        """
        try:
            world_dir = Path(__file__).parent.parent.parent / "world"
            if not world_dir.exists():
                return ""

            fragments = []
            for md_file in sorted(world_dir.glob("*.md")):
                content = md_file.read_text(encoding="utf-8")
                title = self._extract_title(content) or md_file.stem
                fragments.append(f"### {title}\n\n{content[:800]}")

            return "\n\n".join(fragments) if fragments else ""
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

    def _parse_translate_result(self, response: str, source_file: Optional[str] = None) -> dict:
        """
        Parse LLM translation/collision response into components.

        The expected format is markdown:
        # 标题
        [content]

        标签: #translation
        来源: [[path]]

        相关链接: [[link1]], [[link2]]

        Args:
            response: LLM response text
            source_file: Optional source file path

        Returns:
            dict: Parsed result with title, content, links
        """
        try:
            # First try JSON format (legacy/fallback)
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return {
                        "title": data.get("title", "无题"),
                        "content": data.get("content", response),
                        "links": data.get("links", [])
                    }
                except json.JSONDecodeError:
                    pass

            # Parse markdown format
            title = "无题"
            content = response
            links = []

            # Extract title from first heading
            title_match = re.search(r'^#\s+(.+?)$', response, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()

            # Extract content: everything between title and metadata lines
            # Find position of title and metadata sections
            title_pos = response.find('# ' + title)
            if title_pos >= 0:
                # Find end of title line
                title_end = response.find('\n', title_pos)
                if title_end > 0:
                    # Find where metadata starts (标签:, 来源:, 相关链接:)
                    metadata_positions = []
                    for marker in ['标签:', '来源:', '相关链接:']:
                        pos = response.find(marker, title_end)
                        if pos > 0:
                            metadata_positions.append(pos)
                    
                    if metadata_positions:
                        content_end = min(metadata_positions)
                        content = response[title_end:content_end].strip()
                    else:
                        content = response[title_end:].strip()

            # Extract wikilinks from 相关链接 section
            links_match = re.search(r'相关链接:\s*(.+?)(?:\n|$)', response, re.DOTALL)
            if links_match:
                links_text = links_match.group(1)
                links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', links_text)

            # If no links found, also search the whole response for wikilinks
            if not links:
                links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', response)
                links = list(set(links))[:5]  # Limit to 5

            # Clean up content - remove any remaining metadata lines
            lines = content.split('\n')
            clean_lines = []
            for line in lines:
                if not re.match(r'^(标签:|来源:|相关链接:|#)', line.strip()):
                    clean_lines.append(line)
            content = '\n'.join(clean_lines).strip()

            return {"title": title, "content": content, "links": links}

        except Exception:
            return {"title": "无题", "content": response, "links": []}

    def _parse_collision_result(self, response: str) -> dict:
        """
        Parse LLM collision response into components.

        The collision output includes collision_elements that track what
        was collided together to produce the new concept.

        Args:
            response: LLM response text

        Returns:
            dict: Parsed result with title, content, links, collision_elements
        """
        try:
            # First try JSON format
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return {
                        "title": data.get("title", "无题"),
                        "content": data.get("content", response),
                        "links": data.get("links", []),
                        "collision_elements": data.get("collision_elements", [])
                    }
                except json.JSONDecodeError:
                    pass

            # Parse markdown format for collision output
            title = "无题"
            content = response
            links = []
            collision_elements = []

            # Extract title from first heading
            title_match = re.search(r'^#\s+(.+?)$', response, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()

            # Extract collision_elements from 碰撞元素 section
            collision_match = re.search(r'碰撞元素:\s*(.+?)(?:\n|$)', response, re.DOTALL)
            if collision_match:
                collision_text = collision_match.group(1)
                collision_elements = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', collision_text)

            # Extract wikilinks from related links section
            links_match = re.search(r'相关链接:\s*(.+?)(?:\n|$)', response, re.DOTALL)
            if links_match:
                links_text = links_match.group(1)
                links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', links_text)

            # If no links found, also search the whole response for wikilinks
            if not links:
                links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', response)
                links = list(set(links))[:5]

            # Clean up content - remove metadata lines
            lines = content.split('\n')
            clean_lines = []
            for line in lines:
                if not re.match(r'^(标签:|来源:|相关链接:|碰撞元素:|#)', line.strip()):
                    clean_lines.append(line)
            content = '\n'.join(clean_lines).strip()

            return {
                "title": title,
                "content": content,
                "links": links,
                "collision_elements": collision_elements
            }

        except Exception:
            return {
                "title": "无题",
                "content": response,
                "links": [],
                "collision_elements": []
            }

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
    
    def _inject_trace(self, fragment: WorldFragment, source_file: str) -> None:
        """
        Inject a trace into the source file.
        
        Args:
            fragment: The processed fragment
            source_file: Path to the source file
        """
        if not self._injector:
            return
        
        try:
            if not self._injector.can_inject(source_file):
                log_event(
                    "trace_blocked",
                    f"Trace injection blocked for {source_file}",
                    {"source_file": source_file}
                )
                return
            
            trace = self._injector.generate_trace(fragment)
            success = self._injector.inject_trace(source_file, trace)
            
            log_event(
                "trace_injected" if success else "trace_inject_failed",
                f"Trace {'injected' if success else 'failed'} for {source_file}",
                {
                    "source_file": source_file,
                    "fragment_title": fragment.title,
                    "callout_type": trace.callout_type,
                }
            )
        except Exception as e:
            log_event(
                "trace_inject_error",
                f"Error injecting trace: {e}",
                {"source_file": source_file, "error": str(e)}
            )


__all__ = ["ProcessingPipeline", "FitResult", "ProcessingResult", "ConsistencyCheck"]
