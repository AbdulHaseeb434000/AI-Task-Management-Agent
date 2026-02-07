"""Reminder Processor - Processes triggered reminders.

Handles reminder logic including:
- Smart reminder suggestions
- Pattern-based reminders
- Task context enrichment
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import Task, TaskStatus, Reminder, ReminderType, UserPreference
from src.database.connection import get_async_session
from src.reminders.engine import ReminderEvent


class ReminderProcessor:
    """Processes and enhances reminders.

    Provides:
    - Smart reminder suggestions based on patterns
    - Task context enrichment
    - Reminder optimization
    """

    async def enrich_reminder(
        self,
        event: ReminderEvent,
    ) -> Dict[str, Any]:
        """Enrich a reminder event with context.

        Args:
            event: The reminder event.

        Returns:
            Enriched reminder data.
        """
        result = {
            "id": str(event.reminder_id),
            "message": event.message,
            "type": event.reminder_type.value,
            "channels": event.channels,
        }

        if event.task_id:
            task_context = await self._get_task_context(event.task_id)
            if task_context:
                result["task"] = task_context

        return result

    async def _get_task_context(
        self,
        task_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """Get task context for a reminder.

        Args:
            task_id: The task ID.

        Returns:
            Task context dict or None.
        """
        async with get_async_session() as session:
            task = await session.get(Task, task_id)
            if not task:
                return None

            return {
                "id": str(task.id),
                "title": task.title,
                "status": task.status.value,
                "priority": task.priority,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "is_overdue": task.due_date and task.due_date < datetime.utcnow(),
            }

    async def suggest_reminders(
        self,
        user_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Suggest reminders based on tasks and patterns.

        Args:
            user_id: The user's ID.

        Returns:
            List of suggested reminders.
        """
        suggestions = []

        async with get_async_session() as session:
            # Get tasks with due dates but no reminders
            tasks_result = await session.execute(
                select(Task)
                .where(
                    Task.user_id == user_id,
                    Task.deleted_at.is_(None),
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                    Task.due_date.isnot(None),
                    Task.due_date > datetime.utcnow(),
                )
                .order_by(Task.due_date)
                .limit(10)
            )
            tasks = tasks_result.scalars().all()

            # Check which tasks have reminders
            task_ids = [t.id for t in tasks]
            if task_ids:
                reminders_result = await session.execute(
                    select(Reminder.task_id)
                    .where(
                        Reminder.task_id.in_(task_ids),
                        Reminder.sent_at.is_(None),
                        Reminder.is_active == True,
                    )
                )
                tasks_with_reminders = set(r[0] for r in reminders_result.all())

                for task in tasks:
                    if task.id not in tasks_with_reminders:
                        time_until = task.due_date - datetime.utcnow()

                        # Suggest reminder based on urgency
                        if time_until <= timedelta(hours=2):
                            remind_before = timedelta(minutes=30)
                        elif time_until <= timedelta(days=1):
                            remind_before = timedelta(hours=1)
                        elif time_until <= timedelta(days=7):
                            remind_before = timedelta(days=1)
                        else:
                            remind_before = timedelta(days=3)

                        remind_at = task.due_date - remind_before
                        if remind_at > datetime.utcnow():
                            suggestions.append({
                                "task_id": str(task.id),
                                "task_title": task.title,
                                "due_date": task.due_date.isoformat(),
                                "suggested_remind_at": remind_at.isoformat(),
                                "remind_before": self._format_duration(remind_before),
                                "message": f"Reminder: '{task.title}' is due soon",
                            })

        return suggestions

    async def analyze_reminder_patterns(
        self,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Analyze user's reminder patterns.

        Args:
            user_id: The user's ID.

        Returns:
            Pattern analysis dict.
        """
        async with get_async_session() as session:
            # Get sent reminders from the last 30 days
            cutoff = datetime.utcnow() - timedelta(days=30)

            result = await session.execute(
                select(Reminder)
                .where(
                    Reminder.user_id == user_id,
                    Reminder.sent_at.isnot(None),
                    Reminder.sent_at >= cutoff,
                )
            )
            reminders = result.scalars().all()

        if not reminders:
            return {"message": "No reminder history to analyze"}

        # Analyze patterns
        hours = [r.remind_at.hour for r in reminders]
        days = [r.remind_at.weekday() for r in reminders]
        types = [r.reminder_type.value for r in reminders]

        # Find most common hour
        hour_counts = {}
        for h in hours:
            hour_counts[h] = hour_counts.get(h, 0) + 1
        peak_hour = max(hour_counts, key=hour_counts.get)

        # Find most common day
        day_counts = {}
        for d in days:
            day_counts[d] = day_counts.get(d, 0) + 1
        peak_day = max(day_counts, key=day_counts.get)

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        return {
            "total_reminders": len(reminders),
            "peak_hour": peak_hour,
            "peak_day": day_names[peak_day],
            "most_common_type": max(set(types), key=types.count),
            "average_per_week": len(reminders) / 4,
            "suggestion": f"You're most active around {peak_hour}:00 on {day_names[peak_day]}s",
        }

    async def create_smart_reminder(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """Create a smart reminder based on patterns.

        Args:
            user_id: The user's ID.
            task_id: The task ID.

        Returns:
            Created reminder info or None.
        """
        from src.reminders.engine import get_reminder_engine

        patterns = await self.analyze_reminder_patterns(user_id)

        async with get_async_session() as session:
            task = await session.get(Task, task_id)
            if not task or not task.due_date:
                return None

            # Use peak hour for reminder
            peak_hour = patterns.get("peak_hour", 9)

            # Set reminder for day before at peak hour
            remind_at = task.due_date - timedelta(days=1)
            remind_at = remind_at.replace(
                hour=peak_hour,
                minute=0,
                second=0,
                microsecond=0,
            )

            if remind_at <= datetime.utcnow():
                # If that's in the past, remind 1 hour before
                remind_at = task.due_date - timedelta(hours=1)

            if remind_at <= datetime.utcnow():
                return None

            engine = get_reminder_engine()
            reminder = await engine.create_reminder(
                user_id=user_id,
                message=f"Smart reminder: '{task.title}' is due tomorrow",
                remind_at=remind_at,
                reminder_type=ReminderType.SMART,
                task_id=task_id,
            )

            return {
                "id": str(reminder.id),
                "remind_at": reminder.remind_at.isoformat(),
                "message": reminder.message,
                "reason": f"Based on your activity pattern around {peak_hour}:00",
            }

    def _format_duration(self, delta: timedelta) -> str:
        """Format a timedelta as human-readable string."""
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
