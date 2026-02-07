"""Task Management Module.

Provides task graph management with DAG support.
"""

from src.tasks.graph import TaskGraph, TaskNode, GraphValidationError
from src.tasks.manager import TaskManager, get_task_manager

__all__ = [
    "TaskGraph",
    "TaskNode",
    "GraphValidationError",
    "TaskManager",
    "get_task_manager",
]
