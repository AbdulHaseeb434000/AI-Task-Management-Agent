"""Schedule Skill - Time-based task scheduling.

Handles due dates, reminders, and time-based planning.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.skills.base import (
    BaseSkill,
    SkillCategory,
    SkillContext,
    SkillManifest,
    SkillResult,
    PermissionLevel,
    LoadStrategy,
)
from src.database.orm import Task, Reminder, ReminderType, TaskStatus
from src.database.connection import get_async_session


class ScheduleSkill(BaseSkill):
    """Time-based task scheduling."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="schedule",
            version="1.0.0",
            description="Schedule tasks, set due dates, and create reminders",
            category=SkillCategory.INTERNAL,
            triggers=[
                "schedule",
                "set due date",
                "due by",
                "remind me",
                "set reminder",
                "when should i",
                "today's tasks",
                "this week",
                "overdue",
                "upcoming",
            ],
            parameters={
                "action": {
                    "type": "string",
                    "enum": [
                        "set_due_date",
                        "set_reminder",
                        "get_schedule",
                        "get_overdue",
                        "get_upcoming",
                        "reschedule",
                    ],
                    "required": True,
                },
                "task_id": {"type": "string", "required": False},
                "due_date": {"type": "string", "format": "datetime", "required": False},
                "reminder_time": {"type": "string", "format": "datetime", "required": False},
                "reminder_offset": {"type": "string", "required": False},  # e.g., "1h", "1d"
                "time_range": {"type": "string", "required": False},  # today, week, month
            },
            permission_level=PermissionLevel.INTERNAL,
            approval_required=False,
            data_access=["tasks", "reminders"],
            timeout_ms=5000,
            load_strategy=LoadStrategy.EAGER,
        )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute scheduling operation."""
        action = context.parameters.get("action", "get_schedule")

        action_handlers = {
            "set_due_date": self._set_due_date,
            "set_reminder": self._set_reminder,
            "get_schedule": self._get_schedule,
            "get_overdue": self._get_overdue,
            "get_upcoming": self._get_upcoming,
            "reschedule": self._reschedule,
        }

        handler = action_handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")

        try:
            async with get_async_session() as session:
                return await handler(session, context)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse datetime string."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _parse_offset(self, offset_str: str) -> Optional[timedelta]:
        """Parse offset string like '1h', '2d', '30m'."""
        if not offset_str:
            return None

        try:
            value = int(offset_str[:-1])
            unit = offset_str[-1].lower()

            if unit == "m":
                return timedelta(minutes=value)
            elif unit == "h":
                return timedelta(hours=value)
            elif unit == "d":
                return timedelta(days=value)
            elif unit == "w":
                return timedelta(weeks=value)
            else:
                return None
        except (ValueError, IndexError):
            return None

    async def _set_due_date(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Set due date for a task."""
        task_id = context.parameters.get("task_id")
        due_date_str = context.parameters.get("due_date")

        if not task_id:
            return SkillResult(success=False, error="Missing required parameter: task_id")

        due_date = self._parse_datetime(due_date_str)
        if not due_date and due_date_str:
            return SkillResult(success=False, error=f"Invalid date format: {due_date_str}")

        result = await session.execute(
            select(Task).where(
                Task.id == uuid.UUID(task_id),
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
            )
        )
        task = result.scalar_one_or_none()

        if not task:
            return SkillResult(success=False, error=f"Task not found: {task_id}")

        task.due_date = due_date
        task.updated_at = datetime.utcnow()

        return SkillResult(
            success=True,
            data={
                "task_id": str(task.id),
                "title": task.title,
                "due_date": due_date.isoformat() if due_date else None,
                "message": f"Set due date for '{task.title}' to {due_date}" if due_date else f"Cleared due date for '{task.title}'",
            },
        )

    async def _set_reminder(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Set a reminder for a task."""
        task_id = context.parameters.get("task_id")
        reminder_time_str = context.parameters.get("reminder_time")
        reminder_offset_str = context.parameters.get("reminder_offset")

        if not task_id:
            return SkillResult(success=False, error="Missing required parameter: task_id")

        result = await session.execute(
            select(Task).where(
                Task.id == uuid.UUID(task_id),
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
            )
        )
        task = result.scalar_one_or_none()

        if not task:
            return SkillResult(success=False, error=f"Task not found: {task_id}")

        # Calculate reminder time
        reminder_time = None
        reminder_type = ReminderType.TIME_BASED

        if reminder_time_str:
            reminder_time = self._parse_datetime(reminder_time_str)
        elif reminder_offset_str and task.due_date:
            offset = self._parse_offset(reminder_offset_str)
            if offset:
                reminder_time = task.due_date - offset
                reminder_type = ReminderType.RELATIVE
        elif task.due_date:
            # Default: 1 hour before due date
            reminder_time = task.due_date - timedelta(hours=1)
            reminder_type = ReminderType.RELATIVE

        if not reminder_time:
            return SkillResult(
                success=False,
                error="Could not determine reminder time. Provide reminder_time or set a due date.",
            )

        reminder = Reminder(
            id=uuid.uuid4(),
            user_id=uuid.UUID(context.user_id),
            task_id=task.id,
            reminder_type=reminder_type,
            message=f"Reminder: {task.title}",
            scheduled_for=reminder_time,
            channels=["push"],
        )
        session.add(reminder)

        return SkillResult(
            success=True,
            data={
                "reminder_id": str(reminder.id),
                "task_id": str(task.id),
                "title": task.title,
                "scheduled_for": reminder_time.isoformat(),
                "message": f"Set reminder for '{task.title}' at {reminder_time}",
            },
        )

    async def _get_schedule(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Get scheduled tasks for a time range."""
        time_range = context.parameters.get("time_range", "today")
        now = datetime.utcnow()

        if time_range == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif time_range == "week":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        elif time_range == "month":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=30)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)

        result = await session.execute(
            select(Task).where(
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                Task.due_date.isnot(None),
                Task.due_date >= start,
                Task.due_date < end,
            ).order_by(Task.due_date.asc())
        )
        tasks = result.scalars().all()

        return SkillResult(
            success=True,
            data={
                "time_range": time_range,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "count": len(tasks),
                "tasks": [
                    {
                        "task_id": str(t.id),
                        "title": t.title,
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                        "priority": t.priority,
                        "status": t.status.value,
                    }
                    for t in tasks
                ],
            },
        )

    async def _get_overdue(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Get overdue tasks."""
        now = datetime.utcnow()

        result = await session.execute(
            select(Task).where(
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                Task.due_date.isnot(None),
                Task.due_date < now,
            ).order_by(Task.due_date.asc())
        )
        tasks = result.scalars().all()

        return SkillResult(
            success=True,
            data={
                "count": len(tasks),
                "tasks": [
                    {
                        "task_id": str(t.id),
                        "title": t.title,
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                        "overdue_by": str(now - t.due_date) if t.due_date else None,
                        "priority": t.priority,
                    }
                    for t in tasks
                ],
                "message": f"You have {len(tasks)} overdue task(s)" if tasks else "No overdue tasks!",
            },
        )

    async def _get_upcoming(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Get upcoming tasks (next 48 hours)."""
        now = datetime.utcnow()
        end = now + timedelta(hours=48)

        result = await session.execute(
            select(Task).where(
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                Task.due_date.isnot(None),
                Task.due_date >= now,
                Task.due_date <= end,
            ).order_by(Task.due_date.asc())
        )
        tasks = result.scalars().all()

        return SkillResult(
            success=True,
            data={
                "count": len(tasks),
                "tasks": [
                    {
                        "task_id": str(t.id),
                        "title": t.title,
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                        "time_until": str(t.due_date - now) if t.due_date else None,
                        "priority": t.priority,
                    }
                    for t in tasks
                ],
                "message": f"You have {len(tasks)} task(s) due in the next 48 hours",
            },
        )

    async def _reschedule(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Reschedule a task to a new date."""
        task_id = context.parameters.get("task_id")
        new_date_str = context.parameters.get("due_date")

        if not task_id:
            return SkillResult(success=False, error="Missing required parameter: task_id")
        if not new_date_str:
            return SkillResult(success=False, error="Missing required parameter: due_date")

        new_date = self._parse_datetime(new_date_str)
        if not new_date:
            return SkillResult(success=False, error=f"Invalid date format: {new_date_str}")

        result = await session.execute(
            select(Task).where(
                Task.id == uuid.UUID(task_id),
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
            )
        )
        task = result.scalar_one_or_none()

        if not task:
            return SkillResult(success=False, error=f"Task not found: {task_id}")

        old_date = task.due_date
        task.due_date = new_date
        task.updated_at = datetime.utcnow()

        return SkillResult(
            success=True,
            data={
                "task_id": str(task.id),
                "title": task.title,
                "old_due_date": old_date.isoformat() if old_date else None,
                "new_due_date": new_date.isoformat(),
                "message": f"Rescheduled '{task.title}' to {new_date}",
            },
        )
