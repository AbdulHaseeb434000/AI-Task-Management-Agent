"""Search Skill - Search tasks and history.

Full-text and filtered search across tasks.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, or_, and_, func
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


class SearchSkill(BaseSkill):
    """Search tasks and history."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="search",
            version="1.0.0",
            description="Search tasks, history, and filter by various criteria",
            category=SkillCategory.INTERNAL,
            triggers=[
                "search",
                "find",
                "look for",
                "where is",
                "show me",
                "filter",
                "tasks with",
                "tasks about",
            ],
            parameters={
                "action": {
                    "type": "string",
                    "enum": ["search", "filter", "recent", "stats"],
                    "required": True,
                },
                "query": {"type": "string", "required": False},
                "filters": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "priority": {"type": "integer"},
                        "priority_min": {"type": "integer"},
                        "priority_max": {"type": "integer"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "has_due_date": {"type": "boolean"},
                        "created_after": {"type": "string"},
                        "created_before": {"type": "string"},
                    },
                    "required": False,
                },
                "limit": {"type": "integer", "required": False},
            },
            permission_level=PermissionLevel.INTERNAL,
            approval_required=False,
            data_access=["tasks"],
            timeout_ms=5000,
            load_strategy=LoadStrategy.EAGER,
        )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute search operation."""
        action = context.parameters.get("action", "search")

        action_handlers = {
            "search": self._text_search,
            "filter": self._filter_search,
            "recent": self._recent_tasks,
            "stats": self._get_stats,
        }

        handler = action_handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")

        try:
            async with get_async_session() as session:
                return await handler(session, context)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _text_search(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Search tasks by text query."""
        query_text = context.parameters.get("query", "")
        limit = context.parameters.get("limit", 20)

        if not query_text:
            return SkillResult(success=False, error="Search query is required")

        # Simple text search (PostgreSQL full-text could be added)
        search_pattern = f"%{query_text.lower()}%"

        result = await session.execute(
            select(Task).where(
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
                or_(
                    func.lower(Task.title).like(search_pattern),
                    func.lower(Task.description).like(search_pattern),
                ),
            ).order_by(Task.updated_at.desc()).limit(limit)
        )
        tasks = result.scalars().all()

        return SkillResult(
            success=True,
            data={
                "query": query_text,
                "count": len(tasks),
                "tasks": [
                    {
                        "task_id": str(t.id),
                        "title": t.title,
                        "description": (t.description or "")[:100],
                        "status": t.status.value,
                        "priority": t.priority,
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                    }
                    for t in tasks
                ],
            },
        )

    async def _filter_search(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Search tasks with multiple filters."""
        filters = context.parameters.get("filters", {})
        limit = context.parameters.get("limit", 20)

        query = select(Task).where(
            Task.user_id == uuid.UUID(context.user_id),
            Task.deleted_at.is_(None),
        )

        # Apply filters
        if "status" in filters:
            query = query.where(Task.status == TaskStatus(filters["status"]))

        if "priority" in filters:
            query = query.where(Task.priority == filters["priority"])

        if "priority_min" in filters:
            query = query.where(Task.priority >= filters["priority_min"])

        if "priority_max" in filters:
            query = query.where(Task.priority <= filters["priority_max"])

        if "tags" in filters and filters["tags"]:
            # Tasks that have ANY of the specified tags
            for tag in filters["tags"]:
                query = query.where(Task.tags.contains([tag]))

        if filters.get("has_due_date"):
            query = query.where(Task.due_date.isnot(None))
        elif filters.get("has_due_date") is False:
            query = query.where(Task.due_date.is_(None))

        if "created_after" in filters:
            try:
                after = datetime.fromisoformat(filters["created_after"])
                query = query.where(Task.created_at >= after)
            except ValueError:
                pass

        if "created_before" in filters:
            try:
                before = datetime.fromisoformat(filters["created_before"])
                query = query.where(Task.created_at <= before)
            except ValueError:
                pass

        query = query.order_by(Task.priority.desc(), Task.updated_at.desc()).limit(limit)

        result = await session.execute(query)
        tasks = result.scalars().all()

        return SkillResult(
            success=True,
            data={
                "filters_applied": filters,
                "count": len(tasks),
                "tasks": [
                    {
                        "task_id": str(t.id),
                        "title": t.title,
                        "status": t.status.value,
                        "priority": t.priority,
                        "tags": t.tags,
                        "due_date": t.due_date.isoformat() if t.due_date else None,
                    }
                    for t in tasks
                ],
            },
        )

    async def _recent_tasks(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Get recently modified/created tasks."""
        limit = context.parameters.get("limit", 10)
        days = context.parameters.get("filters", {}).get("days", 7)

        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await session.execute(
            select(Task).where(
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
                Task.updated_at >= cutoff,
            ).order_by(Task.updated_at.desc()).limit(limit)
        )
        tasks = result.scalars().all()

        return SkillResult(
            success=True,
            data={
                "days": days,
                "count": len(tasks),
                "tasks": [
                    {
                        "task_id": str(t.id),
                        "title": t.title,
                        "status": t.status.value,
                        "updated_at": t.updated_at.isoformat(),
                        "created_at": t.created_at.isoformat(),
                    }
                    for t in tasks
                ],
            },
        )

    async def _get_stats(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Get task statistics."""
        user_id = uuid.UUID(context.user_id)

        # Get counts by status
        result = await session.execute(
            select(Task.status, func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.deleted_at.is_(None),
            ).group_by(Task.status)
        )
        status_counts = {row[0].value: row[1] for row in result.all()}

        # Get total count
        total_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.deleted_at.is_(None),
            )
        )
        total = total_result.scalar() or 0

        # Get overdue count
        now = datetime.utcnow()
        overdue_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.deleted_at.is_(None),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                Task.due_date.isnot(None),
                Task.due_date < now,
            )
        )
        overdue = overdue_result.scalar() or 0

        # Get due today count
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        due_today_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.deleted_at.is_(None),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
                Task.due_date >= today_start,
                Task.due_date < today_end,
            )
        )
        due_today = due_today_result.scalar() or 0

        # Completion rate (last 30 days)
        month_ago = now - timedelta(days=30)
        completed_result = await session.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.COMPLETED,
                Task.completed_at >= month_ago,
            )
        )
        completed_month = completed_result.scalar() or 0

        return SkillResult(
            success=True,
            data={
                "total_tasks": total,
                "by_status": status_counts,
                "overdue": overdue,
                "due_today": due_today,
                "completed_last_30_days": completed_month,
                "summary": {
                    "pending": status_counts.get("pending", 0),
                    "in_progress": status_counts.get("in_progress", 0),
                    "completed": status_counts.get("completed", 0),
                    "blocked": status_counts.get("blocked", 0),
                },
            },
        )
