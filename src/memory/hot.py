"""Hot Memory - In-context memory for current conversation.

Always loaded, updated every turn. Contains:
- Current conversation (last few turns)
- Active task being discussed
- User's core preferences (compact summary)
- Current session state
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from config.settings import get_settings


settings = get_settings()


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    token_estimate: int = 0


@dataclass
class ActiveTask:
    """The task currently being discussed."""
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: str = "pending"
    priority: int = 3
    due_date: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class UserPreferencesSummary:
    """Compact summary of user preferences."""
    working_hours: Optional[str] = None  # e.g., "9am-5pm"
    timezone: str = "UTC"
    priority_keywords: List[str] = field(default_factory=list)
    default_reminder_time: str = "30m"  # Before due date
    preferred_task_view: str = "list"  # "list", "calendar", "kanban"
    notification_preferences: Dict[str, bool] = field(default_factory=lambda: {
        "email": True,
        "push": True,
        "sms": False,
    })


@dataclass
class SessionState:
    """Current session state."""
    session_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    current_intent: Optional[str] = None
    pending_action: Optional[str] = None
    awaiting_confirmation: bool = False
    context_flags: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HotMemoryState:
    """Complete hot memory state."""
    conversation: List[ConversationTurn]
    active_task: Optional[ActiveTask]
    preferences: UserPreferencesSummary
    session: SessionState
    token_count: int = 0
    max_tokens: int = 1000


class HotMemory:
    """In-context memory manager.

    Manages the hot memory tier which is always present in the context.
    Keeps token count within limits by summarizing or truncating.
    """

    def __init__(
        self,
        max_tokens: int = None,
        max_turns: int = 10,
    ):
        """Initialize hot memory.

        Args:
            max_tokens: Maximum tokens to use for hot memory.
            max_turns: Maximum conversation turns to keep.
        """
        self.max_tokens = max_tokens or settings.hot_memory_max_tokens
        self.max_turns = max_turns
        self._state: Optional[HotMemoryState] = None

    def initialize(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> HotMemoryState:
        """Initialize hot memory for a new session.

        Args:
            session_id: The session ID.
            user_id: The user ID.
            preferences: Optional user preferences.

        Returns:
            Initialized HotMemoryState.
        """
        user_prefs = UserPreferencesSummary()
        if preferences:
            if "working_hours" in preferences:
                user_prefs.working_hours = preferences["working_hours"]
            if "timezone" in preferences:
                user_prefs.timezone = preferences["timezone"]
            if "priority_keywords" in preferences:
                user_prefs.priority_keywords = preferences["priority_keywords"]
            if "default_reminder_time" in preferences:
                user_prefs.default_reminder_time = preferences["default_reminder_time"]

        self._state = HotMemoryState(
            conversation=[],
            active_task=None,
            preferences=user_prefs,
            session=SessionState(
                session_id=session_id,
                user_id=user_id,
            ),
            max_tokens=self.max_tokens,
        )

        return self._state

    def add_turn(
        self,
        role: str,
        content: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Add a conversation turn to hot memory.

        Args:
            role: The role (user, assistant, system).
            content: The message content.
            timestamp: Optional timestamp.
        """
        if not self._state:
            raise RuntimeError("Hot memory not initialized")

        # Estimate tokens (roughly 4 chars per token)
        token_estimate = len(content) // 4

        turn = ConversationTurn(
            role=role,
            content=content,
            timestamp=timestamp or datetime.utcnow(),
            token_estimate=token_estimate,
        )

        self._state.conversation.append(turn)
        self._state.token_count += token_estimate

        # Update last activity
        self._state.session.last_activity = datetime.utcnow()

        # Compact if needed
        self._compact_if_needed()

    def set_active_task(self, task: Optional[Dict[str, Any]]) -> None:
        """Set the currently active task.

        Args:
            task: Task dictionary or None to clear.
        """
        if not self._state:
            raise RuntimeError("Hot memory not initialized")

        if task is None:
            self._state.active_task = None
        else:
            self._state.active_task = ActiveTask(
                id=task.get("id", uuid.uuid4()),
                title=task.get("title", "Untitled"),
                description=task.get("description"),
                status=task.get("status", "pending"),
                priority=task.get("priority", 3),
                due_date=task.get("due_date"),
                tags=task.get("tags", []),
            )

    def update_session_state(
        self,
        intent: Optional[str] = None,
        pending_action: Optional[str] = None,
        awaiting_confirmation: Optional[bool] = None,
        context_flags: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update the session state.

        Args:
            intent: Current user intent.
            pending_action: Action awaiting completion.
            awaiting_confirmation: Whether confirmation is needed.
            context_flags: Additional context flags.
        """
        if not self._state:
            raise RuntimeError("Hot memory not initialized")

        if intent is not None:
            self._state.session.current_intent = intent
        if pending_action is not None:
            self._state.session.pending_action = pending_action
        if awaiting_confirmation is not None:
            self._state.session.awaiting_confirmation = awaiting_confirmation
        if context_flags is not None:
            self._state.session.context_flags.update(context_flags)

    def get_state(self) -> Optional[HotMemoryState]:
        """Get the current hot memory state.

        Returns:
            The current HotMemoryState or None if not initialized.
        """
        return self._state

    def get_context_for_llm(self) -> Dict[str, Any]:
        """Get hot memory formatted for LLM context.

        Returns:
            Dictionary with formatted context data.
        """
        if not self._state:
            return {}

        context = {
            "conversation": [
                {"role": t.role, "content": t.content}
                for t in self._state.conversation
            ],
            "session": {
                "session_id": str(self._state.session.session_id),
                "current_intent": self._state.session.current_intent,
                "awaiting_confirmation": self._state.session.awaiting_confirmation,
            },
        }

        # Add active task if present
        if self._state.active_task:
            context["active_task"] = {
                "id": str(self._state.active_task.id),
                "title": self._state.active_task.title,
                "status": self._state.active_task.status,
                "priority": self._state.active_task.priority,
            }
            if self._state.active_task.due_date:
                context["active_task"]["due_date"] = self._state.active_task.due_date.isoformat()

        # Add compact preferences
        prefs = self._state.preferences
        if prefs.working_hours or prefs.priority_keywords:
            context["user_preferences"] = {}
            if prefs.working_hours:
                context["user_preferences"]["working_hours"] = prefs.working_hours
            if prefs.priority_keywords:
                context["user_preferences"]["priority_keywords"] = prefs.priority_keywords

        return context

    def _compact_if_needed(self) -> None:
        """Compact conversation if over token limit."""
        if not self._state:
            return

        while (
            self._state.token_count > self.max_tokens
            and len(self._state.conversation) > 2
        ):
            # Remove oldest non-system turn
            for i, turn in enumerate(self._state.conversation):
                if turn.role != "system":
                    self._state.token_count -= turn.token_estimate
                    self._state.conversation.pop(i)
                    break

        # Also enforce max turns
        while len(self._state.conversation) > self.max_turns * 2:
            removed = self._state.conversation.pop(0)
            self._state.token_count -= removed.token_estimate

    def summarize_conversation(self) -> str:
        """Generate a summary of the current conversation.

        Returns:
            A text summary of the conversation.
        """
        if not self._state or not self._state.conversation:
            return "No conversation yet."

        # Simple extractive summary
        user_messages = [t.content for t in self._state.conversation if t.role == "user"]
        topics = []

        for msg in user_messages[-5:]:  # Last 5 user messages
            # Extract first sentence or phrase
            first_sentence = msg.split(".")[0].strip()
            if len(first_sentence) > 50:
                first_sentence = first_sentence[:50] + "..."
            topics.append(first_sentence)

        return f"User discussed: {'; '.join(topics)}"

    def clear(self) -> None:
        """Clear hot memory state."""
        self._state = None
