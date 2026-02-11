"""Database interaction tools for agents."""

import json
import sys
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents import function_tool
from database.models import Task, Plan, ExecutionLog, TaskStatus, AgentType
from database.operations import TaskOperations, PlanOperations, LogOperations
from database.connection import init_db

# Initialize database
init_db()

# Create operation instances
task_ops = TaskOperations()
plan_ops = PlanOperations()
log_ops = LogOperations()


@function_tool
def save_task(
    title: str,
    description: str,
    priority: int = 3,
    tags_json: Optional[str] = None,
    metadata_json: Optional[str] = None,
) -> str:
    """Save a new task to the database.

    Args:
        title: Short task title
        description: Full task description
        priority: Priority 1-5 (5 = highest)
        tags_json: Optional JSON array of tags, e.g. '["urgent", "coding"]'
        metadata_json: Optional JSON object for additional context

    Returns:
        JSON string of the created task with its ID
    """
    tags = []
    metadata = {}

    if tags_json:
        try:
            tags = json.loads(tags_json)
        except json.JSONDecodeError:
            pass

    if metadata_json:
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            pass

    task = Task(
        title=title,
        description=description,
        priority=priority,
        tags=tags,
        metadata=metadata,
    )
    task_ops.create_task(task)
    return json.dumps(task.model_dump(), default=str)


@function_tool
def save_plan(
    task_id: str,
    strategy: str,
    steps_json: str,
) -> str:
    """Save an execution plan to the database.

    Args:
        task_id: The task this plan is for
        strategy: High-level approach description
        steps_json: JSON array of plan steps

    Returns:
        JSON string of the created plan
    """
    from .planning import create_plan
    return create_plan(task_id, strategy, steps_json)


@function_tool
def get_task_by_id(task_id: str) -> str:
    """Retrieve a task from the database.

    Args:
        task_id: The ID of the task

    Returns:
        JSON string of the task, or error if not found
    """
    task = task_ops.get_task(task_id)
    if task:
        return json.dumps(task.model_dump(), default=str)
    return json.dumps({"error": f"Task {task_id} not found"})


@function_tool
def get_subtasks_for_task(parent_id: str) -> str:
    """Get all subtasks for a parent task.

    Args:
        parent_id: The parent task ID

    Returns:
        JSON string of list of subtasks
    """
    subtasks = task_ops.get_subtasks(parent_id)
    return json.dumps([t.model_dump() for t in subtasks], default=str)


@function_tool
def log_execution(
    task_id: str,
    agent_type: str,
    action: str,
    input_data: Optional[str] = None,
    output_data: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> str:
    """Log an execution action for auditing.

    Args:
        task_id: The task being executed
        agent_type: Which agent performed the action
        action: Description of the action taken
        input_data: Input provided to the action
        output_data: Output from the action
        status: success, error, or pending
        error_message: Error details if failed
        duration_ms: How long the action took

    Returns:
        JSON string of the created log entry
    """
    log = ExecutionLog(
        task_id=task_id,
        agent_type=AgentType(agent_type),
        action=action,
        input_data=input_data,
        output_data=output_data,
        status=status,
        error_message=error_message,
        duration_ms=duration_ms,
    )
    log_ops.create_log(log)
    return json.dumps(log.model_dump(), default=str)


@function_tool
def get_execution_logs(task_id: str) -> str:
    """Get all execution logs for a task.

    Args:
        task_id: The task ID

    Returns:
        JSON string of list of execution logs
    """
    logs = log_ops.get_logs_for_task(task_id)
    return json.dumps([log.model_dump() for log in logs], default=str)


@function_tool
def get_tasks_by_status(status: str) -> str:
    """Get all tasks with a specific status.

    Args:
        status: The status to filter by (pending, in_progress, completed, failed)

    Returns:
        JSON string of list of matching tasks
    """
    tasks = task_ops.get_tasks_by_status(TaskStatus(status))
    return json.dumps([t.model_dump() for t in tasks], default=str)


@function_tool
def get_tasks_for_agent(agent_type: str) -> str:
    """Get all tasks assigned to a specific agent type.

    Args:
        agent_type: The agent type (code, research, writing, communication)

    Returns:
        JSON string of list of assigned tasks
    """
    tasks = task_ops.get_tasks_by_agent(AgentType(agent_type))
    return json.dumps([t.model_dump() for t in tasks], default=str)
