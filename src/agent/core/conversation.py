"""Conversation Handler - Interprets user intent and manages conversation context.

Responsibilities:
- Interprets user intent from natural language
- Manages multi-turn conversation context
- Handles session persistence and handoff
- Routes requests to appropriate components
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import Session as DBSession, User, SessionState
from src.database.connection import get_async_session


@dataclass
class ConversationMessage:
    """A single message in the conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Context for the current conversation turn."""
    session_id: uuid.UUID
    user_id: uuid.UUID
    message: str
    history: List[ConversationMessage]
    user_preferences: Dict[str, Any]
    active_tasks: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationHandler:
    """Handles conversation flow and context management.

    The conversation handler is responsible for:
    1. Loading/creating conversation sessions
    2. Managing conversation history (with truncation for context limits)
    3. Enriching context with user preferences and active tasks
    4. Persisting conversation state
    """

    def __init__(self, max_history_turns: int = 20):
        """Initialize the conversation handler.

        Args:
            max_history_turns: Maximum number of conversation turns to keep in memory.
        """
        self.max_history_turns = max_history_turns

    async def start_conversation(
        self,
        user_id: uuid.UUID,
        session_id: Optional[uuid.UUID] = None,
    ) -> ConversationContext:
        """Start or resume a conversation.

        Args:
            user_id: The user's ID.
            session_id: Optional session ID to resume.

        Returns:
            ConversationContext with loaded history and user data.
        """
        async with get_async_session() as session:
            # Get user preferences
            user = await session.get(User, user_id)
            user_preferences = user.preferences if user else {}

            # Get or create session
            db_session = None
            if session_id:
                result = await session.execute(
                    select(DBSession).where(
                        DBSession.id == session_id,
                        DBSession.user_id == user_id,
                    )
                )
                db_session = result.scalar_one_or_none()

            if not db_session:
                db_session = DBSession(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    state=SessionState.ACTIVE,
                    conversation_history=[],
                )
                session.add(db_session)
                await session.flush()

            # Convert history to ConversationMessage objects
            history = [
                ConversationMessage(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    timestamp=datetime.fromisoformat(msg["timestamp"]) if "timestamp" in msg else datetime.utcnow(),
                    metadata=msg.get("metadata", {}),
                )
                for msg in (db_session.conversation_history or [])
            ]

            return ConversationContext(
                session_id=db_session.id,
                user_id=user_id,
                message="",  # Will be set when processing
                history=history,
                user_preferences=user_preferences,
                active_tasks=[],  # Will be loaded separately
            )

    async def process_message(
        self,
        context: ConversationContext,
        message: str,
    ) -> ConversationContext:
        """Process an incoming user message.

        Args:
            context: The current conversation context.
            message: The user's message.

        Returns:
            Updated context with the new message added.
        """
        # Add message to context
        context.message = message
        context.history.append(
            ConversationMessage(
                role="user",
                content=message,
                timestamp=datetime.utcnow(),
            )
        )

        # Truncate history if needed
        if len(context.history) > self.max_history_turns * 2:
            # Keep system messages and last N turns
            system_messages = [m for m in context.history if m.role == "system"]
            other_messages = [m for m in context.history if m.role != "system"]
            context.history = system_messages + other_messages[-(self.max_history_turns * 2):]

        return context

    async def add_response(
        self,
        context: ConversationContext,
        response: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationContext:
        """Add an assistant response to the conversation.

        Args:
            context: The current conversation context.
            response: The assistant's response.
            metadata: Optional metadata (actions taken, etc.)

        Returns:
            Updated context with the response added.
        """
        context.history.append(
            ConversationMessage(
                role="assistant",
                content=response,
                timestamp=datetime.utcnow(),
                metadata=metadata or {},
            )
        )
        return context

    async def save_conversation(self, context: ConversationContext) -> None:
        """Persist the conversation to the database.

        Args:
            context: The conversation context to save.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(DBSession).where(DBSession.id == context.session_id)
            )
            db_session = result.scalar_one_or_none()

            if db_session:
                db_session.conversation_history = [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.metadata,
                    }
                    for msg in context.history
                ]
                db_session.last_activity = datetime.utcnow()

    async def end_conversation(self, context: ConversationContext) -> None:
        """End and save the conversation.

        Args:
            context: The conversation context to end.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(DBSession).where(DBSession.id == context.session_id)
            )
            db_session = result.scalar_one_or_none()

            if db_session:
                db_session.state = SessionState.ENDED
                db_session.ended_at = datetime.utcnow()
                db_session.conversation_history = [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.metadata,
                    }
                    for msg in context.history
                ]

    def get_context_summary(self, context: ConversationContext) -> str:
        """Generate a summary of the conversation context for the LLM.

        Args:
            context: The conversation context.

        Returns:
            A formatted string summary of the context.
        """
        parts = []

        # User preferences
        if context.user_preferences:
            prefs = context.user_preferences
            if prefs.get("working_hours"):
                parts.append(f"User's working hours: {prefs['working_hours']}")
            if prefs.get("priority_keywords"):
                parts.append(f"Priority keywords: {', '.join(prefs['priority_keywords'])}")

        # Active tasks summary
        if context.active_tasks:
            task_summary = f"User has {len(context.active_tasks)} active tasks"
            urgent = [t for t in context.active_tasks if t.get("priority", 0) >= 4]
            if urgent:
                task_summary += f" ({len(urgent)} high priority)"
            parts.append(task_summary)

        # Recent conversation topics
        recent_topics = self._extract_topics(context.history[-6:])
        if recent_topics:
            parts.append(f"Recent topics: {', '.join(recent_topics)}")

        return "\n".join(parts) if parts else "No additional context available."

    def _extract_topics(self, messages: List[ConversationMessage]) -> List[str]:
        """Extract key topics from recent messages.

        This is a simple keyword extraction. In production, this could
        use an LLM or more sophisticated NLP.

        Args:
            messages: Recent messages to analyze.

        Returns:
            List of extracted topic keywords.
        """
        topic_keywords = {
            "task": ["task", "todo", "work", "project"],
            "schedule": ["schedule", "due", "deadline", "today", "tomorrow", "week"],
            "priority": ["priority", "urgent", "important", "asap"],
            "reminder": ["remind", "reminder", "notify", "alert"],
            "search": ["find", "search", "look for", "where"],
            "help": ["help", "how", "what", "explain"],
        }

        found_topics = set()
        for msg in messages:
            content_lower = msg.content.lower()
            for topic, keywords in topic_keywords.items():
                if any(kw in content_lower for kw in keywords):
                    found_topics.add(topic)

        return list(found_topics)[:5]

    def format_history_for_llm(
        self,
        context: ConversationContext,
        max_tokens: int = 2000,
    ) -> List[Dict[str, str]]:
        """Format conversation history for LLM consumption.

        Args:
            context: The conversation context.
            max_tokens: Approximate max tokens to include.

        Returns:
            List of message dicts in OpenAI format.
        """
        messages = []

        # Estimate tokens (rough: 4 chars per token)
        total_chars = 0
        max_chars = max_tokens * 4

        # Start from most recent and work backwards
        for msg in reversed(context.history):
            msg_chars = len(msg.content)
            if total_chars + msg_chars > max_chars:
                break
            messages.insert(0, {
                "role": msg.role,
                "content": msg.content,
            })
            total_chars += msg_chars

        return messages
