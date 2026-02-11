"""Learning Module - Agent-controlled memory and preference learning.

This module provides tools for the agent to:
- Store learned patterns about user behavior
- Update user preferences based on observations
- Remember important context for future conversations
- Request approval for significant preference changes
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import User, Memory, Task, TaskStatus
from src.database.connection import get_async_session
from src.approvals.queue import ApprovalQueue, get_approval_queue


class PatternType(str, Enum):
    """Types of learnable patterns."""
    TIME_PREFERENCE = "time_preference"      # When user is productive
    PRIORITY_STYLE = "priority_style"        # How user prioritizes
    TASK_CATEGORY = "task_category"          # Common task types
    COMMUNICATION_STYLE = "communication_style"  # Brief vs detailed
    WORK_PATTERN = "work_pattern"            # Work habits
    REMINDER_PREFERENCE = "reminder_preference"  # When/how to remind


class ImportanceLevel(str, Enum):
    """Importance levels for remembered context."""
    LOW = "low"         # Expires in 1 day
    MEDIUM = "medium"   # Expires in 7 days
    HIGH = "high"       # Expires in 30 days
    PERMANENT = "permanent"  # Never expires


# Memory type constants
MEMORY_TYPE_LEARNED_PATTERN = "learned_pattern"
MEMORY_TYPE_IMPORTANT_CONTEXT = "important_context"
MEMORY_TYPE_PREFERENCE_CHANGE = "preference_change"


@dataclass
class LearnedPattern:
    """A pattern learned about the user."""
    id: uuid.UUID
    user_id: uuid.UUID
    pattern_type: PatternType
    description: str
    confidence: float  # 0.0 to 1.0
    observation_count: int
    first_observed: datetime
    last_observed: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "pattern_type": self.pattern_type.value,
            "description": self.description,
            "confidence": self.confidence,
            "observation_count": self.observation_count,
            "first_observed": self.first_observed.isoformat(),
            "last_observed": self.last_observed.isoformat(),
        }


@dataclass
class ImportantContext:
    """Important context to remember for future conversations."""
    id: uuid.UUID
    user_id: uuid.UUID
    content: str
    importance: ImportanceLevel
    created_at: datetime
    expires_at: Optional[datetime]
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PreferenceUpdate:
    """A proposed preference update."""
    preference_key: str
    old_value: Any
    new_value: Any
    reason: str
    confidence: float
    requires_approval: bool


class LearningModule:
    """Handles agent-controlled learning and memory updates.

    The agent uses this module to:
    1. Store patterns it observes about user behavior
    2. Update preferences when confident
    3. Request approval for significant changes
    4. Remember important context
    """

    # Preferences that require user approval to change
    APPROVAL_REQUIRED_PREFERENCES = {
        "default_priority",
        "notification_preferences",
        "working_hours",
        "timezone",
        "auto_approve_actions",
    }

    # Minimum confidence to auto-update a preference
    AUTO_UPDATE_CONFIDENCE_THRESHOLD = 0.9

    # Minimum observations before storing a pattern
    MIN_OBSERVATIONS_TO_LEARN = 3

    def __init__(self, approval_queue: Optional[ApprovalQueue] = None):
        """Initialize the learning module.

        Args:
            approval_queue: Optional approval queue for preference changes.
        """
        self._approval_queue = approval_queue

    @property
    def approval_queue(self) -> ApprovalQueue:
        if self._approval_queue is None:
            self._approval_queue = get_approval_queue()
        return self._approval_queue

    async def store_learned_pattern(
        self,
        user_id: uuid.UUID,
        pattern_type: str,
        description: str,
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LearnedPattern:
        """Store a learned pattern about the user.

        Called by the agent when it notices a behavioral pattern.

        Args:
            user_id: The user's ID.
            pattern_type: Type of pattern (from PatternType enum).
            description: Human-readable description of the pattern.
            confidence: Confidence level (0.0 to 1.0).
            metadata: Optional additional data about the pattern.

        Returns:
            The stored LearnedPattern.
        """
        # Validate pattern type
        try:
            ptype = PatternType(pattern_type)
        except ValueError:
            ptype = PatternType.WORK_PATTERN  # Default

        # Check if pattern already exists
        existing = await self._get_existing_pattern(user_id, ptype, description)

        async with get_async_session() as session:
            if existing:
                # Update existing pattern
                existing_memory = await session.get(Memory, existing.id)
                if existing_memory:
                    # Increase observation count and update confidence
                    obs_count = existing.observation_count + 1
                    new_confidence = min(1.0, (existing.confidence + confidence) / 2 + 0.05)

                    existing_memory.metadata = {
                        **(existing_memory.metadata or {}),
                        "pattern_type": ptype.value,
                        "confidence": new_confidence,
                        "observation_count": obs_count,
                        "last_observed": datetime.utcnow().isoformat(),
                        **(metadata or {}),
                    }
                    await session.commit()

                    return LearnedPattern(
                        id=existing.id,
                        user_id=user_id,
                        pattern_type=ptype,
                        description=description,
                        confidence=new_confidence,
                        observation_count=obs_count,
                        first_observed=existing.first_observed,
                        last_observed=datetime.utcnow(),
                        metadata=existing_memory.metadata,
                    )

            # Create new pattern
            now = datetime.utcnow()
            memory = Memory(
                user_id=user_id,
                memory_type=MEMORY_TYPE_LEARNED_PATTERN,
                source_type="agent_learning",
                content=description,
                metadata={
                    "pattern_type": ptype.value,
                    "confidence": confidence,
                    "observation_count": 1,
                    "first_observed": now.isoformat(),
                    "last_observed": now.isoformat(),
                    **(metadata or {}),
                },
            )
            session.add(memory)
            await session.commit()
            await session.refresh(memory)

            return LearnedPattern(
                id=memory.id,
                user_id=user_id,
                pattern_type=ptype,
                description=description,
                confidence=confidence,
                observation_count=1,
                first_observed=now,
                last_observed=now,
                metadata=memory.metadata,
            )

    async def _get_existing_pattern(
        self,
        user_id: uuid.UUID,
        pattern_type: PatternType,
        description: str,
    ) -> Optional[LearnedPattern]:
        """Check if a similar pattern already exists."""
        async with get_async_session() as session:
            result = await session.execute(
                select(Memory).where(
                    Memory.user_id == user_id,
                    Memory.memory_type == MEMORY_TYPE_LEARNED_PATTERN,
                    Memory.content == description,
                )
            )
            memory = result.scalar_one_or_none()

            if memory and memory.metadata:
                return LearnedPattern(
                    id=memory.id,
                    user_id=user_id,
                    pattern_type=pattern_type,
                    description=memory.content,
                    confidence=memory.metadata.get("confidence", 0.5),
                    observation_count=memory.metadata.get("observation_count", 1),
                    first_observed=datetime.fromisoformat(
                        memory.metadata.get("first_observed", datetime.utcnow().isoformat())
                    ),
                    last_observed=datetime.fromisoformat(
                        memory.metadata.get("last_observed", datetime.utcnow().isoformat())
                    ),
                    metadata=memory.metadata,
                )
        return None

    async def update_user_preference(
        self,
        user_id: uuid.UUID,
        preference_key: str,
        new_value: Any,
        reason: str,
        confidence: float = 0.8,
    ) -> PreferenceUpdate:
        """Update a user preference based on observed behavior.

        If the preference requires approval, queues it for user confirmation.
        If confidence is high enough and approval not required, updates directly.

        Args:
            user_id: The user's ID.
            preference_key: The preference to update.
            new_value: The new value.
            reason: Why this change is being proposed.
            confidence: Confidence level (0.0 to 1.0).

        Returns:
            PreferenceUpdate with the result.
        """
        requires_approval = (
            preference_key in self.APPROVAL_REQUIRED_PREFERENCES or
            confidence < self.AUTO_UPDATE_CONFIDENCE_THRESHOLD
        )

        async with get_async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            old_value = (user.preferences or {}).get(preference_key)

            update = PreferenceUpdate(
                preference_key=preference_key,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                confidence=confidence,
                requires_approval=requires_approval,
            )

            if requires_approval:
                # Queue for approval
                await self.approval_queue.queue_action(
                    user_id=user_id,
                    action_name="preference.update",
                    action_data={
                        "preference_key": preference_key,
                        "old_value": old_value,
                        "new_value": new_value,
                        "reason": reason,
                        "confidence": confidence,
                    },
                    description=f"Update preference '{preference_key}' to '{new_value}'. Reason: {reason}",
                )
            else:
                # Auto-update
                preferences = user.preferences or {}
                preferences[preference_key] = new_value
                user.preferences = preferences
                await session.commit()

                # Log the change
                await self._log_preference_change(
                    user_id, preference_key, old_value, new_value, reason, "auto"
                )

            return update

    async def _log_preference_change(
        self,
        user_id: uuid.UUID,
        key: str,
        old_value: Any,
        new_value: Any,
        reason: str,
        method: str,
    ) -> None:
        """Log a preference change to memory."""
        async with get_async_session() as session:
            memory = Memory(
                user_id=user_id,
                memory_type=MEMORY_TYPE_PREFERENCE_CHANGE,
                source_type="agent_learning",
                content=f"Changed {key} from {old_value} to {new_value}",
                metadata={
                    "preference_key": key,
                    "old_value": old_value,
                    "new_value": new_value,
                    "reason": reason,
                    "method": method,  # "auto" or "approved"
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            session.add(memory)
            await session.commit()

    async def remember_important_context(
        self,
        user_id: uuid.UUID,
        content: str,
        importance: str = "medium",
        tags: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
    ) -> ImportantContext:
        """Store important context for future conversations.

        Called by the agent when it encounters information worth remembering.

        Args:
            user_id: The user's ID.
            content: The context to remember.
            importance: Importance level ("low", "medium", "high", "permanent").
            tags: Optional tags for retrieval.
            expires_in_days: Custom expiration (overrides importance default).

        Returns:
            The stored ImportantContext.
        """
        # Validate importance
        try:
            imp_level = ImportanceLevel(importance)
        except ValueError:
            imp_level = ImportanceLevel.MEDIUM

        # Calculate expiration
        if expires_in_days is not None:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        elif imp_level == ImportanceLevel.LOW:
            expires_at = datetime.utcnow() + timedelta(days=1)
        elif imp_level == ImportanceLevel.MEDIUM:
            expires_at = datetime.utcnow() + timedelta(days=7)
        elif imp_level == ImportanceLevel.HIGH:
            expires_at = datetime.utcnow() + timedelta(days=30)
        else:  # PERMANENT
            expires_at = None

        async with get_async_session() as session:
            memory = Memory(
                user_id=user_id,
                memory_type=MEMORY_TYPE_IMPORTANT_CONTEXT,
                source_type="agent_learning",
                content=content,
                metadata={
                    "importance": imp_level.value,
                    "tags": tags or [],
                    "expires_at": expires_at.isoformat() if expires_at else None,
                },
            )
            session.add(memory)
            await session.commit()
            await session.refresh(memory)

            return ImportantContext(
                id=memory.id,
                user_id=user_id,
                content=content,
                importance=imp_level,
                created_at=memory.created_at,
                expires_at=expires_at,
                tags=tags or [],
                metadata=memory.metadata,
            )

    async def get_learned_patterns(
        self,
        user_id: uuid.UUID,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[LearnedPattern]:
        """Get all learned patterns for a user.

        Args:
            user_id: The user's ID.
            pattern_type: Optional filter by pattern type.
            min_confidence: Minimum confidence threshold.

        Returns:
            List of LearnedPattern objects.
        """
        async with get_async_session() as session:
            query = select(Memory).where(
                Memory.user_id == user_id,
                Memory.memory_type == MEMORY_TYPE_LEARNED_PATTERN,
            )

            result = await session.execute(query)
            memories = result.scalars().all()

            patterns = []
            for memory in memories:
                if not memory.metadata:
                    continue

                confidence = memory.metadata.get("confidence", 0.0)
                if confidence < min_confidence:
                    continue

                ptype_str = memory.metadata.get("pattern_type", "work_pattern")
                if pattern_type and ptype_str != pattern_type:
                    continue

                try:
                    ptype = PatternType(ptype_str)
                except ValueError:
                    ptype = PatternType.WORK_PATTERN

                patterns.append(LearnedPattern(
                    id=memory.id,
                    user_id=user_id,
                    pattern_type=ptype,
                    description=memory.content,
                    confidence=confidence,
                    observation_count=memory.metadata.get("observation_count", 1),
                    first_observed=datetime.fromisoformat(
                        memory.metadata.get("first_observed", memory.created_at.isoformat())
                    ),
                    last_observed=datetime.fromisoformat(
                        memory.metadata.get("last_observed", memory.created_at.isoformat())
                    ),
                    metadata=memory.metadata,
                ))

            return sorted(patterns, key=lambda p: -p.confidence)

    async def get_important_context(
        self,
        user_id: uuid.UUID,
        tags: Optional[List[str]] = None,
        include_expired: bool = False,
    ) -> List[ImportantContext]:
        """Get important context for a user.

        Args:
            user_id: The user's ID.
            tags: Optional filter by tags.
            include_expired: Whether to include expired context.

        Returns:
            List of ImportantContext objects.
        """
        async with get_async_session() as session:
            query = select(Memory).where(
                Memory.user_id == user_id,
                Memory.memory_type == MEMORY_TYPE_IMPORTANT_CONTEXT,
            ).order_by(Memory.created_at.desc())

            result = await session.execute(query)
            memories = result.scalars().all()

            contexts = []
            now = datetime.utcnow()

            for memory in memories:
                if not memory.metadata:
                    continue

                expires_at_str = memory.metadata.get("expires_at")
                expires_at = datetime.fromisoformat(expires_at_str) if expires_at_str else None

                # Skip expired unless requested
                if not include_expired and expires_at and expires_at < now:
                    continue

                # Filter by tags if specified
                mem_tags = memory.metadata.get("tags", [])
                if tags and not any(t in mem_tags for t in tags):
                    continue

                try:
                    importance = ImportanceLevel(memory.metadata.get("importance", "medium"))
                except ValueError:
                    importance = ImportanceLevel.MEDIUM

                contexts.append(ImportantContext(
                    id=memory.id,
                    user_id=user_id,
                    content=memory.content,
                    importance=importance,
                    created_at=memory.created_at,
                    expires_at=expires_at,
                    tags=mem_tags,
                    metadata=memory.metadata,
                ))

            return contexts

    async def analyze_and_learn(
        self,
        user_id: uuid.UUID,
        recent_days: int = 7,
    ) -> List[LearnedPattern]:
        """Analyze recent behavior and learn patterns.

        This method analyzes task completion patterns and learns from them.
        Called periodically or when agent decides to learn.

        Args:
            user_id: The user's ID.
            recent_days: Days of history to analyze.

        Returns:
            List of newly learned or updated patterns.
        """
        patterns_learned = []
        cutoff = datetime.utcnow() - timedelta(days=recent_days)

        async with get_async_session() as session:
            # Get completed tasks
            result = await session.execute(
                select(Task).where(
                    Task.user_id == user_id,
                    Task.status == TaskStatus.COMPLETED,
                    Task.completed_at >= cutoff,
                    Task.completed_at.isnot(None),
                )
            )
            completed_tasks = result.scalars().all()

            if len(completed_tasks) < self.MIN_OBSERVATIONS_TO_LEARN:
                return patterns_learned

            # Analyze completion time patterns
            completion_hours = [
                task.completed_at.hour
                for task in completed_tasks
                if task.completed_at
            ]

            if completion_hours:
                # Find peak productivity time
                morning = sum(1 for h in completion_hours if 6 <= h < 12)
                afternoon = sum(1 for h in completion_hours if 12 <= h < 17)
                evening = sum(1 for h in completion_hours if 17 <= h < 22)

                total = len(completion_hours)

                if morning / total > 0.5:
                    pattern = await self.store_learned_pattern(
                        user_id=user_id,
                        pattern_type=PatternType.TIME_PREFERENCE.value,
                        description="Most productive in the morning (6am-12pm)",
                        confidence=morning / total,
                        metadata={"morning_ratio": morning / total},
                    )
                    patterns_learned.append(pattern)
                elif afternoon / total > 0.5:
                    pattern = await self.store_learned_pattern(
                        user_id=user_id,
                        pattern_type=PatternType.TIME_PREFERENCE.value,
                        description="Most productive in the afternoon (12pm-5pm)",
                        confidence=afternoon / total,
                        metadata={"afternoon_ratio": afternoon / total},
                    )
                    patterns_learned.append(pattern)
                elif evening / total > 0.5:
                    pattern = await self.store_learned_pattern(
                        user_id=user_id,
                        pattern_type=PatternType.TIME_PREFERENCE.value,
                        description="Most productive in the evening (5pm-10pm)",
                        confidence=evening / total,
                        metadata={"evening_ratio": evening / total},
                    )
                    patterns_learned.append(pattern)

            # Analyze priority preferences
            priorities = [task.priority for task in completed_tasks if task.priority]
            if priorities:
                avg_priority = sum(priorities) / len(priorities)
                high_priority_ratio = sum(1 for p in priorities if p >= 4) / len(priorities)

                if high_priority_ratio > 0.6:
                    pattern = await self.store_learned_pattern(
                        user_id=user_id,
                        pattern_type=PatternType.PRIORITY_STYLE.value,
                        description="Tends to focus on high-priority tasks first",
                        confidence=high_priority_ratio,
                        metadata={"high_priority_ratio": high_priority_ratio},
                    )
                    patterns_learned.append(pattern)

            # Analyze common tags/categories
            all_tags = []
            for task in completed_tasks:
                all_tags.extend(task.tags or [])

            if all_tags:
                tag_counts = {}
                for tag in all_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

                # Find dominant category
                top_tag, top_count = max(tag_counts.items(), key=lambda x: x[1])
                tag_ratio = top_count / len(completed_tasks)

                if tag_ratio > 0.3:  # Tag appears in 30%+ of tasks
                    pattern = await self.store_learned_pattern(
                        user_id=user_id,
                        pattern_type=PatternType.TASK_CATEGORY.value,
                        description=f"Frequently works on '{top_tag}' related tasks",
                        confidence=tag_ratio,
                        metadata={"top_tag": top_tag, "frequency": tag_ratio},
                    )
                    patterns_learned.append(pattern)

        return patterns_learned

    async def forget_pattern(
        self,
        user_id: uuid.UUID,
        pattern_id: uuid.UUID,
    ) -> bool:
        """Forget a learned pattern.

        Args:
            user_id: The user's ID.
            pattern_id: The pattern's ID.

        Returns:
            True if pattern was deleted.
        """
        async with get_async_session() as session:
            memory = await session.get(Memory, pattern_id)
            if memory and memory.user_id == user_id:
                await session.delete(memory)
                await session.commit()
                return True
        return False

    async def cleanup_expired_context(
        self,
        user_id: uuid.UUID,
    ) -> int:
        """Remove expired important context.

        Args:
            user_id: The user's ID.

        Returns:
            Number of items removed.
        """
        now = datetime.utcnow()
        removed = 0

        async with get_async_session() as session:
            result = await session.execute(
                select(Memory).where(
                    Memory.user_id == user_id,
                    Memory.memory_type == MEMORY_TYPE_IMPORTANT_CONTEXT,
                )
            )
            memories = result.scalars().all()

            for memory in memories:
                if memory.metadata:
                    expires_at_str = memory.metadata.get("expires_at")
                    if expires_at_str:
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at < now:
                            await session.delete(memory)
                            removed += 1

            await session.commit()

        return removed


# Global instance
_learning_module: Optional[LearningModule] = None


def get_learning_module() -> LearningModule:
    """Get the global learning module instance."""
    global _learning_module
    if _learning_module is None:
        _learning_module = LearningModule()
    return _learning_module
