"""Database CRUD operations for tasks and plans."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Task, Plan, PlanStep, ExecutionLog, TaskStatus, AgentType
from .connection import get_db, DEFAULT_DB_PATH


class TaskOperations:
    """CRUD operations for tasks."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def create_task(self, task: Task) -> Task:
        """Create a new task."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (
                    id, title, description, status, priority,
                    created_at, updated_at, started_at, completed_at,
                    plan_id, parent_id, subtask_ids, dependencies,
                    assigned_agent, result, error, metadata, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id,
                task.title,
                task.description,
                task.status.value,
                task.priority,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.plan_id,
                task.parent_id,
                json.dumps(task.subtask_ids),
                json.dumps(task.dependencies),
                task.assigned_agent.value if task.assigned_agent else None,
                task.result,
                task.error,
                json.dumps(task.metadata),
                json.dumps(task.tags),
            ))
            conn.commit()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_task(row)
        return None

    def update_task(self, task: Task) -> Task:
        """Update an existing task."""
        task.updated_at = datetime.utcnow()
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks SET
                    title = ?, description = ?, status = ?, priority = ?,
                    updated_at = ?, started_at = ?, completed_at = ?,
                    plan_id = ?, subtask_ids = ?, dependencies = ?,
                    assigned_agent = ?, result = ?, error = ?,
                    metadata = ?, tags = ?
                WHERE id = ?
            """, (
                task.title,
                task.description,
                task.status.value,
                task.priority,
                task.updated_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.plan_id,
                json.dumps(task.subtask_ids),
                json.dumps(task.dependencies),
                task.assigned_agent.value if task.assigned_agent else None,
                task.result,
                task.error,
                json.dumps(task.metadata),
                json.dumps(task.tags),
                task.id,
            ))
            conn.commit()
        return task

    def delete_task(self, task_id: str) -> bool:
        """Delete a task by ID."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        """Get all tasks with a specific status."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE status = ?", (status.value,))
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def get_subtasks(self, parent_id: str) -> list[Task]:
        """Get all subtasks of a parent task."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE parent_id = ?", (parent_id,))
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def get_tasks_by_agent(self, agent_type: AgentType) -> list[Task]:
        """Get all tasks assigned to a specific agent."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE assigned_agent = ?", (agent_type.value,))
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def get_pending_tasks(self) -> list[Task]:
        """Get all pending tasks ready for execution."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM tasks
                WHERE status IN ('pending', 'waiting')
                ORDER BY priority DESC, created_at ASC
            """)
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def _row_to_task(self, row) -> Task:
        """Convert a database row to a Task object."""
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            plan_id=row["plan_id"],
            parent_id=row["parent_id"],
            subtask_ids=json.loads(row["subtask_ids"]),
            dependencies=json.loads(row["dependencies"]),
            assigned_agent=AgentType(row["assigned_agent"]) if row["assigned_agent"] else None,
            result=row["result"],
            error=row["error"],
            metadata=json.loads(row["metadata"]),
            tags=json.loads(row["tags"]),
        )


class PlanOperations:
    """CRUD operations for plans."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def create_plan(self, plan: Plan) -> Plan:
        """Create a new plan."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO plans (id, task_id, strategy, steps, created_at, total_estimated_minutes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                plan.id,
                plan.task_id,
                plan.strategy,
                json.dumps([step.model_dump() for step in plan.steps]),
                plan.created_at.isoformat(),
                plan.total_estimated_minutes,
            ))
            conn.commit()
        return plan

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_plan(row)
        return None

    def get_plan_by_task(self, task_id: str) -> Optional[Plan]:
        """Get plan for a specific task."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plans WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_plan(row)
        return None

    def _row_to_plan(self, row) -> Plan:
        """Convert a database row to a Plan object."""
        steps_data = json.loads(row["steps"])
        steps = [PlanStep(**step) for step in steps_data]
        return Plan(
            id=row["id"],
            task_id=row["task_id"],
            strategy=row["strategy"],
            steps=steps,
            created_at=datetime.fromisoformat(row["created_at"]),
            total_estimated_minutes=row["total_estimated_minutes"],
        )


class LogOperations:
    """Operations for execution logs."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def create_log(self, log: ExecutionLog) -> ExecutionLog:
        """Create a new execution log entry."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO execution_logs (
                    id, task_id, agent_type, action, input_data, output_data,
                    status, error_message, duration_ms, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log.id,
                log.task_id,
                log.agent_type.value,
                log.action,
                log.input_data,
                log.output_data,
                log.status,
                log.error_message,
                log.duration_ms,
                log.timestamp.isoformat(),
            ))
            conn.commit()
        return log

    def get_logs_for_task(self, task_id: str) -> list[ExecutionLog]:
        """Get all logs for a task."""
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM execution_logs WHERE task_id = ? ORDER BY timestamp",
                (task_id,)
            )
            return [self._row_to_log(row) for row in cursor.fetchall()]

    def _row_to_log(self, row) -> ExecutionLog:
        """Convert a database row to an ExecutionLog object."""
        return ExecutionLog(
            id=row["id"],
            task_id=row["task_id"],
            agent_type=AgentType(row["agent_type"]),
            action=row["action"],
            input_data=row["input_data"],
            output_data=row["output_data"],
            status=row["status"],
            error_message=row["error_message"],
            duration_ms=row["duration_ms"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
