"""
Topic Keyword Extraction - Greedy substring matching with synonym expansion.

Uses keyword matching with synonym expansion, sorted by length (longest first)
for greedy matching. No LLM required.
"""

from collections import Counter
from typing import Optional


# Core topic dictionary with synonyms
TOPIC_DICTIONARY: dict[str, set[str]] = {
    "编程": {"编程", "code", "写代码", "开发", "程序员", "软件", "程序", "coding", "development"},
    "AI": {"AI", "人工智能", "机器学习", "深度学习", "ML", "DL", "模型", "神经网络", "chatgpt", "gpt", "llm", "大模型"},
    "Python": {"python", "python3", "py", ".py", "pip", "pipenv", "venv", "pyenv"},
    "JavaScript": {"javascript", "js", "node", "nodejs", "npm", "前端", "react", "vue", "angular", "typescript", "ts"},
    "数据": {"数据", "database", "db", "sql", "mysql", "postgres", "mongodb", "redis", "数据处理", "分析"},
    "Web": {"web", "http", "api", "rest", "graphql", "服务器", "frontend", "backend", "全栈"},
    "DevOps": {"devops", "docker", "kubernetes", "k8s", "ci/cd", "jenkins", "github actions", "部署", "容器"},
    "设计": {"设计", "design", "ui", "ux", "界面", "用户体验", "交互", "figma", "原型"},
    "算法": {"算法", "algorithm", "数据结构", "排序", "搜索", "图论", "dp", "动态规划"},
    "哲学": {"哲学", "philosophy", "思考", "存在", "意识", "认知", "形而上学", "本体论", "认识论"},
    "创意": {"创意", "creative", "艺术", "写作", "灵感", "创作", "故事", "小说"},
    "效率": {"效率", "productivity", "效率工具", "时间管理", "GTD", "番茄钟", "工作流"},
    "系统": {"系统", "system", "架构", "微服务", "分布式", "并发", "性能", "优化"},
    "安全": {"安全", "security", "加密", "认证", "授权", "隐私", "漏洞", "渗透测试"},
}


class TopicExtractor:
    """
    Extracts topics from text using greedy substring matching.

    Supports:
    - Direct keyword matching
    - Synonym expansion
    - Multi-word topic detection
    - Confidence scoring
    """

    def __init__(self, min_confidence: float = 0.3):
        """
        Initialize topic extractor.

        Args:
            min_confidence: Minimum confidence threshold for topic inclusion
        """
        self.min_confidence = min_confidence
        self._build_index()

    def _build_index(self) -> None:
        """Build index sorted by length (longest first) for substring matching."""
        # Build list of (synonym, canonical_topic) sorted by length descending
        self._synonyms: list[tuple[str, str]] = []
        for topic, synonyms in TOPIC_DICTIONARY.items():
            for synonym in synonyms:
                self._synonyms.append((synonym.lower(), topic))
        # Sort by length descending for greedy matching
        self._synonyms.sort(key=lambda x: len(x[0]), reverse=True)

    def extract_topics(self, text: str) -> list[tuple[str, float]]:
        """
        Extract topics from text.

        Args:
            text: Input text to analyze

        Returns:
            List of (topic, confidence) tuples, sorted by confidence descending
        """
        if not text or not text.strip():
            return []

        text_lower = text.lower()
        matched_topics: list[str] = []

        # Greedy substring matching
        i = 0
        while i < len(text_lower):
            matched = False
            # Try longest matches first
            for synonym, topic in self._synonyms:
                if text_lower[i:].startswith(synonym):
                    matched_topics.append(topic)
                    i += len(synonym)
                    matched = True
                    break
            if not matched:
                i += 1

        if not matched_topics:
            return []

        # Count topic frequencies
        topic_counts = Counter(matched_topics)

        # Calculate confidence scores
        max_count = max(topic_counts.values())
        results = []
        for topic, count in topic_counts.most_common():
            confidence = count / max_count  # Normalize to 0-1
            if confidence >= self.min_confidence:
                results.append((topic, round(confidence, 2)))

        return results

    def extract_keywords(self, text: str, top_k: int = 5) -> list[str]:
        """
        Extract top keywords from text.

        Args:
            text: Input text
            top_k: Number of top keywords to return

        Returns:
            List of top keyword strings
        """
        topics = self.extract_topics(text)
        return [topic for topic, _ in topics[:top_k]]


def extract_keywords_simple(text: str) -> list[str]:
    """
    Simple topic extraction without class instantiation.

    Utility function for quick usage.
    """
    extractor = TopicExtractor()
    return extractor.extract_keywords(text)
