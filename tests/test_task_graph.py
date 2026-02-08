"""Tests for Task Graph functionality."""

import uuid
from datetime import datetime, timedelta
import pytest

from src.tasks.graph import TaskGraph, TaskNode, GraphValidationError
from src.database.orm import TaskStatus


class TestTaskNode:
    """Tests for TaskNode dataclass."""

    def test_create_node(self):
        """Test creating a task node."""
        node_id = uuid.uuid4()
        node = TaskNode(
            id=node_id,
            title="Test Task",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        )
        assert node.id == node_id
        assert node.title == "Test Task"
        assert node.status == TaskStatus.PENDING
        assert node.priority == 3

    def test_node_is_completed(self):
        """Test is_completed property."""
        pending_node = TaskNode(
            id=uuid.uuid4(),
            title="Pending",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        )
        assert pending_node.is_completed is False

        completed_node = TaskNode(
            id=uuid.uuid4(),
            title="Completed",
            status=TaskStatus.COMPLETED,
            priority=3,
            due_date=None,
            parent_id=None,
        )
        assert completed_node.is_completed is True

    def test_node_is_blocked(self):
        """Test is_blocked property."""
        blocked_node = TaskNode(
            id=uuid.uuid4(),
            title="Blocked",
            status=TaskStatus.BLOCKED,
            priority=3,
            due_date=None,
            parent_id=None,
        )
        assert blocked_node.is_blocked is True


class TestTaskGraphBasic:
    """Tests for basic TaskGraph operations."""

    def test_create_empty_graph(self):
        """Test creating an empty graph."""
        graph = TaskGraph()
        assert len(graph.nodes) == 0

    def test_add_node(self):
        """Test adding a node to the graph."""
        graph = TaskGraph()
        node = TaskNode(
            id=uuid.uuid4(),
            title="Task 1",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        )
        graph.add_node(node)
        assert len(graph.nodes) == 1
        assert node.id in graph.nodes

    def test_remove_node(self):
        """Test removing a node from the graph."""
        graph = TaskGraph()
        node_id = uuid.uuid4()
        node = TaskNode(
            id=node_id,
            title="Task 1",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        )
        graph.add_node(node)
        graph.remove_node(node_id)
        assert len(graph.nodes) == 0

    def test_clear_graph(self):
        """Test clearing the graph."""
        graph = TaskGraph()
        for i in range(5):
            graph.add_node(TaskNode(
                id=uuid.uuid4(),
                title=f"Task {i}",
                status=TaskStatus.PENDING,
                priority=3,
                due_date=None,
                parent_id=None,
            ))
        assert len(graph.nodes) == 5
        graph.clear()
        assert len(graph.nodes) == 0


class TestTaskGraphDependencies:
    """Tests for dependency management."""

    def test_add_dependency(self):
        """Test adding a dependency between tasks."""
        graph = TaskGraph()

        task1_id = uuid.uuid4()
        task2_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=task1_id,
            title="Task 1",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=task2_id,
            title="Task 2",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))

        # Task 2 depends on Task 1
        graph.add_dependency(task2_id, task1_id)

        deps = graph.get_dependencies(task2_id)
        assert len(deps) == 1
        assert deps[0].id == task1_id

    def test_self_dependency_raises_error(self):
        """Test that self-dependency raises an error."""
        graph = TaskGraph()
        task_id = uuid.uuid4()
        graph.add_node(TaskNode(
            id=task_id,
            title="Task",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))

        with pytest.raises(GraphValidationError, match="cannot depend on itself"):
            graph.add_dependency(task_id, task_id)

    def test_cycle_detection(self):
        """Test that circular dependencies are detected."""
        graph = TaskGraph()

        task1_id = uuid.uuid4()
        task2_id = uuid.uuid4()
        task3_id = uuid.uuid4()

        for task_id, title in [(task1_id, "T1"), (task2_id, "T2"), (task3_id, "T3")]:
            graph.add_node(TaskNode(
                id=task_id,
                title=title,
                status=TaskStatus.PENDING,
                priority=3,
                due_date=None,
                parent_id=None,
            ))

        # T1 -> T2 -> T3
        graph.add_dependency(task2_id, task1_id)
        graph.add_dependency(task3_id, task2_id)

        # Adding T1 -> T3 would create a cycle
        with pytest.raises(GraphValidationError, match="cycle"):
            graph.add_dependency(task1_id, task3_id)

    def test_remove_dependency(self):
        """Test removing a dependency."""
        graph = TaskGraph()

        task1_id = uuid.uuid4()
        task2_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=task1_id,
            title="Task 1",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=task2_id,
            title="Task 2",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))

        graph.add_dependency(task2_id, task1_id)
        graph.remove_dependency(task2_id, task1_id)

        deps = graph.get_dependencies(task2_id)
        assert len(deps) == 0

    def test_get_dependents(self):
        """Test getting tasks that depend on a task."""
        graph = TaskGraph()

        task1_id = uuid.uuid4()
        task2_id = uuid.uuid4()
        task3_id = uuid.uuid4()

        for task_id, title in [(task1_id, "T1"), (task2_id, "T2"), (task3_id, "T3")]:
            graph.add_node(TaskNode(
                id=task_id,
                title=title,
                status=TaskStatus.PENDING,
                priority=3,
                due_date=None,
                parent_id=None,
            ))

        # T2 and T3 both depend on T1
        graph.add_dependency(task2_id, task1_id)
        graph.add_dependency(task3_id, task1_id)

        dependents = graph.get_dependents(task1_id)
        assert len(dependents) == 2


