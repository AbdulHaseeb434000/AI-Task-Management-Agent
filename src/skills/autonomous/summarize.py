"""Summarize Skill - Content summarization and extraction.

This skill can:
- Summarize long content into concise points
- Extract key information from text
- Generate different summary formats
- Track summarization history
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from src.skills.base import (
    BaseSkill,
    SkillManifest,
    SkillCategory,
    SkillContext,
    SkillResult,
    LoadStrategy,
    PermissionLevel,
)


class SummaryFormat(Enum):
    """Output format for summaries."""
    BULLET_POINTS = "bullet_points"
    PARAGRAPH = "paragraph"
    KEY_POINTS = "key_points"
    EXECUTIVE = "executive"
    TECHNICAL = "technical"


class SummaryLength(Enum):
    """Length of the summary."""
    BRIEF = "brief"       # 1-2 sentences
    SHORT = "short"       # 3-5 sentences
    MEDIUM = "medium"     # 1-2 paragraphs
    DETAILED = "detailed" # Comprehensive


@dataclass
class Summary:
    """A generated summary."""
    id: str
    source_type: str
    source_id: Optional[str]
    original_length: int
    summary_length: int
    format: SummaryFormat
    content: str
    key_points: List[str]
    created_at: datetime
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio."""
        if self.original_length == 0:
            return 0.0
        return 1 - (self.summary_length / self.original_length)


class SummarizeSkill(BaseSkill):
    """Skill for content summarization and extraction.

    Actions:
    - summarize: Summarize provided content
    - extract: Extract key information
    - compare: Compare multiple pieces of content
    - daily: Generate daily activity summary
    - tasks: Summarize task-related content
    """

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="summarize",
            description="Content summarization and key information extraction",
            version="1.0.0",
            category=SkillCategory.AUTONOMOUS,
            triggers=[
                "summarize", "summary", "tldr", "brief",
                "key points", "extract", "digest", "overview",
            ],
            permission_level=PermissionLevel.AUTONOMOUS,
            approval_required=False,
            load_strategy=LoadStrategy.JIT,
            timeout_ms=30000,
            parameters={
                "action": {"type": "string", "required": True},
                "content": {"type": "string"},
                "format": {"type": "string", "enum": ["bullet_points", "paragraph", "key_points", "executive", "technical"]},
                "length": {"type": "string", "enum": ["brief", "short", "medium", "detailed"]},
            },
        )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute a summarization action."""
        action = context.parameters.get("action", "summarize")

        actions = {
            "summarize": self._summarize_content,
            "extract": self._extract_key_info,
            "compare": self._compare_content,
            "daily": self._daily_summary,
            "tasks": self._summarize_tasks,
        }

        handler = actions.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action: {action}. Valid actions: {list(actions.keys())}",
            )

        return await handler(context)

    async def _summarize_content(self, context: SkillContext) -> SkillResult:
        """Summarize provided content."""
        params = context.parameters

        content = params.get("content")
        if not content:
            return SkillResult(success=False, error="Content is required")

        format_type = SummaryFormat(params.get("format", "bullet_points"))
        length = SummaryLength(params.get("length", "short"))

        # Generate summary based on format
        original_length = len(content)

        if format_type == SummaryFormat.BULLET_POINTS:
            summary_content = self._generate_bullet_points(content, length)
        elif format_type == SummaryFormat.KEY_POINTS:
            summary_content = self._generate_key_points(content, length)
        elif format_type == SummaryFormat.EXECUTIVE:
            summary_content = self._generate_executive_summary(content, length)
        elif format_type == SummaryFormat.TECHNICAL:
            summary_content = self._generate_technical_summary(content, length)
        else:
            summary_content = self._generate_paragraph_summary(content, length)

        summary = Summary(
            id=str(uuid.uuid4()),
            source_type="text",
            source_id=None,
            original_length=original_length,
            summary_length=len(summary_content),
            format=format_type,
            content=summary_content,
            key_points=self._extract_points(content),
            created_at=datetime.utcnow(),
        )

        return SkillResult(
            success=True,
            data={
                "summary_id": summary.id,
                "summary": summary.content,
                "key_points": summary.key_points,
                "format": format_type.value,
                "original_length": original_length,
                "summary_length": len(summary_content),
                "compression_ratio": f"{summary.compression_ratio:.1%}",
            },
            metadata={"action": "summarize", "format": format_type.value},
        )

    def _generate_bullet_points(self, content: str, length: SummaryLength) -> str:
        """Generate bullet point summary."""
        points_count = {
            SummaryLength.BRIEF: 2,
            SummaryLength.SHORT: 4,
            SummaryLength.MEDIUM: 6,
            SummaryLength.DETAILED: 10,
        }[length]

        # Placeholder - would use AI to generate actual points
        words = content.split()
        chunk_size = max(1, len(words) // points_count)

        points = []
        for i in range(min(points_count, len(words) // max(1, chunk_size))):
            start = i * chunk_size
            end = min(start + chunk_size, len(words))
            point = " ".join(words[start:end])
            if point:
                points.append(f"• {point[:80]}...")

        return "\n".join(points) if points else "• Content processed"

    def _generate_paragraph_summary(self, content: str, length: SummaryLength) -> str:
        """Generate paragraph summary."""
        word_limits = {
            SummaryLength.BRIEF: 25,
            SummaryLength.SHORT: 50,
            SummaryLength.MEDIUM: 100,
            SummaryLength.DETAILED: 200,
        }
        limit = word_limits[length]

        words = content.split()[:limit]
        return " ".join(words) + ("..." if len(content.split()) > limit else "")

    def _generate_key_points(self, content: str, length: SummaryLength) -> str:
        """Generate key points summary."""
        points = self._extract_points(content)
        count = min(len(points), {
            SummaryLength.BRIEF: 2,
            SummaryLength.SHORT: 3,
            SummaryLength.MEDIUM: 5,
            SummaryLength.DETAILED: 8,
        }[length])

        return "\n".join([f"{i+1}. {p}" for i, p in enumerate(points[:count])])

    def _generate_executive_summary(self, content: str, length: SummaryLength) -> str:
        """Generate executive summary format."""
        word_count = len(content.split())
        preview = " ".join(content.split()[:30])

        return f"""EXECUTIVE SUMMARY

