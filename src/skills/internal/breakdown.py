"""Breakdown Skill - Split complex tasks into subtasks.

Analyzes task complexity and creates manageable subtasks.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

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
from src.database.orm import Task, Plan, TaskStatus
from src.database.connection import get_async_session


class BreakdownSkill(BaseSkill):
    """Break down complex tasks into subtasks."""

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="breakdown",
            version="1.0.0",
            description="Split complex tasks into manageable subtasks",
            category=SkillCategory.INTERNAL,
            triggers=[
                "break down",
                "breakdown",
                "split task",
                "divide task",
                "create subtasks",
                "make subtasks",
                "decompose",
                "this is too big",
            ],
            parameters={
                "action": {
                    "type": "string",
                    "enum": ["analyze", "breakdown", "create_subtasks"],
                    "required": True,
                },
                "task_id": {"type": "string", "required": True},
                "subtasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "priority": {"type": "integer"},
                            "estimated_minutes": {"type": "integer"},
                        },
                    },
                    "required": False,
                },
                "max_subtasks": {"type": "integer", "required": False},
            },
            permission_level=PermissionLevel.INTERNAL,
            approval_required=False,
            data_access=["tasks", "plans"],
            timeout_ms=10000,
            load_strategy=LoadStrategy.EAGER,
        )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute breakdown operation."""
        action = context.parameters.get("action", "analyze")

        action_handlers = {
            "analyze": self._analyze_complexity,
            "breakdown": self._suggest_breakdown,
            "create_subtasks": self._create_subtasks,
        }

        handler = action_handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")

        try:
            async with get_async_session() as session:
                return await handler(session, context)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _get_task(self, session: AsyncSession, task_id: str, user_id: str) -> Optional[Task]:
        """Get a task by ID."""
        result = await session.execute(
            select(Task).where(
                Task.id == uuid.UUID(task_id),
                Task.user_id == uuid.UUID(user_id),
                Task.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _analyze_complexity(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Analyze task complexity to determine if breakdown is needed."""
        task_id = context.parameters.get("task_id")
        if not task_id:
            return SkillResult(success=False, error="Missing required parameter: task_id")

        task = await self._get_task(session, task_id, context.user_id)
        if not task:
            return SkillResult(success=False, error=f"Task not found: {task_id}")

        # Analyze complexity signals
        complexity_score = 0
        signals = []

        # Check description length
        desc_len = len(task.description or "")
        if desc_len > 500:
            complexity_score += 2
            signals.append("long description")
        elif desc_len > 200:
            complexity_score += 1

        # Check for multiple action words
        action_words = ["and", "then", "also", "plus", "additionally", "next", "after"]
        text = f"{task.title} {task.description or ""}".lower()
        action_count = sum(1 for word in action_words if word in text)
        if action_count >= 3:
            complexity_score += 2
            signals.append("multiple actions mentioned")
        elif action_count >= 1:
            complexity_score += 1

        # Check for time estimates
        if task.estimated_minutes and task.estimated_minutes > 120:
            complexity_score += 2
            signals.append("long time estimate")
        elif task.estimated_minutes and task.estimated_minutes > 60:
            complexity_score += 1

        # Check existing subtasks
        result = await session.execute(
            select(Task).where(
                Task.parent_id == task.id,
                Task.deleted_at.is_(None),
            )
        )
        existing_subtasks = result.scalars().all()

        recommendation = "simple"
        if complexity_score >= 4:
            recommendation = "strongly_recommend_breakdown"
        elif complexity_score >= 2:
            recommendation = "consider_breakdown"

        return SkillResult(
            success=True,
            data={
                "task_id": str(task.id),
                "title": task.title,
                "complexity_score": complexity_score,
                "signals": signals,
                "recommendation": recommendation,
                "existing_subtasks": len(existing_subtasks),
                "message": self._get_complexity_message(complexity_score, signals),
            },
        )

    def _get_complexity_message(self, score: int, signals: List[str]) -> str:
        """Get human-readable complexity message."""
        if score >= 4:
            return f"This task seems complex ({', '.join(signals)}). I recommend breaking it down into smaller subtasks."
        elif score >= 2:
            return f"This task might benefit from being split ({', '.join(signals)})."
        else:
            return "This task seems manageable as is."

    async def _suggest_breakdown(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Suggest how to break down a task.

        Note: In a real implementation, this would use the LLM to analyze
        the task and suggest meaningful subtasks. For now, we provide a
        structure for the breakdown.
        """
        task_id = context.parameters.get("task_id")
        if not task_id:
            return SkillResult(success=False, error="Missing required parameter: task_id")

        task = await self._get_task(session, task_id, context.user_id)
        if not task:
            return SkillResult(success=False, error=f"Task not found: {task_id}")

        max_subtasks = context.parameters.get("max_subtasks", 5)

        # This would be replaced with LLM-generated suggestions
        # For now, provide a template structure
        suggested_structure = {
            "task_id": str(task.id),
            "title": task.title,
            "suggested_subtasks": [
                {
                    "title": f"Research/Plan: {task.title}",
                    "description": "Gather requirements and plan approach",
                    "priority": task.priority,
                    "order": 1,
                },
                {
                    "title": f"Execute: {task.title}",
                    "description": "Complete the main work",
                    "priority": task.priority,
                    "order": 2,
                },
                {
                    "title": f"Review/Verify: {task.title}",
                    "description": "Check results and finalize",
                    "priority": task.priority,
                    "order": 3,
                },
            ][:max_subtasks],
            "message": "Here's a suggested breakdown. You can customize these subtasks.",
            "note": "For better suggestions, provide more details in the task description.",
        }

        return SkillResult(success=True, data=suggested_structure)

    async def _create_subtasks(self, session: AsyncSession, context: SkillContext) -> SkillResult:
        """Create subtasks for a parent task."""
        task_id = context.parameters.get("task_id")
        subtasks_data = context.parameters.get("subtasks", [])

        if not task_id:
            return SkillResult(success=False, error="Missing required parameter: task_id")

        if not subtasks_data:
            return SkillResult(success=False, error="No subtasks provided")

        parent_task = await self._get_task(session, task_id, context.user_id)
        if not parent_task:
            return SkillResult(success=False, error=f"Task not found: {task_id}")

        created_subtasks = []
        for i, subtask_data in enumerate(subtasks_data):
            subtask = Task(
                id=uuid.uuid4(),
                user_id=uuid.UUID(context.user_id),
                parent_id=parent_task.id,
                title=subtask_data.get("title", f"Subtask {i + 1}"),
                description=subtask_data.get("description", ""),
                priority=subtask_data.get("priority", parent_task.priority),
                status=TaskStatus.PENDING,
                estimated_minutes=subtask_data.get("estimated_minutes"),
                tags=parent_task.tags.copy() if parent_task.tags else [],
            )
            session.add(subtask)
            created_subtasks.append({
                "task_id": str(subtask.id),
                "title": subtask.title,
                "order": i + 1,
            })

        # Update parent task status to indicate it has subtasks
        parent_task.task_metadata = parent_task.task_metadata or {}
        parent_task.task_metadata["has_subtasks"] = True
        parent_task.task_metadata["subtask_count"] = len(created_subtasks)

        await session.flush()

        return SkillResult(
            success=True,
            data={
                "parent_task_id": str(parent_task.id),
                "parent_title": parent_task.title,
                "created_subtasks": created_subtasks,
                "count": len(created_subtasks),
                "message": f"Created {len(created_subtasks)} subtasks for '{parent_task.title}'",
            },
        )
