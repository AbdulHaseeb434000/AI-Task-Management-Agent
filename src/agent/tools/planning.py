"""Planning and task management tools for agents."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents import function_tool
from database.models import Task, Plan, PlanStep, TaskStatus, AgentType, TaskBreakdown
from database.operations import TaskOperations, PlanOperations
from database.connection import init_db, DEFAULT_DB_PATH

# Initialize database on import
init_db()

# Create operation instances
task_ops = TaskOperations()
plan_ops = PlanOperations()


@function_tool
def create_plan(
    task_id: str,
    strategy: str,
    steps: list[dict],
) -> dict:
    """Create an execution plan for a task.

    Args:
        task_id: The ID of the task to plan
        strategy: High-level description of the approach
        steps: List of step dictionaries with: order, description, agent_type, dependencies, estimated_minutes

    Returns:
        The created plan as a dictionary
    """
    plan_steps = []
    for step in steps:
        plan_steps.append(PlanStep(
            order=step["order"],
            description=step["description"],
            agent_type=AgentType(step["agent_type"]),
            dependencies=step.get("dependencies", []),
            estimated_minutes=step.get("estimated_minutes", 15),
        ))

    plan = Plan(
        task_id=task_id,
        strategy=strategy,
        steps=plan_steps,
    )
    plan.calculate_duration()

    # Save to database
    plan_ops.create_plan(plan)

    # Update task with plan reference
    task = task_ops.get_task(task_id)
    if task:
        task.plan_id = plan.id
        task.status = TaskStatus.PLANNING
        task_ops.update_task(task)

    return plan.model_dump()


@function_tool
def create_subtask(
    parent_id: str,
    title: str,
    description: str,
    agent_type: str,
    priority: int = 3,
    dependencies: list[str] = None,
) -> dict:
    """Create a subtask under a parent task.

    Args:
        parent_id: The ID of the parent task
        title: Short title for the subtask
        description: Detailed description of what needs to be done
        agent_type: Which specialist agent handles this (code, research, writing, communication)
        priority: Priority 1-5 (5 = highest)
        dependencies: List of task IDs that must complete first

    Returns:
        The created subtask as a dictionary
    """
    subtask = Task(
        title=title,
        description=description,
        parent_id=parent_id,
        assigned_agent=AgentType(agent_type),
        priority=priority,
        dependencies=dependencies or [],
        status=TaskStatus.WAITING if dependencies else TaskStatus.PENDING,
    )

    # Save subtask
    task_ops.create_task(subtask)

    # Update parent with subtask reference
    parent = task_ops.get_task(parent_id)
    if parent:
        parent.subtask_ids.append(subtask.id)
        task_ops.update_task(parent)

    return subtask.model_dump()


@function_tool
def get_task(task_id: str) -> dict | None:
    """Get a task by its ID.

    Args:
        task_id: The ID of the task to retrieve

    Returns:
        The task as a dictionary, or None if not found
    """
    task = task_ops.get_task(task_id)
    return task.model_dump() if task else None


@function_tool
def update_task_status(
    task_id: str,
    status: str,
    result: str = None,
    error: str = None,
) -> dict:
    """Update the status of a task.

    Args:
        task_id: The ID of the task to update
        status: New status (pending, in_progress, completed, failed)
        result: Result message if completed
        error: Error message if failed

    Returns:
        The updated task as a dictionary
    """
    task = task_ops.get_task(task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}

    new_status = TaskStatus(status)

    if new_status == TaskStatus.IN_PROGRESS:
        task.mark_started()
    elif new_status == TaskStatus.COMPLETED:
        task.mark_completed(result or "Completed")
    elif new_status == TaskStatus.FAILED:
        task.mark_failed(error or "Unknown error")
    else:
        task.status = new_status

    task_ops.update_task(task)

    # Check if all subtasks complete, update parent
    if task.parent_id and new_status == TaskStatus.COMPLETED:
        _check_parent_completion(task.parent_id)

    return task.model_dump()


@function_tool
def get_pending_subtasks(parent_id: str = None) -> list[dict]:
    """Get all pending subtasks ready for execution.

    Args:
        parent_id: Optional parent task ID to filter by

    Returns:
        List of pending tasks as dictionaries
    """
    if parent_id:
        subtasks = task_ops.get_subtasks(parent_id)
        pending = [t for t in subtasks if t.status in [TaskStatus.PENDING, TaskStatus.WAITING]]
    else:
        pending = task_ops.get_pending_tasks()

    # Filter out tasks with incomplete dependencies
    ready = []
    for task in pending:
        if _dependencies_complete(task):
            ready.append(task.model_dump())

    return ready


@function_tool
def get_next_subtask(parent_id: str) -> dict | None:
    """Get the next subtask to execute based on priority and dependencies.

    Args:
        parent_id: The parent task ID

    Returns:
        The next subtask to execute, or None if all complete
    """
    pending = get_pending_subtasks(parent_id)
    if pending:
        # Sort by priority (highest first)
        pending.sort(key=lambda x: x["priority"], reverse=True)
        return pending[0]
    return None


def _dependencies_complete(task: Task) -> bool:
    """Check if all dependencies are complete."""
    for dep_id in task.dependencies:
        dep = task_ops.get_task(dep_id)
        if dep and dep.status != TaskStatus.COMPLETED:
            return False
    return True


def _check_parent_completion(parent_id: str) -> None:
    """Check if all subtasks are complete and update parent."""
    subtasks = task_ops.get_subtasks(parent_id)
    all_complete = all(t.status == TaskStatus.COMPLETED for t in subtasks)

    if all_complete:
        parent = task_ops.get_task(parent_id)
        if parent:
            results = [t.result for t in subtasks if t.result]
            parent.mark_completed(f"All {len(subtasks)} subtasks completed. Results: {'; '.join(results)}")
            task_ops.update_task(parent)
