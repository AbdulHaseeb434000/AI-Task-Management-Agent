"""Tests for Reminder Engine functionality."""

import uuid
from datetime import datetime, timedelta
import pytest

from src.reminders.engine import (
    ReminderEngine,
    ReminderEvent,
    ReminderStatus,
)
from src.database.orm import ReminderType


class TestReminderStatus:
    """Tests for ReminderStatus enum."""

    def test_status_values(self):
        """Test reminder status values."""
        assert ReminderStatus.PENDING.value == "pending"
        assert ReminderStatus.TRIGGERED.value == "triggered"
        assert ReminderStatus.SENT.value == "sent"
        assert ReminderStatus.FAILED.value == "failed"
        assert ReminderStatus.CANCELLED.value == "cancelled"


class TestReminderEvent:
    """Tests for ReminderEvent dataclass."""

    def test_create_event(self):
        """Test creating a reminder event."""
        reminder_id = uuid.uuid4()
        user_id = uuid.uuid4()
        task_id = uuid.uuid4()

        event = ReminderEvent(
            reminder_id=reminder_id,
            user_id=user_id,
            task_id=task_id,
            message="Don't forget to complete your task!",
            reminder_type=ReminderType.TIME_BASED,
            channels=["push", "email"],
            metadata={"priority": "high"},
        )

        assert event.reminder_id == reminder_id
        assert event.user_id == user_id
        assert event.task_id == task_id
        assert event.message == "Don't forget to complete your task!"
        assert event.reminder_type == ReminderType.TIME_BASED
        assert "push" in event.channels
        assert event.metadata["priority"] == "high"


class TestReminderEngineHelpers:
    """Tests for ReminderEngine helper methods."""

    def test_format_duration_minutes(self):
        """Test formatting duration in minutes."""
        engine = ReminderEngine()

        delta = timedelta(minutes=30)
        result = engine._format_duration(delta)
        assert result == "30 minute(s)"

    def test_format_duration_hours(self):
        """Test formatting duration in hours."""
        engine = ReminderEngine()

        delta = timedelta(hours=5)
        result = engine._format_duration(delta)
        assert result == "5 hour(s)"

    def test_format_duration_days(self):
        """Test formatting duration in days."""
        engine = ReminderEngine()

        delta = timedelta(days=3)
        result = engine._format_duration(delta)
        assert result == "3 day(s)"

    def test_format_duration_less_than_minute(self):
        """Test formatting duration less than a minute."""
        engine = ReminderEngine()

        delta = timedelta(seconds=30)
        result = engine._format_duration(delta)
        assert result == "less than a minute"

    def test_format_duration_negative(self):
        """Test formatting negative duration."""
        engine = ReminderEngine()

        delta = timedelta(seconds=-10)
        result = engine._format_duration(delta)
        assert result == "now"


class TestReminderEngineRecurrence:
    """Tests for recurrence calculation."""

    def test_calculate_next_daily(self):
        """Test daily recurrence."""
        engine = ReminderEngine()
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "daily")

        assert next_time is not None
        assert next_time == datetime(2024, 1, 16, 9, 0, 0)

    def test_calculate_next_weekly(self):
        """Test weekly recurrence."""
        engine = ReminderEngine()
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "weekly")

        assert next_time is not None
        assert next_time == datetime(2024, 1, 22, 9, 0, 0)

    def test_calculate_next_monthly(self):
        """Test monthly recurrence (30 days)."""
        engine = ReminderEngine()
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "monthly")

        assert next_time is not None
        assert next_time == datetime(2024, 2, 14, 9, 0, 0)  # 30 days later

    def test_calculate_next_hourly(self):
        """Test hourly recurrence."""
        engine = ReminderEngine()
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "hourly")

        assert next_time is not None
        assert next_time == datetime(2024, 1, 15, 10, 0, 0)

    def test_calculate_next_every_n_hours(self):
        """Test 'every N hours' recurrence."""
        engine = ReminderEngine()
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "every 3 hours")

        assert next_time is not None
        assert next_time == datetime(2024, 1, 15, 12, 0, 0)

    def test_calculate_next_every_n_days(self):
        """Test 'every N days' recurrence."""
        engine = ReminderEngine()
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "every 5 days")

        assert next_time is not None
        assert next_time == datetime(2024, 1, 20, 9, 0, 0)

    def test_calculate_next_every_n_weeks(self):
        """Test 'every N weeks' recurrence."""
        engine = ReminderEngine()
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "every 2 weeks")

        assert next_time is not None
        assert next_time == datetime(2024, 1, 29, 9, 0, 0)

    def test_calculate_next_every_monday(self):
        """Test 'every monday' recurrence."""
        engine = ReminderEngine()
        # Jan 15, 2024 is a Monday
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "every monday")

        assert next_time is not None
        # Next Monday should be Jan 22
        assert next_time.weekday() == 0  # Monday

    def test_calculate_next_every_friday(self):
        """Test 'every friday' recurrence."""
        engine = ReminderEngine()
        # Jan 15, 2024 is a Monday
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "every friday")

        assert next_time is not None
        assert next_time.weekday() == 4  # Friday

    def test_calculate_next_invalid_rule(self):
        """Test invalid recurrence rule returns None."""
        engine = ReminderEngine()
        current = datetime(2024, 1, 15, 9, 0, 0)

        next_time = engine._calculate_next_occurrence(current, "invalid rule")

        assert next_time is None


class TestReminderEngineState:
    """Tests for ReminderEngine state management."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        engine = ReminderEngine(check_interval_seconds=30)

        assert engine.check_interval == 30
        assert engine._running is False
        assert engine._task is None

    def test_register_handler(self):
        """Test registering event handlers."""
        engine = ReminderEngine()

        def my_handler(event):
            pass

        engine.register_handler(my_handler)

        assert len(engine._handlers) == 1

    def test_register_multiple_handlers(self):
        """Test registering multiple handlers."""
        engine = ReminderEngine()

        def handler1(event):
            pass

        def handler2(event):
            pass

        engine.register_handler(handler1)
        engine.register_handler(handler2)

        assert len(engine._handlers) == 2


class TestReminderType:
    """Tests for ReminderType enum from ORM."""

    def test_reminder_types(self):
        """Test reminder type values."""
        assert ReminderType.TIME_BASED.value == "time_based"
        assert ReminderType.RELATIVE.value == "relative"
        assert ReminderType.RECURRING.value == "recurring"
        assert ReminderType.SMART.value == "smart"