class TestTaskGraphBlocking:
    """Tests for blocked task detection."""

    def test_is_blocked_by_incomplete_dependency(self):
        """Test that a task is blocked by incomplete dependencies."""
        graph = TaskGraph()

        task1_id = uuid.uuid4()
        task2_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=task1_id,
            title="Dependency",
            status=TaskStatus.PENDING,  # Not completed
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=task2_id,
            title="Dependent",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))

        graph.add_dependency(task2_id, task1_id)

        is_blocked, blockers = graph.is_blocked(task2_id)
        assert is_blocked is True
        assert len(blockers) == 1
        assert blockers[0].id == task1_id

    def test_not_blocked_when_dependency_completed(self):
        """Test that a task is not blocked when dependencies are complete."""
        graph = TaskGraph()

        task1_id = uuid.uuid4()
        task2_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=task1_id,
            title="Dependency",
            status=TaskStatus.COMPLETED,  # Completed
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=task2_id,
            title="Dependent",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))

        graph.add_dependency(task2_id, task1_id)

        is_blocked, blockers = graph.is_blocked(task2_id)
        assert is_blocked is False
        assert len(blockers) == 0


class TestTaskGraphAvailability:
    """Tests for available task detection."""

    def test_get_available_tasks(self):
        """Test getting tasks that are ready to work on."""
        graph = TaskGraph()

        # Create tasks with different states
        available_id = uuid.uuid4()
        blocked_id = uuid.uuid4()
        completed_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=available_id,
            title="Available",
            status=TaskStatus.PENDING,
            priority=5,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=blocked_id,
            title="Blocked",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=completed_id,
            title="Completed",
            status=TaskStatus.COMPLETED,
            priority=3,
            due_date=None,
            parent_id=None,
        ))

        # Block the blocked task
        graph.add_dependency(blocked_id, available_id)

        available = graph.get_available_tasks()

        # Should only include the available task (not completed, not blocked)
        assert len(available) == 1
        assert available[0].id == available_id

    def test_get_next_task_by_priority(self):
        """Test that next task is selected by priority."""
        graph = TaskGraph()

        low_priority_id = uuid.uuid4()
        high_priority_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=low_priority_id,
            title="Low Priority",
            status=TaskStatus.PENDING,
            priority=1,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=high_priority_id,
            title="High Priority",
            status=TaskStatus.PENDING,
            priority=5,
            due_date=None,
            parent_id=None,
        ))

        next_task = graph.get_next_task()
        assert next_task is not None
        assert next_task.id == high_priority_id


