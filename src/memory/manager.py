"""Memory Manager - Coordinates all memory tiers.

Provides a unified interface to hot, warm, and cold memory.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from config.settings import get_settings
from src.memory.hot import HotMemory, HotMemoryState
from src.memory.warm import WarmMemory, WarmMemoryResult
from src.memory.cold import ColdMemory, ColdQueryResult


settings = get_settings()


@dataclass
class MemoryContext:
    """Combined memory context for LLM."""
    hot: HotMemoryState
    warm: Optional[WarmMemoryResult] = None
    cold_available: bool = True  # Indicates cold memory is available via skills
    total_tokens: int = 0


class MemoryManager:
    """Coordinates all memory tiers.

    Provides a unified interface for:
    - Managing hot memory (always in context)
    - Retrieving warm memory (on-demand)
    - Querying cold memory (via skills)
    - Compacting and archiving old data
    """

    def __init__(
        self,
        hot_max_tokens: int = None,
        warm_max_items: int = None,
        hot_max_turns: int = 10,
    ):
        """Initialize the memory manager.

        Args:
            hot_max_tokens: Max tokens for hot memory.
            warm_max_items: Max items for warm memory.
            hot_max_turns: Max conversation turns in hot memory.
        """
        self.hot = HotMemory(
            max_tokens=hot_max_tokens or settings.hot_memory_max_tokens,
            max_turns=hot_max_turns,
        )
        self.warm = WarmMemory(
            max_items=warm_max_items or settings.warm_memory_max_items,
        )
        self.cold = ColdMemory()

    def initialize_session(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> HotMemoryState:
        """Initialize memory for a new session.

        Args:
            session_id: The session ID.
            user_id: The user ID.
            preferences: Optional user preferences.

        Returns:
            The initialized hot memory state.
        """
        return self.hot.initialize(
            session_id=session_id,
            user_id=user_id,
            preferences=preferences,
        )

    def add_message(
        self,
        role: str,
        content: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a message to hot memory.

        Args:
            role: Message role (user, assistant, system).
            content: Message content.
            timestamp: Optional timestamp.
        """
        self.hot.add_turn(role, content, timestamp)

    def set_active_task(self, task: Optional[Dict[str, Any]]) -> None:
        """Set the currently active task.

        Args:
            task: Task dictionary or None.
        """
        self.hot.set_active_task(task)

    def update_session(
        self,
        intent: Optional[str] = None,
        pending_action: Optional[str] = None,
        awaiting_confirmation: Optional[bool] = None,
    ) -> None:
        """Update session state.

        Args:
            intent: Current intent.
            pending_action: Pending action.
            awaiting_confirmation: Whether awaiting confirmation.
        """
        self.hot.update_session_state(
            intent=intent,
            pending_action=pending_action,
            awaiting_confirmation=awaiting_confirmation,
        )

    async def get_context(
        self,
        user_id: uuid.UUID,
        include_warm: bool = True,
        query: Optional[str] = None,
    ) -> MemoryContext:
        """Get combined memory context.

        Args:
            user_id: The user's ID.
            include_warm: Whether to include warm memory.
            query: Optional query for warm memory retrieval.

        Returns:
            MemoryContext with all available memory.
        """
        hot_state = self.hot.get_state()
        if not hot_state:
            raise RuntimeError("Memory not initialized for session")

        warm_result = None
        if include_warm:
            # Get active task ID if available
            task_id = None
            if hot_state.active_task:
                task_id = hot_state.active_task.id

            warm_result = await self.warm.retrieve(
                user_id=user_id,
                query=query,
                task_id=task_id,
            )

        # Calculate total tokens
        total_tokens = hot_state.token_count
        if warm_result:
            total_tokens += warm_result.token_estimate

        return MemoryContext(
            hot=hot_state,
            warm=warm_result,
            cold_available=True,
            total_tokens=total_tokens,
        )

    def get_llm_context(self) -> Dict[str, Any]:
        """Get formatted context for LLM.

        Returns:
            Dictionary suitable for LLM context.
        """
        return self.hot.get_context_for_llm()

    async def get_llm_context_with_warm(
        self,
        user_id: uuid.UUID,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get formatted context including warm memory.

        Args:
            user_id: The user's ID.
            query: Optional query for relevance.

        Returns:
            Dictionary suitable for LLM context.
        """
        context = self.hot.get_context_for_llm()

        # Add warm memory
        hot_state = self.hot.get_state()
        task_id = hot_state.active_task.id if hot_state and hot_state.active_task else None

        warm_result = await self.warm.retrieve(
            user_id=user_id,
            query=query,
            task_id=task_id,
        )

        if warm_result.recent_tasks:
            context["recent_tasks"] = warm_result.recent_tasks[:5]

        if warm_result.user_patterns:
            context["user_patterns"] = warm_result.user_patterns

        if warm_result.related_tasks:
            context["related_tasks"] = warm_result.related_tasks[:3]

        return context

    async def query_history(
        self,
        user_id: uuid.UUID,
        filters: Optional[Dict[str, Any]] = None,
        search_text: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ColdQueryResult:
        """Query cold memory for task history.

        Args:
            user_id: The user's ID.
            filters: Optional filters.
            search_text: Optional search text.
            limit: Max results.
            offset: Result offset.

        Returns:
            ColdQueryResult with matching items.
        """
        return await self.cold.query_tasks(
            user_id=user_id,
            filters=filters,
            search_text=search_text,
            limit=limit,
            offset=offset,
        )

    async def get_statistics(
        self,
        user_id: uuid.UUID,
        days_back: int = 30,
    ) -> Dict[str, Any]:
        """Get user statistics from cold memory.

        Args:
            user_id: The user's ID.
            days_back: Days to analyze.

        Returns:
            Statistics dictionary.
        """
        return await self.cold.get_task_statistics(
            user_id=user_id,
            days_back=days_back,
        )

    async def save_conversation_summary(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        """Save current conversation summary to warm memory.

        Args:
            user_id: The user's ID.
            session_id: The session ID.
        """
        summary = self.hot.summarize_conversation()
        if summary and summary != "No conversation yet.":
            await self.warm.store_summary(
                user_id=user_id,
                session_id=session_id,
                summary=summary,
            )

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
        await self.warm.store_pattern(
            user_id=user_id,
            pattern_type=pattern_type,
            content=content,
        )

    async def archive_old_data(
        self,
        user_id: uuid.UUID,
        days_old: int = 90,
    ) -> Dict[str, int]:
        """Archive old data to save space.

        Args:
            user_id: The user's ID.
            days_old: Archive data older than this.

        Returns:
            Counts of archived items.
        """
        return await self.cold.archive_old_data(
            user_id=user_id,
            days_old=days_old,
        )

    def clear_hot_memory(self) -> None:
        """Clear hot memory (end of session)."""
        self.hot.clear()


# Global instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


def set_memory_manager(manager: MemoryManager) -> None:
    """Set the global memory manager (for testing)."""
    global _memory_manager
    _memory_manager = manager
