"""Learning Tools - Agent-callable tools for memory and preference management.

These tools allow the agent to:
- Store patterns it observes about user behavior
- Update user preferences based on observations
- Remember important context for future conversations
- Analyze behavior and learn patterns
"""

import json
import uuid
from typing import Optional

from agents import function_tool

from src.memory.learning import (
    get_learning_module,
    PatternType,
    ImportanceLevel,
)


@function_tool
async def store_learned_pattern(
    user_id: str,
    pattern_type: str,
    description: str,
    confidence: float,
) -> str:
    """Store a learned pattern about the user's behavior.

    Call this when you observe a consistent pattern in the user's behavior.
    Patterns are accumulated over time - calling multiple times with the same
    description increases confidence.

    Args:
        user_id: The user's UUID as a string.
        pattern_type: Type of pattern. One of:
            - "time_preference": When user is most productive
            - "priority_style": How user prioritizes tasks
            - "task_category": Common task types
            - "communication_style": Brief vs detailed preference
            - "work_pattern": General work habits
            - "reminder_preference": When/how to remind
        description: Human-readable description of the pattern.
            Example: "Prefers to complete high-priority tasks in the morning"
        confidence: How confident you are (0.0 to 1.0).
            Use 0.5-0.7 for initial observations, 0.8+ for consistent patterns.

    Returns:
        JSON string with pattern details including id, observation_count, and confidence.

    Example:
        >>> await store_learned_pattern(
        ...     user_id="abc-123",
        ...     pattern_type="time_preference",
        ...     description="Most productive before 10am",
        ...     confidence=0.75
        ... )
    """
    learning = get_learning_module()
    pattern = await learning.store_learned_pattern(
        user_id=uuid.UUID(user_id),
        pattern_type=pattern_type,
        description=description,
        confidence=confidence,
    )
    return json.dumps(pattern.to_dict(), default=str)


@function_tool
async def update_user_preference(
    user_id: str,
    preference_key: str,
    new_value: str,
    reason: str,
    confidence: float = 0.8,
) -> str:
    """Update a user preference based on observed behavior.

    Some preferences require user approval before changing:
    - default_priority, notification_preferences, working_hours, timezone

    Other preferences can be auto-updated if confidence is >= 0.9.

    Args:
        user_id: The user's UUID as a string.
        preference_key: The preference to update. Common keys:
            - "default_priority": Default task priority (1-5)
            - "working_hours": e.g., "9am-5pm"
            - "timezone": e.g., "America/New_York"
            - "default_reminder_time": e.g., "30m", "1h"
            - "preferred_task_view": "list", "calendar", "kanban"
            - "communication_style": "brief", "detailed"
        new_value: The new value (as string, will be parsed appropriately).
        reason: Why you're proposing this change. Be specific.
            Example: "User has completed 8/10 recent tasks before 10am"
        confidence: How confident you are (0.0 to 1.0).

    Returns:
        JSON string with:
            - preference_key: The key that was updated
            - old_value: Previous value
            - new_value: New value
            - requires_approval: Whether user approval is needed
            - reason: The reason provided

    Example:
        >>> await update_user_preference(
        ...     user_id="abc-123",
        ...     preference_key="working_hours",
        ...     new_value="8am-4pm",
        ...     reason="User consistently completes tasks between 8am-4pm",
        ...     confidence=0.85
        ... )
    """
    learning = get_learning_module()
    result = await learning.update_user_preference(
        user_id=uuid.UUID(user_id),
        preference_key=preference_key,
        new_value=new_value,
        reason=reason,
        confidence=confidence,
    )
    return json.dumps({
        "preference_key": result.preference_key,
        "old_value": result.old_value,
        "new_value": result.new_value,
        "requires_approval": result.requires_approval,
        "reason": result.reason,
        "confidence": result.confidence,
    }, default=str)


@function_tool
async def remember_important_context(
    user_id: str,
    content: str,
    importance: str = "medium",
    tags_json: Optional[str] = None,
    expires_in_days: Optional[int] = None,
) -> str:
    """Store important context for future conversations.

    Use this to remember information that will be useful later:
    - Project deadlines
    - User's current focus areas
    - Important upcoming events
    - Temporary preferences

    Args:
        user_id: The user's UUID as a string.
        content: The context to remember.
            Example: "User is preparing for Q4 board presentation on Dec 15"
        importance: How important this context is:
            - "low": Expires in 1 day
            - "medium": Expires in 7 days
            - "high": Expires in 30 days
            - "permanent": Never expires
        tags_json: Optional JSON array of tags for easier retrieval.
            Example: '["project", "deadline", "q4"]'
        expires_in_days: Custom expiration (overrides importance default).

    Returns:
        JSON string with context details including id and expiration.

    Example:
        >>> await remember_important_context(
        ...     user_id="abc-123",
        ...     content="User mentioned they're on vacation next week",
        ...     importance="high",
        ...     tags_json='["vacation", "schedule"]'
        ... )
    """
    tags = None
    if tags_json:
        try:
            tags = json.loads(tags_json)
        except json.JSONDecodeError:
            pass

    learning = get_learning_module()
    context = await learning.remember_important_context(
        user_id=uuid.UUID(user_id),
        content=content,
        importance=importance,
        tags=tags,
        expires_in_days=expires_in_days,
    )
    return json.dumps({
        "id": str(context.id),
        "content": context.content,
        "importance": context.importance.value,
        "created_at": context.created_at.isoformat(),
        "expires_at": context.expires_at.isoformat() if context.expires_at else None,
        "tags": context.tags,
    }, default=str)