class TestTaskGraphTopologicalSort:
    """Tests for topological sorting."""

    def test_topological_sort_simple(self):
        """Test simple topological sort."""
        graph = TaskGraph()

        task1_id = uuid.uuid4()
        task2_id = uuid.uuid4()
        task3_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=task1_id,
            title="First",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=task2_id,
            title="Second",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=task3_id,
            title="Third",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))

        # First -> Second -> Third
        graph.add_dependency(task2_id, task1_id)
        graph.add_dependency(task3_id, task2_id)

        sorted_tasks = graph.topological_sort()

        # First should come before Second, Second before Third
        ids = [t.id for t in sorted_tasks]
        assert ids.index(task1_id) < ids.index(task2_id)
        assert ids.index(task2_id) < ids.index(task3_id)

    def test_get_task_chain(self):
        """Test getting the dependency chain for a task."""
        graph = TaskGraph()

        task1_id = uuid.uuid4()
        task2_id = uuid.uuid4()
        task3_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=task1_id,
            title="First",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=task2_id,
            title="Second",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=task3_id,
            title="Third",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))

        graph.add_dependency(task2_id, task1_id)
        graph.add_dependency(task3_id, task2_id)

        chain = graph.get_task_chain(task3_id)

        # Chain should include First and Second
        chain_ids = [t.id for t in chain]
        assert task1_id in chain_ids
        assert task2_id in chain_ids
        assert task3_id not in chain_ids  # Target not in chain


class TestTaskGraphSubtasks:
    """Tests for parent-child relationships."""

    def test_get_subtasks(self):
        """Test getting subtasks of a parent task."""
        graph = TaskGraph()

        parent_id = uuid.uuid4()
        child1_id = uuid.uuid4()
        child2_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=parent_id,
            title="Parent",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))

        # Add children with parent_id set
        child1 = TaskNode(
            id=child1_id,
            title="Child 1",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=parent_id,
        )
        child2 = TaskNode(
            id=child2_id,
            title="Child 2",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=parent_id,
        )

        graph.add_node(child1)
        graph._children[parent_id].add(child1_id)
        graph.add_node(child2)
        graph._children[parent_id].add(child2_id)

        subtasks = graph.get_subtasks(parent_id)
        assert len(subtasks) == 2

    def test_get_parent(self):
        """Test getting the parent of a subtask."""
        graph = TaskGraph()

        parent_id = uuid.uuid4()
        child_id = uuid.uuid4()

        graph.add_node(TaskNode(
            id=parent_id,
            title="Parent",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=None,
        ))
        graph.add_node(TaskNode(
            id=child_id,
            title="Child",
            status=TaskStatus.PENDING,
            priority=3,
            due_date=None,
            parent_id=parent_id,
        ))

        parent = graph.get_parent(child_id)
        assert parent is not None
        assert parent.id == parent_id


class TestTaskGraphFormatting:
    """Tests for formatting and display methods."""

    def test_format_as_list(self):
        """Test formatting tasks as a list."""
        graph = TaskGraph()

        task_id = uuid.uuid4()
        graph.add_node(TaskNode(
            id=task_id,
            title="Test Task",
            status=TaskStatus.PENDING,
            priority=5,
            due_date=datetime.utcnow() + timedelta(days=1),
            parent_id=None,
            tags=["work", "urgent"],
        ))

        task_list = graph.format_as_list()
        assert len(task_list) == 1
        assert task_list[0]["title"] == "Test Task"
        assert task_list[0]["priority"] == 5
        assert task_list[0]["is_blocked"] is False

    def test_describe_relationships(self):
        """Test natural language description of relationships."""
        graph = TaskGraph()

        task_id = uuid.uuid4()
        graph.add_node(TaskNode(
            id=task_id,
            title="Important Task",
            status=TaskStatus.PENDING,
            priority=5,
            due_date=None,
            parent_id=None,
        ))

        description = graph.describe_relationships(task_id)
        assert "Important Task" in description

    def test_get_statistics(self):
        """Test getting graph statistics."""
        graph = TaskGraph()

        # Add some tasks
        for i in range(5):
            graph.add_node(TaskNode(
                id=uuid.uuid4(),
                title=f"Task {i}",
                status=TaskStatus.COMPLETED if i < 2 else TaskStatus.PENDING,
                priority=3,
                due_date=None,
                parent_id=None,
            ))

        stats = graph.get_statistics()
        assert stats["total_tasks"] == 5
        assert stats["completed"] == 2
        assert stats["available"] == 3  # Non-completed, non-blocked
