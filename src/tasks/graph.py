"""Task Graph - DAG-based task dependency management.

Manages tasks as a directed acyclic graph (DAG) for:
- Dependency tracking
- Subtask hierarchies
- Blocked task detection
- Topological ordering
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import Task, TaskStatus
from src.database.connection import get_async_session


class GraphValidationError(Exception):
    """Raised when graph validation fails."""
    pass


@dataclass
class TaskNode:
    """A node in the task graph."""
    id: uuid.UUID
    title: str
    status: TaskStatus
    priority: int
    due_date: Optional[datetime]
    parent_id: Optional[uuid.UUID]
    dependencies: List[uuid.UUID] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def is_blocked(self) -> bool:
        return self.status == TaskStatus.BLOCKED


class TaskGraph:
    """Manages tasks as a directed acyclic graph.

    Internally manages:
    - Parent-child relationships (subtasks)
    - Dependency relationships (must complete before)
    - Blocked task detection
    - Topological ordering for execution

    Externally presents:
    - Simple prioritized lists
    - "What's next" recommendations
    - Progressive disclosure of complexity
    """

    def __init__(self):
        """Initialize empty task graph."""
        self.nodes: Dict[uuid.UUID, TaskNode] = {}
        self._adjacency: Dict[uuid.UUID, Set[uuid.UUID]] = defaultdict(set)  # Dependencies
        self._reverse_adjacency: Dict[uuid.UUID, Set[uuid.UUID]] = defaultdict(set)  # Dependents
        self._children: Dict[uuid.UUID, Set[uuid.UUID]] = defaultdict(set)  # Parent -> Children

    async def load_for_user(self, user_id: uuid.UUID) -> None:
        """Load all tasks for a user into the graph.

        Args:
            user_id: The user's ID.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(Task).where(
                    Task.user_id == user_id,
                    Task.deleted_at.is_(None),
                )
            )
            tasks = result.scalars().all()

        self.clear()

        for task in tasks:
            node = TaskNode(
                id=task.id,
                title=task.title,
                status=task.status,
                priority=task.priority,
                due_date=task.due_date,
                parent_id=task.parent_id,
                dependencies=[],  # Will be loaded from junction table
                tags=task.tags or [],
                created_at=task.created_at,
                metadata=task.task_metadata or {},
            )
            self.add_node(node)

            # Track parent-child relationships
            if task.parent_id:
                self._children[task.parent_id].add(task.id)

        # Load dependencies from the database
        await self._load_dependencies(user_id)

    async def _load_dependencies(self, user_id: uuid.UUID) -> None:
        """Load task dependencies from database.

        Args:
            user_id: The user's ID.
        """
        # Dependencies are stored in task.dependencies many-to-many
        async with get_async_session() as session:
            result = await session.execute(
                select(Task).where(
                    Task.user_id == user_id,
                    Task.deleted_at.is_(None),
                )
            )
            tasks = result.scalars().all()

            for task in tasks:
                if task.dependencies:
                    for dep in task.dependencies:
                        if dep.id in self.nodes:
                            self.add_dependency(task.id, dep.id)

    def clear(self) -> None:
        """Clear the graph."""
        self.nodes.clear()
        self._adjacency.clear()
        self._reverse_adjacency.clear()
        self._children.clear()

    def add_node(self, node: TaskNode) -> None:
        """Add a task node to the graph.

        Args:
            node: The task node to add.
        """
        self.nodes[node.id] = node

        # Add dependencies
        for dep_id in node.dependencies:
            self.add_dependency(node.id, dep_id)

    def remove_node(self, task_id: uuid.UUID) -> None:
        """Remove a task node from the graph.

        Args:
            task_id: The task ID to remove.
        """
        if task_id not in self.nodes:
            return

        # Remove from adjacency lists
        for dep_id in list(self._adjacency[task_id]):
            self._reverse_adjacency[dep_id].discard(task_id)
        del self._adjacency[task_id]

        for dependent_id in list(self._reverse_adjacency[task_id]):
            self._adjacency[dependent_id].discard(task_id)
        del self._reverse_adjacency[task_id]

        # Remove from parent's children
        node = self.nodes[task_id]
        if node.parent_id:
            self._children[node.parent_id].discard(task_id)

        # Remove own children tracking
        del self._children[task_id]

        del self.nodes[task_id]

    def add_dependency(self, task_id: uuid.UUID, depends_on_id: uuid.UUID) -> None:
        """Add a dependency: task_id depends on depends_on_id.

        Args:
            task_id: The task that has the dependency.
            depends_on_id: The task that must complete first.

        Raises:
            GraphValidationError: If this would create a cycle.
        """
        if task_id == depends_on_id:
            raise GraphValidationError("Task cannot depend on itself")

        # Check for cycles
        if self._would_create_cycle(task_id, depends_on_id):
            raise GraphValidationError(
                f"Adding dependency would create a cycle: {task_id} -> {depends_on_id}"
            )

        self._adjacency[task_id].add(depends_on_id)
        self._reverse_adjacency[depends_on_id].add(task_id)

        if task_id in self.nodes:
            self.nodes[task_id].dependencies.append(depends_on_id)

    def remove_dependency(self, task_id: uuid.UUID, depends_on_id: uuid.UUID) -> None:
        """Remove a dependency.

        Args:
            task_id: The task that has the dependency.
            depends_on_id: The dependency to remove.
        """
        self._adjacency[task_id].discard(depends_on_id)
        self._reverse_adjacency[depends_on_id].discard(task_id)

        if task_id in self.nodes:
            deps = self.nodes[task_id].dependencies
            if depends_on_id in deps:
                deps.remove(depends_on_id)

    def _would_create_cycle(self, task_id: uuid.UUID, depends_on_id: uuid.UUID) -> bool:
        """Check if adding a dependency would create a cycle.

        Args:
            task_id: The task that would have the dependency.
            depends_on_id: The proposed dependency.

        Returns:
            True if this would create a cycle.
        """
        # If depends_on_id can reach task_id, adding task_id -> depends_on_id creates cycle
        visited = set()
        stack = [depends_on_id]

        while stack:
            current = stack.pop()
            if current == task_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            stack.extend(self._adjacency.get(current, set()))

        return False

    def get_dependencies(self, task_id: uuid.UUID) -> List[TaskNode]:
        """Get all direct dependencies of a task.

        Args:
            task_id: The task ID.

        Returns:
            List of task nodes this task depends on.
        """
        dep_ids = self._adjacency.get(task_id, set())
        return [self.nodes[dep_id] for dep_id in dep_ids if dep_id in self.nodes]

    def get_dependents(self, task_id: uuid.UUID) -> List[TaskNode]:
        """Get all tasks that depend on this task.

        Args:
            task_id: The task ID.

        Returns:
            List of task nodes that depend on this task.
        """
        dependent_ids = self._reverse_adjacency.get(task_id, set())
        return [self.nodes[dep_id] for dep_id in dependent_ids if dep_id in self.nodes]

    def get_subtasks(self, task_id: uuid.UUID) -> List[TaskNode]:
        """Get all direct subtasks of a task.

        Args:
            task_id: The parent task ID.

        Returns:
            List of child task nodes.
        """
        child_ids = self._children.get(task_id, set())
        return [self.nodes[child_id] for child_id in child_ids if child_id in self.nodes]

    def get_parent(self, task_id: uuid.UUID) -> Optional[TaskNode]:
        """Get the parent task if any.

        Args:
            task_id: The task ID.

        Returns:
            Parent TaskNode or None.
        """
        if task_id not in self.nodes:
            return None
        parent_id = self.nodes[task_id].parent_id
        if parent_id and parent_id in self.nodes:
            return self.nodes[parent_id]
        return None

    def is_blocked(self, task_id: uuid.UUID) -> Tuple[bool, List[TaskNode]]:
        """Check if a task is blocked by incomplete dependencies.

        Args:
            task_id: The task ID to check.

        Returns:
            Tuple of (is_blocked, list of blocking tasks).
        """
        blocking = []
        for dep_id in self._adjacency.get(task_id, set()):
            if dep_id in self.nodes:
                dep_node = self.nodes[dep_id]
                if not dep_node.is_completed:
                    blocking.append(dep_node)

        return len(blocking) > 0, blocking

    def get_available_tasks(self) -> List[TaskNode]:
        """Get all tasks that are ready to work on (not blocked).

        Returns:
            List of TaskNode that have no incomplete dependencies.
        """
        available = []
        for task_id, node in self.nodes.items():
            if node.is_completed:
                continue
            is_blocked, _ = self.is_blocked(task_id)
            if not is_blocked:
                available.append(node)

        # Sort by priority (high first) and due date (soon first)
        return sorted(
            available,
            key=lambda t: (
                -t.priority,
                t.due_date or datetime.max,
            ),
        )

    def get_next_task(self) -> Optional[TaskNode]:
        """Get the single most recommended next task.

        Returns:
            The highest priority available task, or None.
        """
        available = self.get_available_tasks()
        return available[0] if available else None

    def topological_sort(self) -> List[TaskNode]:
        """Get tasks in topological order (dependencies first).

        Returns:
            List of TaskNode in execution order.

        Raises:
            GraphValidationError: If graph has a cycle.
        """
        in_degree = {task_id: 0 for task_id in self.nodes}

        for task_id in self.nodes:
            for dep_id in self._adjacency.get(task_id, set()):
                if dep_id in in_degree:
                    in_degree[task_id] += 1

        # Start with nodes that have no dependencies
        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort by priority to get consistent ordering
            queue.sort(key=lambda t: (-self.nodes[t].priority, self.nodes[t].title))
            task_id = queue.pop(0)
            result.append(self.nodes[task_id])

            for dependent_id in self._reverse_adjacency.get(task_id, set()):
                if dependent_id in in_degree:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)

        if len(result) != len(self.nodes):
            raise GraphValidationError("Graph contains a cycle")

        return result

    def get_task_chain(self, task_id: uuid.UUID) -> List[TaskNode]:
        """Get the dependency chain for a task (what must be done first).

        Args:
            task_id: The target task ID.

        Returns:
            List of tasks in order of execution to reach this task.
        """
        if task_id not in self.nodes:
            return []

        # BFS to find all ancestors
        ancestors = set()
        queue = list(self._adjacency.get(task_id, set()))

        while queue:
            current = queue.pop(0)
            if current in ancestors or current not in self.nodes:
                continue
            ancestors.add(current)
            queue.extend(self._adjacency.get(current, set()))

        # Get nodes and sort topologically
        ancestor_nodes = [self.nodes[a] for a in ancestors]

        # Simple sort by dependency count
        ancestor_nodes.sort(key=lambda n: len(self._adjacency.get(n.id, set())))

        return ancestor_nodes

    def format_as_list(
        self,
        show_blocked: bool = True,
        show_completed: bool = False,
        max_items: int = 10,
    ) -> List[Dict[str, Any]]:
        """Format tasks as a simple prioritized list.

        Args:
            show_blocked: Include blocked tasks.
            show_completed: Include completed tasks.
            max_items: Maximum items to return.

        Returns:
            List of task dicts for display.
        """
        result = []

        for node in self.get_available_tasks():
            if not show_completed and node.is_completed:
                continue
            result.append(self._format_node(node, is_blocked=False))
            if len(result) >= max_items:
                return result

        if show_blocked:
            for task_id, node in self.nodes.items():
                if node.is_completed:
                    continue
                is_blocked, blockers = self.is_blocked(task_id)
                if is_blocked:
                    formatted = self._format_node(node, is_blocked=True)
                    formatted["blocked_by"] = [b.title for b in blockers[:3]]
                    result.append(formatted)
                    if len(result) >= max_items:
                        return result

        return result

    def _format_node(self, node: TaskNode, is_blocked: bool = False) -> Dict[str, Any]:
        """Format a task node for display.

        Args:
            node: The task node.
            is_blocked: Whether the task is blocked.

        Returns:
            Dictionary for display.
        """
        return {
            "id": str(node.id),
            "title": node.title,
            "status": node.status.value,
            "priority": node.priority,
            "due_date": node.due_date.isoformat() if node.due_date else None,
            "tags": node.tags,
            "is_blocked": is_blocked,
            "has_subtasks": len(self._children.get(node.id, set())) > 0,
            "dependency_count": len(self._adjacency.get(node.id, set())),
        }

    def describe_relationships(self, task_id: uuid.UUID) -> str:
        """Describe task relationships in natural language.

        Args:
            task_id: The task ID.

        Returns:
            Natural language description of relationships.
        """
        if task_id not in self.nodes:
            return "Task not found."

        node = self.nodes[task_id]
        parts = [f"**{node.title}**"]

        # Describe dependencies
        deps = self.get_dependencies(task_id)
        if deps:
            incomplete_deps = [d for d in deps if not d.is_completed]
            if incomplete_deps:
                parts.append(f"Waiting on: {', '.join(d.title for d in incomplete_deps[:3])}")
            else:
                parts.append("All dependencies complete!")

        # Describe dependents
        dependents = self.get_dependents(task_id)
        if dependents:
            parts.append(f"Blocks: {', '.join(d.title for d in dependents[:3])}")

        # Describe subtasks
        subtasks = self.get_subtasks(task_id)
        if subtasks:
            completed = sum(1 for s in subtasks if s.is_completed)
            parts.append(f"Subtasks: {completed}/{len(subtasks)} complete")

        # Describe parent
        parent = self.get_parent(task_id)
        if parent:
            parts.append(f"Part of: {parent.title}")

        return "\n".join(parts)

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics.

        Returns:
            Dictionary of statistics.
        """
        total = len(self.nodes)
        completed = sum(1 for n in self.nodes.values() if n.is_completed)
        blocked = sum(1 for task_id in self.nodes if self.is_blocked(task_id)[0])
        available = len(self.get_available_tasks())

        total_deps = sum(len(deps) for deps in self._adjacency.values())
        total_children = sum(len(children) for children in self._children.values())

        return {
            "total_tasks": total,
            "completed": completed,
            "blocked": blocked,
            "available": available,
            "total_dependencies": total_deps,
            "total_subtasks": total_children,
            "root_tasks": sum(1 for n in self.nodes.values() if n.parent_id is None),
        }
