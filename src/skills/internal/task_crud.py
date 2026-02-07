"""Task CRUD Skill - Create, read, update, delete tasks.

This is an internal skill that's always available (eager load).
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, update, delete
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
from src.database.orm import Task, TaskStatus
from src.database.connection import get_async_session


class TaskCrudSkill(BaseSkill):
    """CRUD operations for tasks."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="task_crud",
            version="1.0.0",
            description="Create, read, update, and delete tasks",
            category=SkillCategory.INTERNAL,
            triggers=[
                "create task",
                "add task",
                "new task",
                "make task",
                "delete task",
                "remove task",
                "update task",
                "edit task",
                "modify task",
                "show task",
                "get task",
                "list tasks",
                "show my tasks",
                "what are my tasks",
                "complete task",
                "finish task",
                "mark done",
            ],
            parameters={
                "action": {
                    "type": "string",
                    "enum": ["create", "read", "update", "delete", "list", "complete"],
                    "required": True,
                },
                "task_id": {"type": "string", "required": False},
                "title": {"type": "string", "required": False},
                "description": {"type": "string", "required": False},
                "priority": {"type": "integer", "minimum": 1, "maximum": 5, "required": False},
                "due_date": {"type": "string", "format": "datetime", "required": False},
                "tags": {"type": "array", "items": {"type": "string"}, "required": False},
                "status": {"type": "string", "required": False},
                "filters": {"type": "object", "required": False},
            },
            permission_level=PermissionLevel.INTERNAL,
            approval_required=False,
            data_access=["tasks"],
            external_calls=False,
            timeout_ms=5000,
            load_strategy=LoadStrategy.EAGER,
        )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute CRUD operation."""
        action = context.parameters.get("action")

        if not action:
            return SkillResult(success=False, error="Missing required parameter: action")

        action_handlers = {
            "create": self._create_task,
            "read": self._read_task,
            "update": self._update_task,
            "delete": self._delete_task,
            "list": self._list_tasks,
            "complete": self._complete_task,
        }

        handler = action_handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")

        try:
            async with get_async_session() as session:
                return await handler(session, context)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _create_task(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Create a new task."""
        title = context.parameters.get("title")
        if not title:
            return SkillResult(success=False, error="Missing required parameter: title")

        task = Task(
            id=uuid.uuid4(),
            user_id=uuid.UUID(context.user_id),
            title=title,
            description=context.parameters.get("description", ""),
            priority=context.parameters.get("priority", 3),
            tags=context.parameters.get("tags", []),
            status=TaskStatus.PENDING,
        )

        # Handle due date
        due_date = context.parameters.get("due_date")
        if due_date:
            if isinstance(due_date, str):
                task.due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            else:
                task.due_date = due_date

        session.add(task)
        await session.flush()

        return SkillResult(
            success=True,
            data={
                "task_id": str(task.id),
                "title": task.title,
                "status": task.status.value,
                "priority": task.priority,
                "message": f"Created task: {task.title}",
            },
        )

    async def _read_task(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Read a task by ID."""
        task_id = context.parameters.get("task_id")
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

        return SkillResult(
            success=True,
            data={
                "task_id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status.value,
                "priority": task.priority,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "tags": task.tags,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "result": task.result,
            },
        )

    async def _update_task(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Update a task."""
        task_id = context.parameters.get("task_id")
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

        # Update fields
        updates = {}
        if "title" in context.parameters:
            task.title = context.parameters["title"]
            updates["title"] = task.title
        if "description" in context.parameters:
            task.description = context.parameters["description"]
            updates["description"] = task.description
        if "priority" in context.parameters:
            task.priority = context.parameters["priority"]
            updates["priority"] = task.priority
        if "status" in context.parameters:
            task.status = TaskStatus(context.parameters["status"])
            updates["status"] = task.status.value
        if "due_date" in context.parameters:
            due_date = context.parameters["due_date"]
            if due_date:
                task.due_date = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            else:
                task.due_date = None
            updates["due_date"] = str(task.due_date) if task.due_date else None
        if "tags" in context.parameters:
            task.tags = context.parameters["tags"]
            updates["tags"] = task.tags

        task.updated_at = datetime.utcnow()

        return SkillResult(
            success=True,
            data={
                "task_id": str(task.id),
                "updates": updates,
                "message": f"Updated task: {task.title}",
            },
        )

    async def _delete_task(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Soft delete a task."""
        task_id = context.parameters.get("task_id")
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

        # Soft delete
        task.deleted_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()

        return SkillResult(
            success=True,
            data={
                "task_id": str(task.id),
                "title": task.title,
                "message": f"Deleted task: {task.title}",
            },
        )

    async def _list_tasks(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """List tasks with optional filters."""
        filters = context.parameters.get("filters", {})

        query = select(Task).where(
            Task.user_id == uuid.UUID(context.user_id),
            Task.deleted_at.is_(None),
        )

        # Apply filters
        if "status" in filters:
            query = query.where(Task.status == TaskStatus(filters["status"]))
        if "priority" in filters:
            query = query.where(Task.priority == filters["priority"])
        if "parent_id" in filters:
            if filters["parent_id"]:
                query = query.where(Task.parent_id == uuid.UUID(filters["parent_id"]))
            else:
                query = query.where(Task.parent_id.is_(None))  # Top-level only

        # Default: order by priority desc, then due_date
        query = query.order_by(Task.priority.desc(), Task.due_date.asc().nullslast())

        # Limit
        limit = filters.get("limit", 20)
        query = query.limit(limit)

        result = await session.execute(query)
        tasks = result.scalars().all()

        return SkillResult(
            success=True,
            data={
                "count": len(tasks),
                "tasks": [
                    {
                        "task_id": str(t.id),
                        "title": t.title,
                        "status": t.status.value,
                        "priority": t.priority,
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                        "tags": t.tags,
                    }
                    for t in tasks
                ],
            },
        )

    async def _complete_task(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Mark a task as completed."""
        task_id = context.parameters.get("task_id")
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

        # Mark completed
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        task.result = context.parameters.get("result", "Completed")

        return SkillResult(
            success=True,
            data={
                "task_id": str(task.id),
                "title": task.title,
                "status": "completed",
                "completed_at": task.completed_at.isoformat(),
                "message": f"Completed task: {task.title}",
            },
        )
