"""Planning and task management tools for agents."""

import json
import sys
from pathlib import Path
from typing import Optional, List

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
    steps_json: str,
) -> str:
    """Create an execution plan for a task.

    Args:
        task_id: The ID of the task to plan
        strategy: High-level description of the approach
        steps_json: JSON string of steps array. Each step: {"order": 1, "description": "...", "agent_type": "code", "dependencies": [], "estimated_minutes": 15}

    Returns:
        JSON string of the created plan
    """
    try:
        steps = json.loads(steps_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON for steps"})

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

    return json.dumps(plan.model_dump(), default=str)


@function_tool
def create_subtask(
    parent_id: str,
    title: str,
    description: str,
    agent_type: str,
    priority: int = 3,
    dependencies_json: Optional[str] = None,
) -> str:
    """Create a subtask under a parent task.

    Args:
        parent_id: The ID of the parent task
        title: Short title for the subtask
        description: Detailed description of what needs to be done
        agent_type: Which specialist agent handles this (code, research, writing, communication)
        priority: Priority 1-5 (5 = highest)
        dependencies_json: Optional JSON string of task IDs that must complete first, e.g. '["task-1", "task-2"]'

    Returns:
        JSON string of the created subtask
    """
    dependencies = []
    if dependencies_json:
        try:
            dependencies = json.loads(dependencies_json)
        except json.JSONDecodeError:
            pass

    subtask = Task(
        title=title,
        description=description,
        parent_id=parent_id,
        assigned_agent=AgentType(agent_type),
        priority=priority,
        dependencies=dependencies,
        status=TaskStatus.WAITING if dependencies else TaskStatus.PENDING,
    )

    # Save subtask
    task_ops.create_task(subtask)

    # Update parent with subtask reference
    parent = task_ops.get_task(parent_id)
    if parent:
        parent.subtask_ids.append(subtask.id)
        task_ops.update_task(parent)

    return json.dumps(subtask.model_dump(), default=str)


@function_tool
def get_task(task_id: str) -> str:
    """Get a task by its ID.

    Args:
        task_id: The ID of the task to retrieve

    Returns:
        JSON string of the task, or error message if not found
    """
    task = task_ops.get_task(task_id)
    if task:
        return json.dumps(task.model_dump(), default=str)
    return json.dumps({"error": f"Task {task_id} not found"})


@function_tool
def update_task_status(
    task_id: str,
    status: str,
    result: Optional[str] = None,
    error: Optional[str] = None,
) -> str:
    """Update the status of a task.

    Args:
        task_id: The ID of the task to update
        status: New status (pending, in_progress, completed, failed)
        result: Result message if completed
        error: Error message if failed

    Returns:
        JSON string of the updated task
    """
    task = task_ops.get_task(task_id)
    if not task:
        return json.dumps({"error": f"Task {task_id} not found"})

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

    return json.dumps(task.model_dump(), default=str)


@function_tool
def get_pending_subtasks(parent_id: Optional[str] = None) -> str:
    """Get all pending subtasks ready for execution.

    Args:
        parent_id: Optional parent task ID to filter by

    Returns:
        JSON string of list of pending tasks
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

    return json.dumps(ready, default=str)


@function_tool
def get_next_subtask(parent_id: str) -> str:
    """Get the next subtask to execute based on priority and dependencies.

    Args:
        parent_id: The parent task ID

    Returns:
        JSON string of the next subtask, or null if all complete
    """
    pending_json = get_pending_subtasks(parent_id)
    pending = json.loads(pending_json)
    if pending:
        # Sort by priority (highest first)
        pending.sort(key=lambda x: x["priority"], reverse=True)
        return json.dumps(pending[0], default=str)
    return json.dumps(None)


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
