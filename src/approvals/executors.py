"""Action Executors - Functions to execute approved actions.

This module contains executor functions that are called when
an action is approved by the user.
"""

import uuid
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import User, Memory
from src.database.connection import get_async_session


async def execute_preference_update(action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a preference update action.

    Called when a user approves a preference update.

    Args:
        action_data: Contains:
            - user_id: The user's UUID (as string)
            - preference_key: The preference to update
            - old_value: Previous value
            - new_value: New value
            - reason: Why this change was proposed
            - confidence: Confidence level

    Returns:
        Dict with update result.
    """
    user_id = uuid.UUID(action_data["user_id"]) if isinstance(action_data.get("user_id"), str) else action_data.get("user_id")
    preference_key = action_data.get("preference_key")
    new_value = action_data.get("new_value")
    reason = action_data.get("reason", "User approved")

    if not user_id or not preference_key:
        return {"success": False, "error": "Missing user_id or preference_key"}

    async with get_async_session() as session:
        user = await session.get(User, user_id)
        if not user:
            return {"success": False, "error": f"User {user_id} not found"}

        # Get current preferences
        preferences = user.preferences or {}
        old_value = preferences.get(preference_key)

        # Update preference
        preferences[preference_key] = new_value
        user.preferences = preferences
        await session.commit()

        # Log the change
        memory = Memory(
            user_id=user_id,
            memory_type="preference_change",
            source_type="user_approved",
            content=f"Changed {preference_key} from {old_value} to {new_value}",
            metadata={
                "preference_key": preference_key,
                "old_value": old_value,
                "new_value": new_value,
                "reason": reason,
                "method": "approved",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        session.add(memory)
        await session.commit()

    return {
        "success": True,
        "preference_key": preference_key,
        "old_value": old_value,
        "new_value": new_value,
    }


async def execute_task_delete(action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a task deletion action.

    Args:
        action_data: Contains task_id, title, etc.

    Returns:
        Dict with deletion result.
    """
    from src.database.orm import Task

    task_id = action_data.get("task_id")
    if not task_id:
        return {"success": False, "error": "Missing task_id"}

    if isinstance(task_id, str):
        task_id = uuid.UUID(task_id)

    async with get_async_session() as session:
        task = await session.get(Task, task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}

        # Soft delete
        task.deleted_at = datetime.utcnow()
        await session.commit()

    return {
        "success": True,
        "task_id": str(task_id),
        "title": action_data.get("title", "Unknown"),
    }


async def execute_email_send(action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an email send action.

    Args:
        action_data: Contains to, subject, body, etc.

    Returns:
        Dict with send result.
    """
    # This would integrate with the notification service
    # For now, return a placeholder
    return {
        "success": True,
        "to": action_data.get("to"),
        "subject": action_data.get("subject"),
        "status": "queued",
        "message": "Email integration not configured",
    }


async def execute_calendar_event(action_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a calendar event creation.

    Args:
        action_data: Contains title, start_time, end_time, etc.

    Returns:
        Dict with creation result.
    """
    # This would integrate with calendar service
    # For now, return a placeholder
    return {
        "success": True,
        "title": action_data.get("title"),
        "status": "pending",
        "message": "Calendar integration not configured",
    }


def register_default_executors(queue) -> None:
    """Register all default executors with the approval queue.

    Args:
        queue: The ApprovalQueue instance.
    """
    queue.register_executor("preference.update", execute_preference_update)
    queue.register_executor("task.delete", execute_task_delete)
    queue.register_executor("email.send", execute_email_send)
    queue.register_executor("calendar.create", execute_calendar_event)
    queue.register_executor("calendar.update", execute_calendar_event)
