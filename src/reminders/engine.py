"""Reminder Engine - Scheduling and processing reminders.

Handles:
- Time-based reminders
- Relative reminders (before due date)
- Recurring reminders
- Smart reminders (pattern-based)
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import Reminder, ReminderType, Task
from src.database.connection import get_async_session


class ReminderStatus(Enum):
    """Reminder status."""
    PENDING = "pending"
    TRIGGERED = "triggered"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ReminderEvent:
    """A triggered reminder event."""
    reminder_id: uuid.UUID
    user_id: uuid.UUID
    task_id: Optional[uuid.UUID]
    message: str
    reminder_type: ReminderType
    channels: List[str]
    metadata: Dict[str, Any]


class ReminderEngine:
    """Manages reminder scheduling and processing.

    Provides:
    - Creating and scheduling reminders
    - Processing due reminders
    - Recurring reminder calculation
    - Integration with notification dispatcher
    """

    def __init__(self, check_interval_seconds: int = 60):
        """Initialize the reminder engine.

        Args:
            check_interval_seconds: How often to check for due reminders.
        """
        self.check_interval = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._handlers: List[Callable[[ReminderEvent], Any]] = []

    async def start(self) -> None:
        """Start the reminder engine background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the reminder engine."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def register_handler(self, handler: Callable[[ReminderEvent], Any]) -> None:
        """Register a handler for triggered reminders.

        Args:
            handler: Callback function for reminder events.
        """
        self._handlers.append(handler)

    async def _run_loop(self) -> None:
        """Background loop that checks for due reminders."""
        while self._running:
            try:
                await self.process_due_reminders()
            except Exception as e:
                # Log error but continue running
                print(f"Error processing reminders: {e}")

            await asyncio.sleep(self.check_interval)

    async def create_reminder(
        self,
        user_id: uuid.UUID,
        message: str,
        remind_at: datetime,
        reminder_type: ReminderType = ReminderType.TIME_BASED,
        task_id: Optional[uuid.UUID] = None,
        recurrence_rule: Optional[str] = None,
        channels: Optional[List[str]] = None,
    ) -> Reminder:
        """Create a new reminder.

        Args:
            user_id: The user's ID.
            message: Reminder message.
            remind_at: When to trigger the reminder.
            reminder_type: Type of reminder.
            task_id: Optional associated task.
            recurrence_rule: Optional recurrence rule (e.g., "daily", "weekly").
            channels: Notification channels (defaults to ["push"]).

        Returns:
            The created Reminder.
        """
        async with get_async_session() as session:
            reminder = Reminder(
                user_id=user_id,
                task_id=task_id,
                remind_at=remind_at,
                reminder_type=reminder_type,
                message=message,
                is_recurring=recurrence_rule is not None,
                recurrence_rule=recurrence_rule,
                notification_channels=channels or ["push"],
            )
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)
            return reminder

    async def create_relative_reminder(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        before_due: timedelta,
        message: Optional[str] = None,
    ) -> Optional[Reminder]:
        """Create a reminder relative to a task's due date.

        Args:
            user_id: The user's ID.
            task_id: The task ID.
            before_due: How long before due date to remind.
            message: Optional custom message.

        Returns:
            The created Reminder or None if task has no due date.
        """
        async with get_async_session() as session:
            task = await session.get(Task, task_id)
            if not task or not task.due_date:
                return None

            remind_at = task.due_date - before_due
            if remind_at <= datetime.utcnow():
                remind_at = datetime.utcnow() + timedelta(minutes=5)

            default_message = f"Reminder: '{task.title}' is due in {self._format_duration(before_due)}"

            return await self.create_reminder(
                user_id=user_id,
                message=message or default_message,
                remind_at=remind_at,
                reminder_type=ReminderType.RELATIVE,
                task_id=task_id,
            )

    async def create_recurring_reminder(
        self,
        user_id: uuid.UUID,
        message: str,
        first_at: datetime,
        rule: str,
        task_id: Optional[uuid.UUID] = None,
    ) -> Reminder:
        """Create a recurring reminder.

        Args:
            user_id: The user's ID.
            message: Reminder message.
            first_at: First trigger time.
            rule: Recurrence rule (e.g., "daily", "weekly", "every monday").
            task_id: Optional associated task.

        Returns:
            The created Reminder.
        """
        return await self.create_reminder(
            user_id=user_id,
            message=message,
            remind_at=first_at,
            reminder_type=ReminderType.RECURRING,
            task_id=task_id,
            recurrence_rule=rule,
        )

    async def process_due_reminders(self) -> List[ReminderEvent]:
        """Process all due reminders.

        Returns:
            List of triggered reminder events.
        """
        events = []
        now = datetime.utcnow()

        async with get_async_session() as session:
            # Get all due, unsent reminders
            result = await session.execute(
                select(Reminder).where(
                    Reminder.remind_at <= now,
                    Reminder.sent_at.is_(None),
                    Reminder.is_active == True,
                )
            )
            reminders = result.scalars().all()

            for reminder in reminders:
                event = ReminderEvent(
                    reminder_id=reminder.id,
                    user_id=reminder.user_id,
                    task_id=reminder.task_id,
                    message=reminder.message,
                    reminder_type=reminder.reminder_type,
                    channels=reminder.notification_channels or ["push"],
                    metadata=reminder.metadata or {},
                )
                events.append(event)

                # Mark as sent
                reminder.sent_at = now

                # Handle recurring reminders
                if reminder.is_recurring and reminder.recurrence_rule:
                    next_time = self._calculate_next_occurrence(
                        reminder.remind_at,
                        reminder.recurrence_rule,
                    )
                    if next_time:
                        # Create next occurrence
                        new_reminder = Reminder(
                            user_id=reminder.user_id,
                            task_id=reminder.task_id,
                            remind_at=next_time,
                            reminder_type=reminder.reminder_type,
                            message=reminder.message,
                            is_recurring=True,
                            recurrence_rule=reminder.recurrence_rule,
                            notification_channels=reminder.notification_channels,
                        )
                        session.add(new_reminder)

                # Notify handlers
                for handler in self._handlers:
                    try:
                        result = handler(event)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        print(f"Handler error: {e}")

            await session.commit()

        return events

    async def cancel_reminder(self, reminder_id: uuid.UUID) -> bool:
        """Cancel a reminder.

        Args:
            reminder_id: The reminder ID.

        Returns:
            True if cancelled.
        """
        async with get_async_session() as session:
            reminder = await session.get(Reminder, reminder_id)
            if not reminder:
                return False

            reminder.is_active = False
            await session.commit()
            return True

    async def get_pending_reminders(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get pending reminders for a user.

        Args:
            user_id: The user's ID.
            limit: Maximum reminders to return.

        Returns:
            List of reminder dicts.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(Reminder)
                .where(
                    Reminder.user_id == user_id,
                    Reminder.sent_at.is_(None),
                    Reminder.is_active == True,
                )
                .order_by(Reminder.remind_at)
                .limit(limit)
            )
            reminders = result.scalars().all()

        return [
            {
                "id": str(r.id),
                "message": r.message,
                "remind_at": r.remind_at.isoformat(),
                "type": r.reminder_type.value,
                "is_recurring": r.is_recurring,
                "task_id": str(r.task_id) if r.task_id else None,
                "channels": r.notification_channels,
            }
            for r in reminders
        ]

    async def get_upcoming_reminders(
        self,
        user_id: uuid.UUID,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """Get reminders due in the next N hours.

        Args:
            user_id: The user's ID.
            hours: Hours to look ahead.

        Returns:
            List of reminder dicts.
        """
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours)

        async with get_async_session() as session:
            result = await session.execute(
                select(Reminder)
                .where(
                    Reminder.user_id == user_id,
                    Reminder.remind_at >= now,
                    Reminder.remind_at <= cutoff,
                    Reminder.sent_at.is_(None),
                    Reminder.is_active == True,
                )
                .order_by(Reminder.remind_at)
            )
            reminders = result.scalars().all()

        return [
            {
                "id": str(r.id),
                "message": r.message,
                "remind_at": r.remind_at.isoformat(),
                "time_until": self._format_duration(r.remind_at - now),
                "type": r.reminder_type.value,
            }
            for r in reminders
        ]

    def _calculate_next_occurrence(
        self,
        current: datetime,
        rule: str,
    ) -> Optional[datetime]:
        """Calculate the next occurrence for a recurring reminder.

        Args:
            current: Current reminder time.
            rule: Recurrence rule.

        Returns:
            Next occurrence time or None if rule invalid.
        """
        rule_lower = rule.lower().strip()

        if rule_lower == "daily":
            return current + timedelta(days=1)
        elif rule_lower == "weekly":
            return current + timedelta(weeks=1)
        elif rule_lower == "monthly":
            # Simple: add 30 days
            return current + timedelta(days=30)
        elif rule_lower == "hourly":
            return current + timedelta(hours=1)
        elif rule_lower.startswith("every "):
            # Parse "every N hours/days/weeks"
            parts = rule_lower[6:].split()
            if len(parts) >= 2:
                try:
                    n = int(parts[0])
                    unit = parts[1]
                    if unit.startswith("hour"):
                        return current + timedelta(hours=n)
                    elif unit.startswith("day"):
                        return current + timedelta(days=n)
                    elif unit.startswith("week"):
                        return current + timedelta(weeks=n)
                except ValueError:
                    pass

            # Handle "every monday", "every friday", etc.
            days = {
                "monday": 0, "tuesday": 1, "wednesday": 2,
                "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
            }
            day_name = parts[0] if parts else ""
            if day_name in days:
                target_day = days[day_name]
                current_day = current.weekday()
                days_ahead = target_day - current_day
                if days_ahead <= 0:
                    days_ahead += 7
                return current + timedelta(days=days_ahead)

        return None

    def _format_duration(self, delta: timedelta) -> str:
        """Format a timedelta as human-readable string.

        Args:
            delta: The timedelta.

        Returns:
            Human-readable string.
        """
        total_seconds = int(delta.total_seconds())

        if total_seconds < 0:
            return "now"

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours >= 24:
            days = hours // 24
            return f"{days} day(s)"
        elif hours > 0:
            return f"{hours} hour(s)"
        elif minutes > 0:
            return f"{minutes} minute(s)"
        else:
            return "less than a minute"


# Global instance
_engine: Optional[ReminderEngine] = None


def get_reminder_engine() -> ReminderEngine:
    """Get the global reminder engine instance."""
    global _engine
    if _engine is None:
        _engine = ReminderEngine()
    return _engine
