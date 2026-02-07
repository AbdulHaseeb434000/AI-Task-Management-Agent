"""Database module for PostgreSQL persistence."""

from .orm import (
    Base,
    User,
    Task,
    Plan,
    Session,
    Skill,
    Approval,
    Reminder,
    UserPreference,
    Memory,
    AuditLog,
    UndoAction,
    TaskStatus,
    PermissionLevel,
    ApprovalStatus,
    ReminderType,
    SessionState,
    EventType,
)
from .connection import (
    async_engine,
    sync_engine,
    AsyncSessionLocal,
    SyncSessionLocal,
    init_db,
    init_db_sync,
    get_async_session,
    get_sync_session,
    get_session,
)

# Keep old Pydantic models for backward compatibility
from .models import (
    Task as TaskSchema,
    Plan as PlanSchema,
    PlanStep,
    ExecutionLog,
    TaskBreakdown,
    AgentType,
)

__all__ = [
    # ORM Models
    "Base",
    "User",
    "Task",
    "Plan",
    "Session",
    "Skill",
    "Approval",
    "Reminder",
    "UserPreference",
    "Memory",
    "AuditLog",
    "UndoAction",
    # Enums
    "TaskStatus",
    "PermissionLevel",
    "ApprovalStatus",
    "ReminderType",
    "SessionState",
    "EventType",
    # Connection
    "async_engine",
    "sync_engine",
    "AsyncSessionLocal",
    "SyncSessionLocal",
    "init_db",
    "init_db_sync",
    "get_async_session",
    "get_sync_session",
    "get_session",
    # Pydantic Schemas (backward compat)
    "TaskSchema",
    "PlanSchema",
    "PlanStep",
    "ExecutionLog",
    "TaskBreakdown",
    "AgentType",
]
