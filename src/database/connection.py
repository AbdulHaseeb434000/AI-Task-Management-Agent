"""Database connection management."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# Default database path
DEFAULT_DB_PATH = Path("data/tasks.db")


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialize the database with required tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                plan_id TEXT,
                parent_id TEXT,
                subtask_ids TEXT DEFAULT '[]',
                dependencies TEXT DEFAULT '[]',
                assigned_agent TEXT,
                result TEXT,
                error TEXT,
                metadata TEXT DEFAULT '{}',
                tags TEXT DEFAULT '[]',
                FOREIGN KEY (parent_id) REFERENCES tasks(id),
                FOREIGN KEY (plan_id) REFERENCES plans(id)
            )
        """)

        # Plans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                strategy TEXT NOT NULL,
                steps TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                total_estimated_minutes INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)

        # Execution logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_type TEXT NOT NULL,
                action TEXT NOT NULL,
                input_data TEXT,
                output_data TEXT,
                status TEXT NOT NULL DEFAULT 'success',
                error_message TEXT,
                duration_ms INTEGER,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)

        # Indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_agent)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_task ON execution_logs(task_id)")

        conn.commit()


@contextmanager
def get_db(db_path: Path = DEFAULT_DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection context manager."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
