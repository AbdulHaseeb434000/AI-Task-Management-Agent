"""Prioritize Skill - Priority scoring and task ordering.

Analyzes tasks and suggests optimal priority based on:
- Due dates (urgency)
- Dependencies (blocking others)
- User patterns (preferences)
- Explicit signals in task description
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy import select
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


class PrioritizeSkill(BaseSkill):
    """Priority scoring and task ordering."""

    # Keywords that suggest urgency
    URGENT_KEYWORDS = {
        "urgent", "asap", "immediately", "critical", "emergency",
        "deadline", "today", "now", "important", "priority"
    }

    LOW_PRIORITY_KEYWORDS = {
        "someday", "eventually", "when possible", "nice to have",
        "optional", "maybe", "if time", "low priority"
    }

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="prioritize",
            version="1.0.0",
            description="Priority scoring algorithm for tasks",
            category=SkillCategory.INTERNAL,
            triggers=[
                "prioritize",
                "what should i do first",
                "what's most important",
                "order my tasks",
                "rank tasks",
                "suggest priority",
                "reprioritize",
            ],
            parameters={
                "action": {
                    "type": "string",
                    "enum": ["score", "reorder", "suggest", "what_next"],
                    "required": True,
                },
                "task_id": {"type": "string", "required": False},
                "task_ids": {"type": "array", "items": {"type": "string"}, "required": False},
            },
            permission_level=PermissionLevel.INTERNAL,
            approval_required=False,
            data_access=["tasks"],
            timeout_ms=5000,
            load_strategy=LoadStrategy.EAGER,
        )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute prioritization."""
        action = context.parameters.get("action", "what_next")

        action_handlers = {
            "score": self._score_task,
            "reorder": self._reorder_tasks,
            "suggest": self._suggest_priority,
            "what_next": self._what_next,
        }

        handler = action_handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")

        try:
            async with get_async_session() as session:
                return await handler(session, context)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def _calculate_priority_score(self, task: Task, now: datetime) -> Dict[str, Any]:
        """Calculate priority score for a task.

        Scoring factors:
        - Base priority (user-set): 1-5 → 0-40 points
        - Due date urgency: 0-30 points
        - Keyword signals: -10 to +20 points
        - Blocking factor: 0-10 points (if others depend on this)

        Returns:
            Dict with score and breakdown
        """
        breakdown = {}

        # Base priority (max 40 points)
        base_score = (task.priority / 5) * 40
        breakdown["base_priority"] = round(base_score, 1)

        # Due date urgency (max 30 points)
        urgency_score = 0
        if task.due_date:
            time_until = (task.due_date - now).total_seconds()
            hours_until = time_until / 3600

            if hours_until < 0:
                # Overdue - maximum urgency
                urgency_score = 30
            elif hours_until < 4:
                urgency_score = 28
            elif hours_until < 24:
                urgency_score = 25
            elif hours_until < 48:
                urgency_score = 20
            elif hours_until < 72:
                urgency_score = 15
            elif hours_until < 168:  # 1 week
                urgency_score = 10
            else:
                urgency_score = 5

        breakdown["due_date_urgency"] = urgency_score

        # Keyword signals (-10 to +20 points)
        keyword_score = 0
        text = f"{task.title} {task.description or ''}".lower()

        for keyword in self.URGENT_KEYWORDS:
            if keyword in text:
                keyword_score += 5
                break  # Only count once

        for keyword in self.LOW_PRIORITY_KEYWORDS:
            if keyword in text:
                keyword_score -= 5
                break

        keyword_score = max(-10, min(20, keyword_score))
        breakdown["keyword_signals"] = keyword_score

        # Blocking factor (if task has dependents)
        # This would need to check dependents in real implementation
        blocking_score = 0
        breakdown["blocking_factor"] = blocking_score

        total = base_score + urgency_score + keyword_score + blocking_score
        breakdown["total"] = round(total, 1)

        return breakdown

    async def _score_task(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Score a single task."""
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

        now = datetime.utcnow()
        score = self._calculate_priority_score(task, now)

        return SkillResult(
            success=True,
            data={
                "task_id": str(task.id),
                "title": task.title,
                "current_priority": task.priority,
                "calculated_score": score["total"],
                "breakdown": score,
                "suggested_priority": min(5, max(1, int(score["total"] / 20) + 1)),
            },
        )

    async def _reorder_tasks(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Reorder tasks by calculated priority."""
        task_ids = context.parameters.get("task_ids", [])

        query = select(Task).where(
            Task.user_id == uuid.UUID(context.user_id),
            Task.deleted_at.is_(None),
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
        )

        if task_ids:
            query = query.where(Task.id.in_([uuid.UUID(tid) for tid in task_ids]))

        result = await session.execute(query)
        tasks = result.scalars().all()

        now = datetime.utcnow()
        scored_tasks = []
        for task in tasks:
            score = self._calculate_priority_score(task, now)
            scored_tasks.append({
                "task_id": str(task.id),
                "title": task.title,
                "score": score["total"],
                "current_priority": task.priority,
            })

        # Sort by score descending
        scored_tasks.sort(key=lambda x: x["score"], reverse=True)

        return SkillResult(
            success=True,
            data={
                "ordered_tasks": scored_tasks,
                "count": len(scored_tasks),
            },
        )

    async def _suggest_priority(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Suggest priority adjustments for tasks."""
        result = await session.execute(
            select(Task).where(
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            )
        )
        tasks = result.scalars().all()

        now = datetime.utcnow()
        suggestions = []

        for task in tasks:
            score = self._calculate_priority_score(task, now)
            suggested = min(5, max(1, int(score["total"] / 20) + 1))

            if suggested != task.priority:
                suggestions.append({
                    "task_id": str(task.id),
                    "title": task.title,
                    "current_priority": task.priority,
                    "suggested_priority": suggested,
                    "reason": self._get_suggestion_reason(task, score),
                })

        return SkillResult(
            success=True,
            data={
                "suggestions": suggestions,
                "count": len(suggestions),
            },
        )

    def _get_suggestion_reason(self, task: Task, score: Dict) -> str:
        """Get human-readable reason for priority suggestion."""
        reasons = []

        if score["due_date_urgency"] >= 25:
            reasons.append("approaching deadline")
        elif score["due_date_urgency"] == 30:
            reasons.append("overdue")

        if score["keyword_signals"] > 0:
            reasons.append("marked as urgent")
        elif score["keyword_signals"] < 0:
            reasons.append("marked as low priority")

        if not reasons:
            reasons.append("based on overall score")

        return ", ".join(reasons)

    async def _what_next(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Suggest what task to work on next."""
        result = await session.execute(
            select(Task).where(
                Task.user_id == uuid.UUID(context.user_id),
                Task.deleted_at.is_(None),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            )
        )
        tasks = result.scalars().all()

        if not tasks:
            return SkillResult(
                success=True,
                data={
                    "message": "No pending tasks. You're all caught up!",
                    "next_task": None,
                },
            )

        now = datetime.utcnow()
        scored_tasks = []
        for task in tasks:
            score = self._calculate_priority_score(task, now)
            scored_tasks.append((task, score["total"]))

        # Sort by score descending
        scored_tasks.sort(key=lambda x: x[1], reverse=True)

        top_task, top_score = scored_tasks[0]

        return SkillResult(
            success=True,
            data={
                "next_task": {
                    "task_id": str(top_task.id),
                    "title": top_task.title,
                    "description": top_task.description,
                    "priority": top_task.priority,
                    "due_date": top_task.due_date.isoformat() if top_task.due_date else None,
                    "score": round(top_score, 1),
                },
                "alternatives": [
                    {
                        "task_id": str(t.id),
                        "title": t.title,
                        "score": round(s, 1),
                    }
                    for t, s in scored_tasks[1:4]  # Top 3 alternatives
                ],
                "message": f"I suggest working on: {top_task.title}",
            },
        )