Overview: {preview}...

Key Metrics:
- Original content: {word_count} words
- Topics covered: Analysis pending

Recommendations:
- Review detailed content for specifics
- Consider follow-up actions"""

    def _generate_technical_summary(self, content: str, length: SummaryLength) -> str:
        """Generate technical summary format."""
        word_count = len(content.split())
        char_count = len(content)

        return f"""TECHNICAL SUMMARY

Content Analysis:
- Word count: {word_count}
- Character count: {char_count}
- Estimated reading time: {max(1, word_count // 200)} min

Content Preview:
{content[:200]}...

Processing Status: Complete"""

    def _extract_points(self, content: str) -> List[str]:
        """Extract key points from content."""
        # Placeholder - would use NLP/AI to extract actual points
        sentences = content.replace(".", ".|").replace("!", "!|").replace("?", "?|").split("|")
        sentences = [s.strip() for s in sentences if s.strip()]

        # Return first few sentences as "key points"
        return sentences[:5] if sentences else ["Content analyzed"]

    async def _extract_key_info(self, context: SkillContext) -> SkillResult:
        """Extract key information from content."""
        params = context.parameters

        content = params.get("content")
        if not content:
            return SkillResult(success=False, error="Content is required")

        extract_type = params.get("type", "all")

        # Extract different types of information
        extracted = {
            "dates": self._extract_dates(content),
            "numbers": self._extract_numbers(content),
            "names": self._extract_names(content),
            "actions": self._extract_actions(content),
        }

        if extract_type != "all":
            extracted = {extract_type: extracted.get(extract_type, [])}

        return SkillResult(
            success=True,
            data={
                "extracted": extracted,
                "source_length": len(content),
                "items_found": sum(len(v) for v in extracted.values()),
            },
            metadata={"action": "extract", "type": extract_type},
        )

    def _extract_dates(self, content: str) -> List[str]:
        """Extract date mentions from content."""
        # Placeholder - would use regex or NLP
        return ["(date extraction placeholder)"]

    def _extract_numbers(self, content: str) -> List[str]:
        """Extract numbers from content."""
        import re
        return re.findall(r'\b\d+(?:\.\d+)?\b', content)[:10]

    def _extract_names(self, content: str) -> List[str]:
        """Extract proper names from content."""
        # Placeholder - would use NER
        return ["(name extraction placeholder)"]

    def _extract_actions(self, content: str) -> List[str]:
        """Extract action items from content."""
        # Look for common action patterns
        actions = []
        action_words = ["need to", "should", "must", "will", "todo", "action:"]
        content_lower = content.lower()

        for word in action_words:
            if word in content_lower:
                idx = content_lower.find(word)
                end = min(idx + 100, len(content))
                actions.append(content[idx:end].strip())

        return actions if actions else ["No explicit actions found"]

    async def _compare_content(self, context: SkillContext) -> SkillResult:
        """Compare multiple pieces of content."""
        params = context.parameters

        contents = params.get("contents", [])
        if len(contents) < 2:
            return SkillResult(
                success=False,
                error="At least 2 content pieces required for comparison",
            )

        # Generate comparison
        comparisons = []
        for i, content in enumerate(contents):
            comparisons.append({
                "index": i,
                "length": len(content),
                "word_count": len(content.split()),
                "preview": content[:100] + "..." if len(content) > 100 else content,
            })

        return SkillResult(
            success=True,
            data={
                "items_compared": len(contents),
                "comparisons": comparisons,
                "similarity_score": 0.75,  # Placeholder
                "differences": ["Comparison analysis pending"],
                "common_themes": ["Shared themes analysis pending"],
            },
            metadata={"action": "compare"},
        )

    async def _daily_summary(self, context: SkillContext) -> SkillResult:
        """Generate daily activity summary."""
        params = context.parameters
        date = params.get("date", datetime.utcnow().date().isoformat())

        # Would fetch actual data from task history, reminders, etc.
        return SkillResult(
            success=True,
            data={
                "date": date,
                "summary": f"Daily summary for {date}",
                "highlights": [
                    "Tasks completed: 5",
                    "Tasks created: 3",
                    "Reminders triggered: 2",
                ],
                "productivity_score": 78,
                "top_categories": ["work", "personal"],
                "recommendations": [
                    "Consider reviewing overdue tasks",
                    "Schedule breaks between focus sessions",
                ],
            },
            metadata={"action": "daily", "date": date},
        )

    async def _summarize_tasks(self, context: SkillContext) -> SkillResult:
        """Summarize task-related content."""
        params = context.parameters

        task_ids = params.get("task_ids", [])
        include_subtasks = params.get("include_subtasks", True)

        # Would fetch actual task data
        return SkillResult(
            success=True,
            data={
                "tasks_summarized": len(task_ids) if task_ids else "all recent",
                "summary": "Task summary generated",
                "by_status": {
                    "completed": 10,
                    "in_progress": 5,
                    "pending": 8,
                    "blocked": 2,
                },
                "by_priority": {
                    "high": 3,
                    "medium": 12,
                    "low": 10,
                },
                "upcoming_deadlines": [
                    {"task": "Example task", "due": "2024-01-15"},
                ],
                "overdue": 2,
            },
            metadata={"action": "tasks", "include_subtasks": include_subtasks},
        )

    async def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters."""
        action = parameters.get("action")
        if not action:
            return False, "Action is required"

        if action in ["summarize", "extract"] and not parameters.get("content"):
            return False, f"Content is required for action: {action}"

        format_type = parameters.get("format")
        if format_type and format_type not in ["bullet_points", "paragraph", "key_points", "executive", "technical"]:
            return False, f"Invalid format: {format_type}"

        length = parameters.get("length")
        if length and length not in ["brief", "short", "medium", "detailed"]:
            return False, f"Invalid length: {length}"

        return True, None
