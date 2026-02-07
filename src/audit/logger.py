"""Audit Logger - Records all agent actions.

Provides:
- Action logging with full context
- Undo tracking
- Query capabilities
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import AuditLog, EventType, UndoAction
from src.database.connection import get_async_session


@dataclass
class AuditEntry:
    """An audit log entry."""
    id: uuid.UUID
    user_id: uuid.UUID
    event_type: EventType
    entity_type: str
    entity_id: Optional[uuid.UUID]
    details: Dict[str, Any]
    session_id: Optional[uuid.UUID]
    created_at: datetime
    can_undo: bool = False


class AuditLogger:
    """Logs and tracks all agent actions.

    Provides:
    - Comprehensive action logging
    - Undo support for reversible actions
    - Query and search capabilities
    """

    async def log(
        self,
        user_id: uuid.UUID,
        event_type: EventType,
        entity_type: str,
        entity_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[uuid.UUID] = None,
        undo_data: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log an action.

        Args:
            user_id: The user's ID.
            event_type: Type of event.
            entity_type: Type of entity (task, reminder, etc).
            entity_id: ID of the affected entity.
            details: Additional details.
            session_id: Optional session ID.
            undo_data: Data needed to undo this action.

        Returns:
            The created AuditEntry.
        """
        async with get_async_session() as session:
            # Create audit log
            log_entry = AuditLog(
                user_id=user_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details or {},
                session_id=session_id,
            )
            session.add(log_entry)
            await session.flush()

            # Create undo action if provided
            if undo_data:
                undo = UndoAction(
                    audit_log_id=log_entry.id,
                    user_id=user_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    action_type=event_type.value,
                    undo_data=undo_data,
                )
                session.add(undo)

            await session.commit()

        return AuditEntry(
            id=log_entry.id,
            user_id=user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            session_id=session_id,
            created_at=log_entry.created_at,
            can_undo=undo_data is not None,
        )

    async def log_task_created(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        title: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> AuditEntry:
        """Log task creation.

        Args:
            user_id: The user's ID.
            task_id: The new task's ID.
            title: Task title.
            session_id: Optional session ID.

        Returns:
            AuditEntry.
        """
        return await self.log(
            user_id=user_id,
            event_type=EventType.TASK_CREATED,
            entity_type="task",
            entity_id=task_id,
            details={"title": title},
            session_id=session_id,
            undo_data={"action": "delete", "task_id": str(task_id)},
        )

    async def log_task_updated(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        changes: Dict[str, Any],
        previous_values: Dict[str, Any],
        session_id: Optional[uuid.UUID] = None,
    ) -> AuditEntry:
        """Log task update.

        Args:
            user_id: The user's ID.
            task_id: The task's ID.
            changes: What was changed.
            previous_values: Previous values for undo.
            session_id: Optional session ID.

        Returns:
            AuditEntry.
        """
        return await self.log(
            user_id=user_id,
            event_type=EventType.TASK_UPDATED,
            entity_type="task",
            entity_id=task_id,
            details={"changes": changes},
            session_id=session_id,
            undo_data={
                "action": "update",
                "task_id": str(task_id),
                "restore_values": previous_values,
            },
        )

    async def log_task_completed(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        title: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> AuditEntry:
        """Log task completion.

        Args:
            user_id: The user's ID.
            task_id: The task's ID.
            title: Task title.
            session_id: Optional session ID.

        Returns:
            AuditEntry.
        """
        return await self.log(
            user_id=user_id,
            event_type=EventType.TASK_COMPLETED,
            entity_type="task",
            entity_id=task_id,
            details={"title": title},
            session_id=session_id,
            undo_data={
                "action": "uncomplete",
                "task_id": str(task_id),
            },
        )

    async def log_task_deleted(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        task_data: Dict[str, Any],
        session_id: Optional[uuid.UUID] = None,
    ) -> AuditEntry:
        """Log task deletion.

        Args:
            user_id: The user's ID.
            task_id: The task's ID.
            task_data: Full task data for potential restore.
            session_id: Optional session ID.

        Returns:
            AuditEntry.
        """
        return await self.log(
            user_id=user_id,
            event_type=EventType.TASK_DELETED,
            entity_type="task",
            entity_id=task_id,
            details={"title": task_data.get("title")},
            session_id=session_id,
            undo_data={
                "action": "restore",
                "task_data": task_data,
            },
        )

    async def log_skill_executed(
        self,
        user_id: uuid.UUID,
        skill_name: str,
        parameters: Dict[str, Any],
        result: Dict[str, Any],
        session_id: Optional[uuid.UUID] = None,
    ) -> AuditEntry:
        """Log skill execution.

        Args:
            user_id: The user's ID.
            skill_name: Name of the skill.
            parameters: Skill parameters.
            result: Skill result.
            session_id: Optional session ID.

        Returns:
            AuditEntry.
        """
        return await self.log(
            user_id=user_id,
            event_type=EventType.SKILL_EXECUTED,
            entity_type="skill",
            details={
                "skill_name": skill_name,
                "parameters": parameters,
                "result_summary": self._summarize_result(result),
            },
            session_id=session_id,
        )

    async def log_approval_requested(
        self,
        user_id: uuid.UUID,
        approval_id: uuid.UUID,
        action_type: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> AuditEntry:
        """Log approval request.

        Args:
            user_id: The user's ID.
            approval_id: The approval's ID.
            action_type: Type of action.
            session_id: Optional session ID.

        Returns:
            AuditEntry.
        """
        return await self.log(
            user_id=user_id,
            event_type=EventType.APPROVAL_REQUESTED,
            entity_type="approval",
            entity_id=approval_id,
            details={"action_type": action_type},
            session_id=session_id,
        )

    async def log_approval_response(
        self,
        user_id: uuid.UUID,
        approval_id: uuid.UUID,
        approved: bool,
        session_id: Optional[uuid.UUID] = None,
    ) -> AuditEntry:
        """Log approval response.

        Args:
            user_id: The user's ID.
            approval_id: The approval's ID.
            approved: Whether it was approved.
            session_id: Optional session ID.

        Returns:
            AuditEntry.
        """
        event_type = (
            EventType.APPROVAL_GRANTED if approved
            else EventType.APPROVAL_DENIED
        )
        return await self.log(
            user_id=user_id,
            event_type=event_type,
            entity_type="approval",
            entity_id=approval_id,
            details={"approved": approved},
            session_id=session_id,
        )

    async def log_session_started(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> AuditEntry:
        """Log session start.

        Args:
            user_id: The user's ID.
            session_id: The session ID.

        Returns:
            AuditEntry.
        """
        return await self.log(
            user_id=user_id,
            event_type=EventType.SESSION_STARTED,
            entity_type="session",
            entity_id=session_id,
            session_id=session_id,
        )

    async def log_session_ended(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        message_count: int,
    ) -> AuditEntry:
        """Log session end.

        Args:
            user_id: The user's ID.
            session_id: The session ID.
            message_count: Number of messages in session.

        Returns:
            AuditEntry.
        """
        return await self.log(
            user_id=user_id,
            event_type=EventType.SESSION_ENDED,
            entity_type="session",
            entity_id=session_id,
            details={"message_count": message_count},
            session_id=session_id,
        )

    async def get_recent(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        event_types: Optional[List[EventType]] = None,
    ) -> List[AuditEntry]:
        """Get recent audit entries.

        Args:
            user_id: The user's ID.
            limit: Maximum entries.
            event_types: Optional filter by event types.

        Returns:
            List of AuditEntry.
        """
        async with get_async_session() as session:
            conditions = [AuditLog.user_id == user_id]
            if event_types:
                conditions.append(AuditLog.event_type.in_(event_types))

            result = await session.execute(
                select(AuditLog)
                .where(and_(*conditions))
                .order_by(desc(AuditLog.created_at))
                .limit(limit)
            )
            logs = result.scalars().all()

        return [
            AuditEntry(
                id=log.id,
                user_id=log.user_id,
                event_type=log.event_type,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                details=log.details or {},
                session_id=log.session_id,
                created_at=log.created_at,
            )
            for log in logs
        ]

    async def get_undoable_actions(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent undoable actions.

        Args:
            user_id: The user's ID.
            limit: Maximum actions.

        Returns:
            List of undoable action info.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(UndoAction)
                .where(
                    UndoAction.user_id == user_id,
                    UndoAction.undone_at.is_(None),
                )
                .order_by(desc(UndoAction.created_at))
                .limit(limit)
            )
            undos = result.scalars().all()

        return [
            {
                "id": str(undo.id),
                "audit_log_id": str(undo.audit_log_id),
                "action_type": undo.action_type,
                "entity_type": undo.entity_type,
                "entity_id": str(undo.entity_id) if undo.entity_id else None,
                "created_at": undo.created_at.isoformat(),
            }
            for undo in undos
        ]

    async def undo(
        self,
        undo_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Undo an action.

        Args:
            undo_id: The undo action ID.
            user_id: The user's ID.

        Returns:
            Result of the undo operation.
        """
        async with get_async_session() as session:
            undo = await session.get(UndoAction, undo_id)

            if not undo:
                return {"success": False, "error": "Undo action not found"}

            if undo.user_id != user_id:
                return {"success": False, "error": "Not authorized"}

            if undo.undone_at:
                return {"success": False, "error": "Already undone"}

            # Execute the undo based on action type
            result = await self._execute_undo(undo.undo_data)

            if result["success"]:
                undo.undone_at = datetime.utcnow()
                await session.commit()

            return result

    async def _execute_undo(
        self,
        undo_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an undo operation.

        Args:
            undo_data: The undo data.

        Returns:
            Result dict.
        """
        action = undo_data.get("action")

        if action == "delete":
            # Undo task creation by deleting
            from src.database.orm import Task
            task_id = uuid.UUID(undo_data["task_id"])
            async with get_async_session() as session:
                task = await session.get(Task, task_id)
                if task:
                    task.deleted_at = datetime.utcnow()
                    await session.commit()
                    return {"success": True, "message": "Task deleted"}
            return {"success": False, "error": "Task not found"}

        elif action == "update":
            # Undo update by restoring previous values
            from src.database.orm import Task
            task_id = uuid.UUID(undo_data["task_id"])
            restore_values = undo_data.get("restore_values", {})
            async with get_async_session() as session:
                task = await session.get(Task, task_id)
                if task:
                    for key, value in restore_values.items():
                        if hasattr(task, key):
                            setattr(task, key, value)
                    await session.commit()
                    return {"success": True, "message": "Task restored"}
            return {"success": False, "error": "Task not found"}

        elif action == "uncomplete":
            # Undo completion
            from src.database.orm import Task, TaskStatus
            task_id = uuid.UUID(undo_data["task_id"])
            async with get_async_session() as session:
                task = await session.get(Task, task_id)
                if task:
                    task.status = TaskStatus.PENDING
                    task.completed_at = None
                    await session.commit()
                    return {"success": True, "message": "Task uncompleted"}
            return {"success": False, "error": "Task not found"}

        elif action == "restore":
            # Restore deleted task
            from src.database.orm import Task, TaskStatus
            task_data = undo_data.get("task_data", {})
            async with get_async_session() as session:
                task = Task(
                    id=uuid.UUID(task_data["id"]) if "id" in task_data else uuid.uuid4(),
                    user_id=uuid.UUID(task_data["user_id"]),
                    title=task_data.get("title", "Restored Task"),
                    description=task_data.get("description"),
                    status=TaskStatus(task_data.get("status", "pending")),
                    priority=task_data.get("priority", 3),
                    tags=task_data.get("tags", []),
                )
                session.add(task)
                await session.commit()
                return {"success": True, "message": "Task restored"}

        return {"success": False, "error": f"Unknown action: {action}"}

    def _summarize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize a result for logging.

        Args:
            result: The full result.

        Returns:
            Summarized result.
        """
        summary = {}

        if "success" in result:
            summary["success"] = result["success"]
        if "error" in result:
            summary["error"] = result["error"]
        if "data" in result:
            data = result["data"]
            if isinstance(data, dict):
                summary["data_keys"] = list(data.keys())
            elif isinstance(data, list):
                summary["data_count"] = len(data)

        return summary


# Global logger
_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger."""
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger
