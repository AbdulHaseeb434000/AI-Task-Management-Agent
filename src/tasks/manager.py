"""Task Manager - High-level task operations.

Provides a unified interface for task CRUD and graph operations.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import Task, TaskStatus
from src.database.connection import get_async_session
from src.tasks.graph import TaskGraph, TaskNode, GraphValidationError


class TaskManager:
    """High-level task management operations.

    Combines database operations with graph management for:
    - Task CRUD with dependency awareness
    - Automatic blocking status updates
    - Subtask management
    - Graph-aware prioritization
    """

    def __init__(self):
        """Initialize the task manager."""
        self._graphs: Dict[uuid.UUID, TaskGraph] = {}  # User ID -> Graph

    async def get_graph(self, user_id: uuid.UUID) -> TaskGraph:
        """Get or create a task graph for a user.

        Args:
            user_id: The user's ID.

        Returns:
            TaskGraph for the user.
        """
        if user_id not in self._graphs:
            graph = TaskGraph()
            await graph.load_for_user(user_id)
            self._graphs[user_id] = graph
        return self._graphs[user_id]

    async def refresh_graph(self, user_id: uuid.UUID) -> TaskGraph:
        """Reload the task graph from database.

        Args:
            user_id: The user's ID.

        Returns:
            Fresh TaskGraph for the user.
        """
        graph = TaskGraph()
        await graph.load_for_user(user_id)
        self._graphs[user_id] = graph
        return graph

    async def create_task(
        self,
        user_id: uuid.UUID,
        title: str,
        description: Optional[str] = None,
        priority: int = 3,
        due_date: Optional[datetime] = None,
        tags: Optional[List[str]] = None,
        parent_id: Optional[uuid.UUID] = None,
        dependencies: Optional[List[uuid.UUID]] = None,
    ) -> Task:
        """Create a new task.

        Args:
            user_id: The user's ID.
            title: Task title.
            description: Task description.
            priority: Priority 1-5.
            due_date: Due date.
            tags: List of tags.
            parent_id: Parent task ID for subtasks.
            dependencies: Task IDs that must complete first.

        Returns:
            The created Task.
        """
        async with get_async_session() as session:
            task = Task(
                user_id=user_id,
                title=title,
                description=description,
                priority=priority,
                due_date=due_date,
                tags=tags or [],
                parent_id=parent_id,
                status=TaskStatus.PENDING,
            )
            session.add(task)
            await session.flush()

            # Add dependencies
            if dependencies:
                for dep_id in dependencies:
                    dep_task = await session.get(Task, dep_id)
                    if dep_task and dep_task.user_id == user_id:
                        task.dependencies.append(dep_task)

                # Check if blocked
                incomplete_deps = [
                    d for d in task.dependencies
                    if d.status != TaskStatus.COMPLETED
                ]
                if incomplete_deps:
                    task.status = TaskStatus.BLOCKED

            await session.commit()

            # Update graph
            graph = await self.get_graph(user_id)
            node = TaskNode(
                id=task.id,
                title=task.title,
                status=task.status,
                priority=task.priority,
                due_date=task.due_date,
                parent_id=task.parent_id,
                dependencies=[d.id for d in task.dependencies],
                tags=task.tags or [],
            )
            graph.add_node(node)

            return task

    async def update_task(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        updates: Dict[str, Any],
    ) -> Optional[Task]:
        """Update a task.

        Args:
            user_id: The user's ID.
            task_id: The task ID.
            updates: Dictionary of fields to update.

        Returns:
            Updated Task or None if not found.
        """
        async with get_async_session() as session:
            task = await session.get(Task, task_id)
            if not task or task.user_id != user_id or task.deleted_at:
                return None

            # Apply updates
            for field, value in updates.items():
                if hasattr(task, field):
                    setattr(task, field, value)

            task.updated_at = datetime.utcnow()
            await session.commit()

            # Refresh graph
            await self.refresh_graph(user_id)

            return task

    async def complete_task(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> Optional[Task]:
        """Mark a task as completed and unblock dependents.

        Args:
            user_id: The user's ID.
            task_id: The task ID.

        Returns:
            Updated Task or None if not found.
        """
        async with get_async_session() as session:
            task = await session.get(Task, task_id)
            if not task or task.user_id != user_id or task.deleted_at:
                return None

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.updated_at = datetime.utcnow()

            # Get dependents from graph
            graph = await self.get_graph(user_id)
            dependents = graph.get_dependents(task_id)

            # Check if any dependents should be unblocked
            for dependent in dependents:
                if dependent.status == TaskStatus.BLOCKED:
                    # Check if all dependencies are now complete
                    is_still_blocked, blockers = graph.is_blocked(dependent.id)
                    # Exclude this task from blockers check since we're completing it
                    remaining_blockers = [b for b in blockers if b.id != task_id]
                    if not remaining_blockers:
                        # Unblock the dependent
                        dep_task = await session.get(Task, dependent.id)
                        if dep_task:
                            dep_task.status = TaskStatus.PENDING
                            dep_task.updated_at = datetime.utcnow()

            await session.commit()

            # Refresh graph
            await self.refresh_graph(user_id)

            return task

    async def delete_task(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        hard_delete: bool = False,
    ) -> bool:
        """Delete a task (soft delete by default).

        Args:
            user_id: The user's ID.
            task_id: The task ID.
            hard_delete: If True, permanently delete.

        Returns:
            True if deleted.
        """
        async with get_async_session() as session:
            task = await session.get(Task, task_id)
            if not task or task.user_id != user_id:
                return False

            if hard_delete:
                await session.delete(task)
            else:
                task.deleted_at = datetime.utcnow()

            await session.commit()

            # Update graph
            graph = await self.get_graph(user_id)
            graph.remove_node(task_id)

            return True

    async def add_dependency(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        depends_on_id: uuid.UUID,
    ) -> bool:
        """Add a dependency between tasks.

        Args:
            user_id: The user's ID.
            task_id: The task that has the dependency.
            depends_on_id: The task that must complete first.

        Returns:
            True if dependency was added.

        Raises:
            GraphValidationError: If this would create a cycle.
        """
        async with get_async_session() as session:
            task = await session.get(Task, task_id)
            dep_task = await session.get(Task, depends_on_id)

            if not task or not dep_task:
                return False
            if task.user_id != user_id or dep_task.user_id != user_id:
                return False

            # Validate with graph
            graph = await self.get_graph(user_id)
            graph.add_dependency(task_id, depends_on_id)  # Raises if cycle

            # Add to database
            task.dependencies.append(dep_task)

            # Update status if blocked
            if dep_task.status != TaskStatus.COMPLETED:
                task.status = TaskStatus.BLOCKED
                task.updated_at = datetime.utcnow()

            await session.commit()
            return True

    async def remove_dependency(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        depends_on_id: uuid.UUID,
    ) -> bool:
        """Remove a dependency between tasks.

        Args:
            user_id: The user's ID.
            task_id: The task that has the dependency.
            depends_on_id: The dependency to remove.

        Returns:
            True if dependency was removed.
        """
        async with get_async_session() as session:
            task = await session.get(Task, task_id)
            if not task or task.user_id != user_id:
                return False

            # Find and remove dependency
            for dep in task.dependencies:
                if dep.id == depends_on_id:
                    task.dependencies.remove(dep)
                    break
            else:
                return False

            # Check if still blocked
            incomplete_deps = [
                d for d in task.dependencies
                if d.status != TaskStatus.COMPLETED
            ]
            if not incomplete_deps and task.status == TaskStatus.BLOCKED:
                task.status = TaskStatus.PENDING

            task.updated_at = datetime.utcnow()
            await session.commit()

            # Update graph
            graph = await self.get_graph(user_id)
            graph.remove_dependency(task_id, depends_on_id)

            return True

    async def create_subtask(
        self,
        user_id: uuid.UUID,
        parent_id: uuid.UUID,
        title: str,
        **kwargs,
    ) -> Optional[Task]:
        """Create a subtask under a parent task.

        Args:
            user_id: The user's ID.
            parent_id: The parent task ID.
            title: Subtask title.
            **kwargs: Additional task fields.

        Returns:
            Created Task or None if parent not found.
        """
        async with get_async_session() as session:
            parent = await session.get(Task, parent_id)
            if not parent or parent.user_id != user_id or parent.deleted_at:
                return None

        return await self.create_task(
            user_id=user_id,
            title=title,
            parent_id=parent_id,
            **kwargs,
        )

    async def get_next_task(self, user_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Get the recommended next task to work on.

        Args:
            user_id: The user's ID.

        Returns:
            Task dict or None if no tasks available.
        """
        graph = await self.get_graph(user_id)
        next_task = graph.get_next_task()

        if not next_task:
            return None

        return {
            "id": str(next_task.id),
            "title": next_task.title,
            "priority": next_task.priority,
            "due_date": next_task.due_date.isoformat() if next_task.due_date else None,
            "tags": next_task.tags,
            "reason": self._explain_recommendation(next_task, graph),
        }

    def _explain_recommendation(self, task: TaskNode, graph: TaskGraph) -> str:
        """Explain why a task is recommended.

        Args:
            task: The recommended task.
            graph: The task graph.

        Returns:
            Explanation string.
        """
        reasons = []

        if task.priority >= 4:
            reasons.append("High priority")

        if task.due_date:
            days_until = (task.due_date - datetime.utcnow()).days
            if days_until <= 0:
                reasons.append("Due today or overdue")
            elif days_until <= 1:
                reasons.append("Due tomorrow")
            elif days_until <= 3:
                reasons.append("Due soon")

        dependents = graph.get_dependents(task.id)
        if dependents:
            reasons.append(f"Unblocks {len(dependents)} task(s)")

        if not reasons:
            reasons.append("Ready to work on")

        return "; ".join(reasons)

    async def get_available_tasks(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get all available (unblocked) tasks.

        Args:
            user_id: The user's ID.
            limit: Maximum tasks to return.

        Returns:
            List of task dicts.
        """
        graph = await self.get_graph(user_id)
        return graph.format_as_list(show_blocked=False, max_items=limit)

    async def get_blocked_tasks(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get all blocked tasks with blocking info.

        Args:
            user_id: The user's ID.
            limit: Maximum tasks to return.

        Returns:
            List of task dicts with blocked_by info.
        """
        graph = await self.get_graph(user_id)
        blocked = []

        for task_id, node in graph.nodes.items():
            if node.is_completed:
                continue
            is_blocked, blockers = graph.is_blocked(task_id)
            if is_blocked:
                blocked.append({
                    "id": str(node.id),
                    "title": node.title,
                    "priority": node.priority,
                    "blocked_by": [
                        {"id": str(b.id), "title": b.title}
                        for b in blockers[:5]
                    ],
                })
                if len(blocked) >= limit:
                    break

        return blocked

    async def get_task_details(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """Get full task details with relationships.

        Args:
            user_id: The user's ID.
            task_id: The task ID.

        Returns:
            Task dict with full details or None.
        """
        async with get_async_session() as session:
            task = await session.get(Task, task_id)
            if not task or task.user_id != user_id or task.deleted_at:
                return None

            graph = await self.get_graph(user_id)

            dependencies = graph.get_dependencies(task_id)
            dependents = graph.get_dependents(task_id)
            subtasks = graph.get_subtasks(task_id)
            parent = graph.get_parent(task_id)

            is_blocked, blockers = graph.is_blocked(task_id)

            return {
                "id": str(task.id),
                "title": task.title,
                "description": task.description,
                "status": task.status.value,
                "priority": task.priority,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "tags": task.tags,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "is_blocked": is_blocked,
                "blocked_by": [{"id": str(b.id), "title": b.title} for b in blockers],
                "dependencies": [{"id": str(d.id), "title": d.title, "status": d.status.value} for d in dependencies],
                "dependents": [{"id": str(d.id), "title": d.title} for d in dependents],
                "subtasks": [{"id": str(s.id), "title": s.title, "status": s.status.value} for s in subtasks],
                "parent": {"id": str(parent.id), "title": parent.title} if parent else None,
                "relationships_description": graph.describe_relationships(task_id),
            }


# Global instance
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get the global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


def set_task_manager(manager: TaskManager) -> None:
    """Set the global task manager (for testing)."""
    global _task_manager
    _task_manager = manager
