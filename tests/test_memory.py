"""Tests for Memory System functionality."""

import uuid
from datetime import datetime
import pytest

from src.memory.hot import (
    HotMemory,
    HotMemoryState,
    ConversationTurn,
    ActiveTask,
    UserPreferencesSummary,
    SessionState,
)


class TestConversationTurn:
    """Tests for ConversationTurn dataclass."""

    def test_create_turn(self):
        """Test creating a conversation turn."""
        turn = ConversationTurn(
            role="user",
            content="Hello, how are you?",
        )
        assert turn.role == "user"
        assert turn.content == "Hello, how are you?"
        assert turn.timestamp is not None

    def test_turn_with_timestamp(self):
        """Test creating a turn with explicit timestamp."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        turn = ConversationTurn(
            role="assistant",
            content="I'm doing well!",
            timestamp=ts,
        )
        assert turn.timestamp == ts


class TestActiveTask:
    """Tests for ActiveTask dataclass."""

    def test_create_active_task(self):
        """Test creating an active task."""
        task_id = uuid.uuid4()
        task = ActiveTask(
            id=task_id,
            title="Complete project",
            description="Finish the AI project",
            status="in_progress",
            priority=5,
        )
        assert task.id == task_id
        assert task.title == "Complete project"
        assert task.priority == 5

    def test_active_task_defaults(self):
        """Test active task default values."""
        task = ActiveTask(
            id=uuid.uuid4(),
            title="Simple task",
        )
        assert task.status == "pending"
        assert task.priority == 3
        assert task.tags == []


class TestUserPreferencesSummary:
    """Tests for UserPreferencesSummary dataclass."""

    def test_default_preferences(self):
        """Test default user preferences."""
        prefs = UserPreferencesSummary()
        assert prefs.timezone == "UTC"
        assert prefs.default_reminder_time == "30m"
        assert prefs.preferred_task_view == "list"
        assert prefs.notification_preferences["email"] is True
        assert prefs.notification_preferences["push"] is True
        assert prefs.notification_preferences["sms"] is False

    def test_custom_preferences(self):
        """Test custom user preferences."""
        prefs = UserPreferencesSummary(
            working_hours="9am-6pm",
            timezone="America/New_York",
            priority_keywords=["urgent", "important"],
        )
        assert prefs.working_hours == "9am-6pm"
        assert prefs.timezone == "America/New_York"
        assert "urgent" in prefs.priority_keywords


class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_create_session_state(self):
        """Test creating session state."""
        session_id = uuid.uuid4()
        user_id = uuid.uuid4()
        state = SessionState(
            session_id=session_id,
            user_id=user_id,
        )
        assert state.session_id == session_id
        assert state.user_id == user_id
        assert state.current_intent is None
        assert state.awaiting_confirmation is False


class TestHotMemory:
    """Tests for HotMemory class."""

    def test_initialize(self):
        """Test initializing hot memory."""
        memory = HotMemory(max_tokens=1000, max_turns=10)
        session_id = uuid.uuid4()
        user_id = uuid.uuid4()

        state = memory.initialize(session_id, user_id)

        assert state is not None
        assert state.session.session_id == session_id
        assert state.session.user_id == user_id
        assert len(state.conversation) == 0

    def test_initialize_with_preferences(self):
        """Test initializing with user preferences."""
        memory = HotMemory()
        session_id = uuid.uuid4()
        user_id = uuid.uuid4()

        state = memory.initialize(
            session_id,
            user_id,
            preferences={
                "working_hours": "8am-4pm",
                "timezone": "Europe/London",
            }
        )

        assert state.preferences.working_hours == "8am-4pm"
        assert state.preferences.timezone == "Europe/London"

    def test_add_turn(self):
        """Test adding a conversation turn."""
        memory = HotMemory()
        memory.initialize(uuid.uuid4(), uuid.uuid4())

        memory.add_turn("user", "Hello!")
        memory.add_turn("assistant", "Hi there!")

        state = memory.get_state()
        assert len(state.conversation) == 2
        assert state.conversation[0].role == "user"
        assert state.conversation[1].role == "assistant"

    def test_add_turn_without_init_raises(self):
        """Test that adding a turn without initialization raises error."""
        memory = HotMemory()

        with pytest.raises(RuntimeError, match="not initialized"):
            memory.add_turn("user", "Hello!")

    def test_set_active_task(self):
        """Test setting the active task."""
        memory = HotMemory()
        memory.initialize(uuid.uuid4(), uuid.uuid4())

        task_data = {
            "id": uuid.uuid4(),
            "title": "Test Task",
            "description": "A test task",
            "priority": 5,
        }
        memory.set_active_task(task_data)

        state = memory.get_state()
        assert state.active_task is not None
        assert state.active_task.title == "Test Task"
        assert state.active_task.priority == 5

    def test_clear_active_task(self):
        """Test clearing the active task."""
        memory = HotMemory()
        memory.initialize(uuid.uuid4(), uuid.uuid4())

        memory.set_active_task({"id": uuid.uuid4(), "title": "Task"})
        memory.set_active_task(None)

        state = memory.get_state()
        assert state.active_task is None

    def test_update_session_state(self):
        """Test updating session state."""
        memory = HotMemory()
        memory.initialize(uuid.uuid4(), uuid.uuid4())

        memory.update_session_state(
            intent="create_task",
            pending_action="waiting_for_title",
            awaiting_confirmation=True,
        )

        state = memory.get_state()
        assert state.session.current_intent == "create_task"
        assert state.session.pending_action == "waiting_for_title"
        assert state.session.awaiting_confirmation is True

    def test_get_context_for_llm(self):
        """Test getting LLM context."""
        memory = HotMemory()
        memory.initialize(uuid.uuid4(), uuid.uuid4())

        memory.add_turn("user", "Create a task")
        memory.set_active_task({"id": uuid.uuid4(), "title": "New Task"})

        context = memory.get_context_for_llm()

        assert "conversation" in context
        assert len(context["conversation"]) == 1
        assert "active_task" in context
        assert context["active_task"]["title"] == "New Task"

    def test_token_compaction(self):
        """Test that memory compacts when over token limit."""
        # Use a small token limit
        memory = HotMemory(max_tokens=100, max_turns=5)
        memory.initialize(uuid.uuid4(), uuid.uuid4())

        # Add many messages to trigger compaction
        for i in range(20):
            memory.add_turn("user", f"Message {i} " * 20)
            memory.add_turn("assistant", f"Response {i} " * 20)

        state = memory.get_state()
        # Should have compacted to fewer turns
        assert len(state.conversation) <= 10  # max_turns * 2

    def test_summarize_conversation(self):
        """Test conversation summarization."""
        memory = HotMemory()
        memory.initialize(uuid.uuid4(), uuid.uuid4())

        memory.add_turn("user", "I need to complete the project report.")
        memory.add_turn("assistant", "I can help with that.")
        memory.add_turn("user", "Also, schedule a meeting for tomorrow.")

        summary = memory.summarize_conversation()

        assert "User discussed" in summary
        assert len(summary) > 0

    def test_summarize_empty_conversation(self):
        """Test summarizing empty conversation."""
        memory = HotMemory()
        memory.initialize(uuid.uuid4(), uuid.uuid4())

        summary = memory.summarize_conversation()
        assert summary == "No conversation yet."

    def test_clear_memory(self):
        """Test clearing hot memory."""
        memory = HotMemory()
        memory.initialize(uuid.uuid4(), uuid.uuid4())
        memory.add_turn("user", "Hello")

        memory.clear()

        assert memory.get_state() is None


class TestHotMemoryState:
    """Tests for HotMemoryState dataclass."""

    def test_create_state(self):
        """Test creating hot memory state."""
        session = SessionState(
            session_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )
        state = HotMemoryState(
            conversation=[],
            active_task=None,
            preferences=UserPreferencesSummary(),
            session=session,
            max_tokens=1000,
        )
        assert state.token_count == 0
        assert state.max_tokens == 1000
