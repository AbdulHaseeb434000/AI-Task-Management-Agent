"""Cold Memory - Database/Vector Store memory.

Never loaded directly, queried via skills. Contains:
- All historical tasks
- Complete interaction logs
- Full preference history
- Archived data
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import Task, TaskStatus, Memory, AuditLog, Session, User
from src.database.connection import get_async_session


# Memory type constants
MEMORY_TYPE_CONVERSATION_SUMMARY = "conversation_summary"
MEMORY_TYPE_ARCHIVED = "archived"


@dataclass
class ColdQueryResult:
    """Result from cold memory query."""
    items: List[Dict[str, Any]]
    total_count: int
    has_more: bool
    query_time_ms: float


class ColdMemory:
    """Long-term storage and retrieval.

    Handles queries to the full historical database.
    Never loaded into context directly - used by skills.
    """

    async def query_tasks(
        self,
        user_id: uuid.UUID,
        filters: Optional[Dict[str, Any]] = None,
        search_text: Optional[str] = None,
        include_deleted: bool = False,
        order_by: str = "updated_at",
        order_desc: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> ColdQueryResult:
        """Query all historical tasks.

        Args:
            user_id: The user's ID.
            filters: Optional filters (status, priority, date range, tags).
            search_text: Optional text search in title/description.
            include_deleted: Whether to include soft-deleted tasks.
            order_by: Field to order by.
            order_desc: Whether to order descending.
            limit: Maximum results.
            offset: Result offset for pagination.

        Returns:
            ColdQueryResult with matching tasks.
        """
        start_time = datetime.utcnow()
        filters = filters or {}

        async with get_async_session() as session:
            # Base query
            conditions = [Task.user_id == user_id]

            if not include_deleted:
                conditions.append(Task.deleted_at.is_(None))

            # Apply filters
            if "status" in filters:
                if isinstance(filters["status"], list):
                    conditions.append(Task.status.in_([
                        TaskStatus(s) for s in filters["status"]
                    ]))
                else:
                    conditions.append(Task.status == TaskStatus(filters["status"]))

            if "priority" in filters:
                if isinstance(filters["priority"], dict):
                    if "min" in filters["priority"]:
                        conditions.append(Task.priority >= filters["priority"]["min"])
                    if "max" in filters["priority"]:
                        conditions.append(Task.priority <= filters["priority"]["max"])
                else:
                    conditions.append(Task.priority == filters["priority"])

            if "due_date" in filters:
                due_filter = filters["due_date"]
                if "before" in due_filter:
                    conditions.append(Task.due_date <= due_filter["before"])
                if "after" in due_filter:
                    conditions.append(Task.due_date >= due_filter["after"])

            if "tags" in filters:
                conditions.append(Task.tags.overlap(filters["tags"]))

            if "created_after" in filters:
                conditions.append(Task.created_at >= filters["created_after"])

            if "created_before" in filters:
                conditions.append(Task.created_at <= filters["created_before"])

            # Text search
            if search_text:
                search_conditions = or_(
                    Task.title.ilike(f"%{search_text}%"),
                    Task.description.ilike(f"%{search_text}%"),
                )
                conditions.append(search_conditions)

            # Get total count
            count_result = await session.execute(
                select(func.count(Task.id)).where(and_(*conditions))
            )
            total_count = count_result.scalar()

            # Build order clause
            order_field = getattr(Task, order_by, Task.updated_at)
            order_clause = desc(order_field) if order_desc else order_field

            # Get results
            result = await session.execute(
                select(Task)
                .where(and_(*conditions))
                .order_by(order_clause)
                .limit(limit)
                .offset(offset)
            )
            tasks = result.scalars().all()

        end_time = datetime.utcnow()
        query_time_ms = (end_time - start_time).total_seconds() * 1000

        return ColdQueryResult(
            items=[self._task_to_dict(task) for task in tasks],
            total_count=total_count,
            has_more=offset + len(tasks) < total_count,
            query_time_ms=query_time_ms,
        )

    async def query_interaction_logs(
        self,
        user_id: uuid.UUID,
        event_types: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ColdQueryResult:
        """Query interaction/audit logs.

        Args:
            user_id: The user's ID.
            event_types: Optional filter by event types.
            start_date: Optional start date.
            end_date: Optional end date.
            limit: Maximum results.
            offset: Result offset.

        Returns:
            ColdQueryResult with matching logs.
        """
        start_time = datetime.utcnow()

        async with get_async_session() as session:
            conditions = [AuditLog.user_id == user_id]

            if event_types:
                conditions.append(AuditLog.event_type.in_(event_types))
            if start_date:
                conditions.append(AuditLog.created_at >= start_date)
            if end_date:
                conditions.append(AuditLog.created_at <= end_date)

            # Get count
            count_result = await session.execute(
                select(func.count(AuditLog.id)).where(and_(*conditions))
            )
            total_count = count_result.scalar()

            # Get results
            result = await session.execute(
                select(AuditLog)
                .where(and_(*conditions))
                .order_by(desc(AuditLog.created_at))
                .limit(limit)
                .offset(offset)
            )
            logs = result.scalars().all()

        end_time = datetime.utcnow()
        query_time_ms = (end_time - start_time).total_seconds() * 1000

        return ColdQueryResult(
            items=[
                {
                    "id": str(log.id),
                    "event_type": log.event_type.value if hasattr(log.event_type, 'value') else str(log.event_type),
                    "entity_type": log.entity_type,
                    "entity_id": str(log.entity_id) if log.entity_id else None,
                    "details": log.details,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ],
            total_count=total_count,
            has_more=offset + len(logs) < total_count,
            query_time_ms=query_time_ms,
        )

    async def query_memories(
        self,
        user_id: uuid.UUID,
        memory_types: Optional[List[str]] = None,
        search_content: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ColdQueryResult:
        """Query stored memories.

        Args:
            user_id: The user's ID.
            memory_types: Optional filter by memory types.
            search_content: Optional content search.
            limit: Maximum results.
            offset: Result offset.

        Returns:
            ColdQueryResult with matching memories.
        """
        start_time = datetime.utcnow()

        async with get_async_session() as session:
            conditions = [Memory.user_id == user_id]

            if memory_types:
                conditions.append(Memory.memory_type.in_(memory_types))
            if search_content:
                conditions.append(Memory.content.ilike(f"%{search_content}%"))

            # Get count
            count_result = await session.execute(
                select(func.count(Memory.id)).where(and_(*conditions))
            )
            total_count = count_result.scalar()

            # Get results
            result = await session.execute(
                select(Memory)
                .where(and_(*conditions))
                .order_by(desc(Memory.created_at))
                .limit(limit)
                .offset(offset)
            )
            memories = result.scalars().all()

        end_time = datetime.utcnow()
        query_time_ms = (end_time - start_time).total_seconds() * 1000

        return ColdQueryResult(
            items=[
                {
                    "id": str(memory.id),
                    "type": memory.memory_type.value,
                    "content": memory.content,
                    "metadata": memory.metadata,
                    "created_at": memory.created_at.isoformat(),
                }
                for memory in memories
            ],
            total_count=total_count,
            has_more=offset + len(memories) < total_count,
            query_time_ms=query_time_ms,
        )

    async def get_session_history(
        self,
        user_id: uuid.UUID,
        days_back: int = 30,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get recent session history.

        Args:
            user_id: The user's ID.
            days_back: How many days to look back.
            limit: Maximum sessions.

        Returns:
            List of session summaries.
        """
        cutoff = datetime.utcnow() - timedelta(days=days_back)

        async with get_async_session() as session:
            result = await session.execute(
                select(Session)
                .where(
                    Session.user_id == user_id,
                    Session.created_at >= cutoff,
                )
                .order_by(desc(Session.created_at))
                .limit(limit)
            )
            sessions = result.scalars().all()

        return [
            {
                "id": str(s.id),
                "state": s.state.value if hasattr(s.state, 'value') else str(s.state),
                "created_at": s.created_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "message_count": len(s.conversation_history or []),
            }
            for s in sessions
        ]

    async def get_task_statistics(
        self,
        user_id: uuid.UUID,
        days_back: int = 30,
    ) -> Dict[str, Any]:
        """Get task statistics for the user.

        Args:
            user_id: The user's ID.
            days_back: Days to analyze.

        Returns:
            Dictionary of statistics.
        """
        cutoff = datetime.utcnow() - timedelta(days=days_back)

        async with get_async_session() as session:
            # Total tasks
            total_result = await session.execute(
                select(func.count(Task.id)).where(
                    Task.user_id == user_id,
                    Task.deleted_at.is_(None),
                )
            )
            total_tasks = total_result.scalar()

            # By status
            status_result = await session.execute(
                select(Task.status, func.count(Task.id))
                .where(
                    Task.user_id == user_id,
                    Task.deleted_at.is_(None),
                )
                .group_by(Task.status)
            )
            by_status = {
                row[0].value: row[1]
                for row in status_result.all()
            }

            # Completed in period
            completed_result = await session.execute(
                select(func.count(Task.id)).where(
                    Task.user_id == user_id,
                    Task.status == TaskStatus.COMPLETED,
                    Task.completed_at >= cutoff,
                )
            )
            completed_in_period = completed_result.scalar()

            # Created in period
            created_result = await session.execute(
                select(func.count(Task.id)).where(
                    Task.user_id == user_id,
                    Task.created_at >= cutoff,
                    Task.deleted_at.is_(None),
                )
            )
            created_in_period = created_result.scalar()

            # Overdue
            overdue_result = await session.execute(
                select(func.count(Task.id)).where(
                    Task.user_id == user_id,
                    Task.deleted_at.is_(None),
                    Task.status != TaskStatus.COMPLETED,
                    Task.due_date < datetime.utcnow(),
                )
            )
            overdue_count = overdue_result.scalar()

            # Average completion time (for tasks with due dates)
            avg_completion_time = None
            # This would require more complex query to calculate properly

        return {
            "total_tasks": total_tasks,
            "by_status": by_status,
            "completed_in_period": completed_in_period,
            "created_in_period": created_in_period,
            "overdue_count": overdue_count,
            "period_days": days_back,
            "completion_rate": (
                completed_in_period / created_in_period
                if created_in_period > 0 else 0
            ),
        }

    async def archive_old_data(
        self,
        user_id: uuid.UUID,
        days_old: int = 90,
    ) -> Dict[str, int]:
        """Archive/compact old data.

        Args:
            user_id: The user's ID.
            days_old: Archive data older than this.

        Returns:
            Dictionary with counts of archived items.
        """
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        archived = {"sessions": 0, "memories": 0}

        async with get_async_session() as session:
            # Archive old memories by summarizing
            old_memories = await session.execute(
                select(Memory).where(
                    Memory.user_id == user_id,
                    Memory.created_at < cutoff,
                    Memory.memory_type == MEMORY_TYPE_CONVERSATION_SUMMARY,
                )
            )
            memories = old_memories.scalars().all()

            if memories:
                # Create a summary of summaries
                combined_content = "\n".join([m.content for m in memories[:10]])
                if combined_content:
                    archived_memory = Memory(
                        user_id=user_id,
                        memory_type=MEMORY_TYPE_ARCHIVED,
                        source_type="archive",
                        content=f"Archived summaries from {cutoff.date()}: {combined_content[:1000]}",
                        metadata={"archived_count": len(memories)},
                    )
                    session.add(archived_memory)

                    # Delete old memories
                    for memory in memories:
                        await session.delete(memory)
                    archived["memories"] = len(memories)

        return archived

    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        """Convert a Task to dictionary.

        Args:
            task: The Task object.

        Returns:
            Dictionary representation.
        """
        return {
            "id": str(task.id),
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "tags": task.tags,
            "parent_id": str(task.parent_id) if task.parent_id else None,
            "plan_id": str(task.plan_id) if task.plan_id else None,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "deleted_at": task.deleted_at.isoformat() if task.deleted_at else None,
        }
