"""Warm Memory - Retrieved on-demand memory.

Loaded when relevant to current query. Contains:
- Recent tasks (last 7 days)
- Relevant task history (semantic search)
- User patterns summary
- Related context for current task
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from src.database.orm import Task, TaskStatus, Memory
from src.database.connection import get_async_session


# Memory type constants
MEMORY_TYPE_CONVERSATION_SUMMARY = "conversation_summary"
MEMORY_TYPE_USER_PREFERENCE = "user_preference"
MEMORY_TYPE_TASK_PATTERN = "task_pattern"


settings = get_settings()


@dataclass
class WarmMemoryResult:
    """Result from warm memory retrieval."""
    recent_tasks: List[Dict[str, Any]] = field(default_factory=list)
    related_tasks: List[Dict[str, Any]] = field(default_factory=list)
    user_patterns: Dict[str, Any] = field(default_factory=dict)
    context_items: List[Dict[str, Any]] = field(default_factory=list)
    token_estimate: int = 0


@dataclass
class UserPattern:
    """A detected user pattern."""
    pattern_type: str  # "time_preference", "priority_style", "task_category"
    description: str
    confidence: float
    last_observed: datetime


class WarmMemory:
    """On-demand memory retrieval.

    Retrieves relevant context when needed, including:
    - Recent tasks
    - Semantically related history
    - User behavior patterns
    """

    def __init__(
        self,
        max_items: int = None,
        lookback_days: int = 7,
    ):
        """Initialize warm memory.

        Args:
            max_items: Maximum items to retrieve.
            lookback_days: Days to look back for recent items.
        """
        self.max_items = max_items or settings.warm_memory_max_items
        self.lookback_days = lookback_days

    async def retrieve(
        self,
        user_id: uuid.UUID,
        query: Optional[str] = None,
        task_id: Optional[uuid.UUID] = None,
        include_patterns: bool = True,
    ) -> WarmMemoryResult:
        """Retrieve relevant warm memory.

        Args:
            user_id: The user's ID.
            query: Optional search query for semantic relevance.
            task_id: Optional task ID to find related tasks.
            include_patterns: Whether to include user patterns.

        Returns:
            WarmMemoryResult with retrieved data.
        """
        result = WarmMemoryResult()

        async with get_async_session() as session:
            # Get recent tasks
            recent_tasks = await self._get_recent_tasks(
                session, user_id, self.lookback_days
            )
            result.recent_tasks = recent_tasks

            # Get related tasks if query or task provided
            if query or task_id:
                related = await self._get_related_tasks(
                    session, user_id, query, task_id
                )
                result.related_tasks = related

            # Get user patterns
            if include_patterns:
                patterns = await self._get_user_patterns(session, user_id)
                result.user_patterns = patterns

            # Get stored context items
            context = await self._get_context_items(session, user_id, query)
            result.context_items = context

        # Estimate tokens
        result.token_estimate = self._estimate_tokens(result)

        return result

    async def _get_recent_tasks(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        days: int,
    ) -> List[Dict[str, Any]]:
        """Get tasks from the last N days.

        Args:
            session: Database session.
            user_id: The user's ID.
            days: Number of days to look back.

        Returns:
            List of task dictionaries.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await session.execute(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.deleted_at.is_(None),
                or_(
                    Task.created_at >= cutoff,
                    Task.updated_at >= cutoff,
                ),
            )
            .order_by(Task.updated_at.desc())
            .limit(self.max_items)
        )
        tasks = result.scalars().all()

        return [
            {
                "id": str(task.id),
                "title": task.title,
                "status": task.status.value,
                "priority": task.priority,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "tags": task.tags,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
            for task in tasks
        ]

    async def _get_related_tasks(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        query: Optional[str],
        task_id: Optional[uuid.UUID],
    ) -> List[Dict[str, Any]]:
        """Get tasks related to a query or task.

        Args:
            session: Database session.
            user_id: The user's ID.
            query: Optional search query.
            task_id: Optional related task ID.

        Returns:
            List of related task dictionaries.
        """
        related = []

        if task_id:
            # Get the source task
            source_task = await session.get(Task, task_id)
            if source_task:
                # Find tasks with similar tags
                if source_task.tags:
                    result = await session.execute(
                        select(Task)
                        .where(
                            Task.user_id == user_id,
                            Task.id != task_id,
                            Task.deleted_at.is_(None),
                            Task.tags.overlap(source_task.tags),
                        )
                        .limit(10)
                    )
                    related.extend(result.scalars().all())

                # Find subtasks and parent
                if source_task.parent_id:
                    parent = await session.get(Task, source_task.parent_id)
                    if parent:
                        related.append(parent)

                # Find tasks with similar title keywords
                title_words = source_task.title.lower().split()[:3]
                if title_words:
                    for word in title_words:
                        if len(word) > 3:  # Skip short words
                            result = await session.execute(
                                select(Task)
                                .where(
                                    Task.user_id == user_id,
                                    Task.id != task_id,
                                    Task.deleted_at.is_(None),
                                    Task.title.ilike(f"%{word}%"),
                                )
                                .limit(5)
                            )
                            related.extend(result.scalars().all())

        if query:
            # Simple keyword search
            keywords = query.lower().split()
            for keyword in keywords[:3]:
                if len(keyword) > 2:
                    result = await session.execute(
                        select(Task)
                        .where(
                            Task.user_id == user_id,
                            Task.deleted_at.is_(None),
                            or_(
                                Task.title.ilike(f"%{keyword}%"),
                                Task.description.ilike(f"%{keyword}%"),
                            ),
                        )
                        .limit(10)
                    )
                    related.extend(result.scalars().all())

        # Deduplicate and limit
        seen_ids = set()
        unique_related = []
        for task in related:
            if task.id not in seen_ids:
                seen_ids.add(task.id)
                unique_related.append({
                    "id": str(task.id),
                    "title": task.title,
                    "status": task.status.value,
                    "priority": task.priority,
                    "tags": task.tags,
                })
                if len(unique_related) >= 15:
                    break

        return unique_related

    async def _get_user_patterns(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Get detected user patterns.

        Args:
            session: Database session.
            user_id: The user's ID.

        Returns:
            Dictionary of patterns.
        """
        patterns = {}

        # Analyze task completion patterns
        result = await session.execute(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at.isnot(None),
            )
            .order_by(Task.completed_at.desc())
            .limit(50)
        )
        completed_tasks = result.scalars().all()

        if completed_tasks:
            # Analyze completion times
            completion_hours = [
                task.completed_at.hour
                for task in completed_tasks
                if task.completed_at
            ]
            if completion_hours:
                avg_hour = sum(completion_hours) // len(completion_hours)
                if avg_hour < 12:
                    patterns["productivity_time"] = "morning"
                elif avg_hour < 17:
                    patterns["productivity_time"] = "afternoon"
                else:
                    patterns["productivity_time"] = "evening"

            # Analyze common tags
            all_tags = []
            for task in completed_tasks:
                all_tags.extend(task.tags or [])
            if all_tags:
                tag_counts = {}
                for tag in all_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]
                patterns["common_categories"] = [tag for tag, _ in top_tags]

            # Average priority
            priorities = [task.priority for task in completed_tasks if task.priority]
            if priorities:
                avg_priority = sum(priorities) / len(priorities)
                if avg_priority >= 4:
                    patterns["priority_preference"] = "high_priority_focus"
                elif avg_priority <= 2:
                    patterns["priority_preference"] = "low_priority_focus"
                else:
                    patterns["priority_preference"] = "balanced"

        return patterns

    async def _get_context_items(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        query: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Get stored context/memory items.

        Args:
            session: Database session.
            user_id: The user's ID.
            query: Optional search query.

        Returns:
            List of context items.
        """
        items = []

        # Get recent memories
        stmt = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.memory_type.in_([
                    MEMORY_TYPE_CONVERSATION_SUMMARY,
                    MEMORY_TYPE_USER_PREFERENCE,
                    MEMORY_TYPE_TASK_PATTERN,
                ]),
            )
            .order_by(Memory.created_at.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        memories = result.scalars().all()

        for memory in memories:
            items.append({
                "type": memory.memory_type.value,
                "content": memory.content[:500],  # Truncate
                "created_at": memory.created_at.isoformat(),
            })

        return items

    def _estimate_tokens(self, result: WarmMemoryResult) -> int:
        """Estimate tokens for the result.

        Args:
            result: The warm memory result.

        Returns:
            Estimated token count.
        """
        total_chars = 0

        for task in result.recent_tasks:
            total_chars += len(str(task))
        for task in result.related_tasks:
            total_chars += len(str(task))
        total_chars += len(str(result.user_patterns))
        for item in result.context_items:
            total_chars += len(str(item))

        # Rough estimate: 4 chars per token
        return total_chars // 4

    async def store_pattern(
        self,
        user_id: uuid.UUID,
        pattern_type: str,
        content: str,
    ) -> None:
        """Store a detected user pattern.

        Args:
            user_id: The user's ID.
            pattern_type: Type of pattern.
            content: Pattern description.
        """
        async with get_async_session() as session:
            memory = Memory(
                user_id=user_id,
                memory_type=MEMORY_TYPE_TASK_PATTERN,
                source_type="learning",
                content=content,
                metadata={"pattern_type": pattern_type},
            )
            session.add(memory)

    async def store_summary(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        summary: str,
    ) -> None:
        """Store a conversation summary.

        Args:
            user_id: The user's ID.
            session_id: The session ID.
            summary: The conversation summary.
        """
        async with get_async_session() as session:
            memory = Memory(
                user_id=user_id,
                memory_type=MEMORY_TYPE_CONVERSATION_SUMMARY,
                source_type="session",
                content=summary,
                metadata={"session_id": str(session_id)},
            )
            session.add(memory)

    def format_for_context(self, result: WarmMemoryResult) -> str:
        """Format warm memory for inclusion in LLM context.

        Args:
            result: The warm memory result.

        Returns:
            Formatted string for LLM context.
        """
        parts = []

        if result.recent_tasks:
            parts.append("**Recent Tasks:**")
            for task in result.recent_tasks[:5]:
                status_icon = {
                    "pending": "[ ]",
                    "in_progress": "[~]",
                    "completed": "[x]",
                    "blocked": "[!]",
                }.get(task.get("status", ""), "[ ]")
                parts.append(f"  {status_icon} {task.get('title', 'Untitled')}")

        if result.user_patterns:
            parts.append("\n**User Patterns:**")
            for key, value in result.user_patterns.items():
                parts.append(f"  - {key}: {value}")

        return "\n".join(parts)
