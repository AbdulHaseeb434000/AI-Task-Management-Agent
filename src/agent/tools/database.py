"""Database interaction tools for agents."""

import sys
from pathlib import Path

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
    tags: list[str] = None,
    metadata: dict = None,
) -> dict:
    """Save a new task to the database.

    Args:
        title: Short task title
        description: Full task description
        priority: Priority 1-5 (5 = highest)
        tags: Optional list of tags for categorization
        metadata: Optional additional context

    Returns:
        The created task as a dictionary with its ID
    """
    task = Task(
        title=title,
        description=description,
        priority=priority,
        tags=tags or [],
        metadata=metadata or {},
    )
    task_ops.create_task(task)
    return task.model_dump()


@function_tool
def save_plan(
    task_id: str,
    strategy: str,
    steps: list[dict],
) -> dict:
    """Save an execution plan to the database.

    Args:
        task_id: The task this plan is for
        strategy: High-level approach description
        steps: List of plan steps

    Returns:
        The created plan as a dictionary
    """
    from .planning import create_plan
    return create_plan(task_id, strategy, steps)


@function_tool
def get_task_by_id(task_id: str) -> dict | None:
    """Retrieve a task from the database.

    Args:
        task_id: The ID of the task

    Returns:
        The task as a dictionary, or None if not found
    """
    task = task_ops.get_task(task_id)
    return task.model_dump() if task else None


@function_tool
def get_subtasks_for_task(parent_id: str) -> list[dict]:
    """Get all subtasks for a parent task.

    Args:
        parent_id: The parent task ID

    Returns:
        List of subtasks as dictionaries
    """
    subtasks = task_ops.get_subtasks(parent_id)
    return [t.model_dump() for t in subtasks]


@function_tool
def log_execution(
    task_id: str,
    agent_type: str,
    action: str,
    input_data: str = None,
    output_data: str = None,
    status: str = "success",
    error_message: str = None,
    duration_ms: int = None,
) -> dict:
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
        The created log entry as a dictionary
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
    return log.model_dump()


@function_tool
def get_execution_logs(task_id: str) -> list[dict]:
    """Get all execution logs for a task.

    Args:
        task_id: The task ID

    Returns:
        List of execution logs
    """
    logs = log_ops.get_logs_for_task(task_id)
    return [log.model_dump() for log in logs]


@function_tool
def get_tasks_by_status(status: str) -> list[dict]:
    """Get all tasks with a specific status.

    Args:
        status: The status to filter by (pending, in_progress, completed, failed)

    Returns:
        List of matching tasks
    """
    tasks = task_ops.get_tasks_by_status(TaskStatus(status))
    return [t.model_dump() for t in tasks]


@function_tool
def get_tasks_for_agent(agent_type: str) -> list[dict]:
    """Get all tasks assigned to a specific agent type.

    Args:
        agent_type: The agent type (code, research, writing, communication)

    Returns:
        List of assigned tasks
    """
    tasks = task_ops.get_tasks_by_agent(AgentType(agent_type))
    return [t.model_dump() for t in tasks]
