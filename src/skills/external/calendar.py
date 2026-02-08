"""Calendar Skill - Integration with calendar services.

Supports:
- Google Calendar (placeholder for OAuth integration)
- Outlook Calendar (placeholder for Graph API)
- Generic iCal
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from src.skills.base import (
    BaseSkill,
    SkillManifest,
    SkillCategory,
    SkillContext,
    SkillResult,
    LoadStrategy,
    PermissionLevel,
)


class CalendarProvider(Enum):
    """Supported calendar providers."""
    GOOGLE = "google"
    OUTLOOK = "outlook"
    ICAL = "ical"


@dataclass
class CalendarEvent:
    """A calendar event."""
    id: str
    title: str
    start: datetime
    end: datetime
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: List[str] = None
    all_day: bool = False
    recurring: bool = False
    recurrence_rule: Optional[str] = None

    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []


class CalendarSkill(BaseSkill):
    """Skill for calendar operations.

    Actions:
    - create_event: Create a new calendar event
    - update_event: Update an existing event
    - delete_event: Delete an event
    - list_events: List events in a time range
    - find_free_time: Find available time slots
    - sync_task: Sync a task to calendar as event
    """

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="calendar",
            description="Manage calendar events and sync with tasks",
            version="1.0.0",
            category=SkillCategory.EXTERNAL,
            triggers=[
                "calendar", "schedule", "meeting", "event",
                "block time", "add to calendar", "sync calendar",
            ],
            permission_level=PermissionLevel.EXTERNAL,
            approval_required=True,  # External side effects
            load_strategy=LoadStrategy.LAZY,
            timeout_ms=30000,
            required_config=["calendar_provider"],
            parameters_schema={
                "action": {"type": "string", "required": True},
                "title": {"type": "string"},
                "start": {"type": "string", "format": "datetime"},
                "end": {"type": "string", "format": "datetime"},
                "duration_minutes": {"type": "integer"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
        )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute a calendar action."""
        action = context.parameters.get("action", "list_events")

        actions = {
            "create_event": self._create_event,
            "update_event": self._update_event,
            "delete_event": self._delete_event,
            "list_events": self._list_events,
            "find_free_time": self._find_free_time,
            "sync_task": self._sync_task,
        }

        handler = actions.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action: {action}. Valid actions: {list(actions.keys())}",
            )

        return await handler(context)

    async def _create_event(self, context: SkillContext) -> SkillResult:
        """Create a new calendar event."""
        params = context.parameters

        title = params.get("title")
        if not title:
            return SkillResult(success=False, error="Title is required")

        # Parse start time
        start_str = params.get("start")
        if not start_str:
            return SkillResult(success=False, error="Start time is required")

        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        except ValueError:
            return SkillResult(success=False, error=f"Invalid start time format: {start_str}")

        # Calculate end time
        end_str = params.get("end")
        duration = params.get("duration_minutes", 60)

        if end_str:
            try:
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except ValueError:
                return SkillResult(success=False, error=f"Invalid end time format: {end_str}")
        else:
            end = start + timedelta(minutes=duration)

        event = CalendarEvent(
            id=str(uuid.uuid4()),
            title=title,
            start=start,
            end=end,
            description=params.get("description"),
            location=params.get("location"),
            attendees=params.get("attendees", []),
        )

        # TODO: Integrate with actual calendar provider
        # For now, return success with the event data
        return SkillResult(
            success=True,
            data={
                "event_id": event.id,
                "title": event.title,
                "start": event.start.isoformat(),
                "end": event.end.isoformat(),
                "description": event.description,
                "location": event.location,
                "attendees": event.attendees,
                "provider": "placeholder",
                "message": f"Event '{title}' created (placeholder - no actual calendar integration)",
            },
            metadata={"action": "create_event", "provider": "placeholder"},
        )

    async def _update_event(self, context: SkillContext) -> SkillResult:
        """Update an existing calendar event."""
        params = context.parameters

        event_id = params.get("event_id")
        if not event_id:
            return SkillResult(success=False, error="Event ID is required")

        updates = {}
        if "title" in params:
            updates["title"] = params["title"]
        if "start" in params:
            updates["start"] = params["start"]
        if "end" in params:
            updates["end"] = params["end"]
        if "description" in params:
            updates["description"] = params["description"]
        if "location" in params:
            updates["location"] = params["location"]

        if not updates:
            return SkillResult(success=False, error="No updates provided")

        # TODO: Integrate with actual calendar provider
        return SkillResult(
            success=True,
            data={
                "event_id": event_id,
                "updates": updates,
                "message": f"Event updated (placeholder)",
            },
            metadata={"action": "update_event"},
        )

    async def _delete_event(self, context: SkillContext) -> SkillResult:
        """Delete a calendar event."""
        params = context.parameters

        event_id = params.get("event_id")
        if not event_id:
            return SkillResult(success=False, error="Event ID is required")

        # TODO: Integrate with actual calendar provider
        return SkillResult(
            success=True,
            data={
                "event_id": event_id,
                "deleted": True,
                "message": f"Event deleted (placeholder)",
            },
            metadata={"action": "delete_event"},
        )

    async def _list_events(self, context: SkillContext) -> SkillResult:
        """List calendar events in a time range."""
        params = context.parameters

        # Default to today
        start_str = params.get("start")
        end_str = params.get("end")

        now = datetime.utcnow()
        if start_str:
            try:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except ValueError:
                start = now.replace(hour=0, minute=0, second=0)
        else:
            start = now.replace(hour=0, minute=0, second=0)

        if end_str:
            try:
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except ValueError:
                end = start + timedelta(days=1)
        else:
            end = start + timedelta(days=1)

        # TODO: Integrate with actual calendar provider
        # Return placeholder data
        return SkillResult(
            success=True,
            data={
                "events": [],
                "start": start.isoformat(),
                "end": end.isoformat(),
                "count": 0,
                "message": "No events found (placeholder - no calendar integration)",
            },
            metadata={"action": "list_events"},
        )

    async def _find_free_time(self, context: SkillContext) -> SkillResult:
        """Find free time slots in the calendar."""
        params = context.parameters

        duration = params.get("duration_minutes", 30)
        date_str = params.get("date")

        if date_str:
            try:
                target_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
            except ValueError:
                target_date = datetime.utcnow().date()
        else:
            target_date = datetime.utcnow().date()

        # TODO: Integrate with actual calendar and find free slots
        # Return placeholder free slots
        work_start = datetime.combine(target_date, datetime.min.time().replace(hour=9))
        work_end = datetime.combine(target_date, datetime.min.time().replace(hour=17))

        free_slots = [
            {"start": work_start.isoformat(), "end": (work_start + timedelta(hours=1)).isoformat()},
            {"start": (work_start + timedelta(hours=2)).isoformat(), "end": (work_start + timedelta(hours=3)).isoformat()},
        ]

        return SkillResult(
            success=True,
            data={
                "date": target_date.isoformat(),
                "duration_minutes": duration,
                "free_slots": free_slots,
                "message": "Found 2 free slots (placeholder data)",
            },
            metadata={"action": "find_free_time"},
        )

    async def _sync_task(self, context: SkillContext) -> SkillResult:
        """Sync a task to calendar as a time block."""
        params = context.parameters

        task_id = params.get("task_id")
        if not task_id:
            return SkillResult(success=False, error="Task ID is required")

        start_str = params.get("start")
        if not start_str:
            return SkillResult(success=False, error="Start time is required for calendar sync")

        duration = params.get("duration_minutes", 60)

        # TODO: Fetch task details and create calendar event
        return SkillResult(
            success=True,
            data={
                "task_id": task_id,
                "synced": True,
                "event_id": str(uuid.uuid4()),
                "start": start_str,
                "duration_minutes": duration,
                "message": f"Task synced to calendar (placeholder)",
            },
            metadata={"action": "sync_task"},
        )

    async def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters."""
        action = parameters.get("action")
        if not action:
            return False, "Action is required"
        return True, None

    def requires_approval(self, context: SkillContext) -> bool:
        """Calendar actions with external side effects require approval."""
        action = context.parameters.get("action", "")
        # Read-only actions don't need approval
        if action in ["list_events", "find_free_time"]:
            return False
        return True