@function_tool
async def get_user_patterns(
    user_id: str,
    pattern_type: Optional[str] = None,
    min_confidence: float = 0.5,
) -> str:
    """Get learned patterns about the user.

    Use this to retrieve what you've learned about the user's behavior
    to inform your responses and suggestions.

    Args:
        user_id: The user's UUID as a string.
        pattern_type: Optional filter by type (see store_learned_pattern).
        min_confidence: Minimum confidence threshold (default 0.5).

    Returns:
        JSON string of list of pattern dicts, sorted by confidence (highest first).

    Example:
        >>> patterns = await get_user_patterns(
        ...     user_id="abc-123",
        ...     pattern_type="time_preference"
        ... )
        >>> # Returns: '[{"description": "Most productive before 10am", "confidence": 0.85, ...}]'
    """
    learning = get_learning_module()
    patterns = await learning.get_learned_patterns(
        user_id=uuid.UUID(user_id),
        pattern_type=pattern_type,
        min_confidence=min_confidence,
    )
    return json.dumps([p.to_dict() for p in patterns], default=str)


@function_tool
async def get_important_context(
    user_id: str,
    tags_json: Optional[str] = None,
) -> str:
    """Get important context remembered for the user.

    Use this to retrieve context that was stored for future reference.

    Args:
        user_id: The user's UUID as a string.
        tags_json: Optional JSON array of tags to filter by.

    Returns:
        JSON string of list of context items (non-expired), most recent first.

    Example:
        >>> context = await get_important_context(
        ...     user_id="abc-123",
        ...     tags_json='["deadline"]'
        ... )
    """
    tags = None
    if tags_json:
        try:
            tags = json.loads(tags_json)
        except json.JSONDecodeError:
            pass

    learning = get_learning_module()
    contexts = await learning.get_important_context(
        user_id=uuid.UUID(user_id),
        tags=tags,
        include_expired=False,
    )
    return json.dumps([
        {
            "id": str(c.id),
            "content": c.content,
            "importance": c.importance.value,
            "created_at": c.created_at.isoformat(),
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "tags": c.tags,
        }
        for c in contexts
    ], default=str)


@function_tool
async def analyze_and_learn_patterns(
    user_id: str,
    recent_days: int = 7,
) -> str:
    """Analyze recent user behavior and learn patterns.

    Call this periodically or when you want to update your understanding
    of the user's behavior. Analyzes:
    - Task completion times
    - Priority preferences
    - Common task categories

    Args:
        user_id: The user's UUID as a string.
        recent_days: Number of days to analyze (default 7).

    Returns:
        JSON string with:
            - patterns_learned: Number of patterns learned/updated
            - patterns: List of pattern details

    Example:
        >>> result = await analyze_and_learn_patterns(user_id="abc-123")
        >>> # Returns: '{"patterns_learned": 2, "patterns": [...]}'
    """
    learning = get_learning_module()
    patterns = await learning.analyze_and_learn(
        user_id=uuid.UUID(user_id),
        recent_days=recent_days,
    )
    return json.dumps({
        "patterns_learned": len(patterns),
        "patterns": [p.to_dict() for p in patterns],
    }, default=str)


@function_tool
async def forget_learned_pattern(
    user_id: str,
    pattern_id: str,
) -> str:
    """Forget a learned pattern.

    Use this if a pattern is no longer accurate or the user requests it.

    Args:
        user_id: The user's UUID as a string.
        pattern_id: The pattern's UUID to forget.

    Returns:
        JSON string with success status.
    """
    learning = get_learning_module()
    success = await learning.forget_pattern(
        user_id=uuid.UUID(user_id),
        pattern_id=uuid.UUID(pattern_id),
    )
    return json.dumps({"success": success})


# Export all tools
LEARNING_TOOLS = [
    store_learned_pattern,
    update_user_preference,
    remember_important_context,
    get_user_patterns,
    get_important_context,
    analyze_and_learn_patterns,
    forget_learned_pattern,
]
