"""SQLAlchemy ORM models for PostgreSQL.

These models define the database schema following spec.md architecture.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, JSON,
    ForeignKey, Enum, Table, Index
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Enums
class TaskStatus(str, PyEnum):
    PENDING = "pending"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PermissionLevel(str, PyEnum):
    INTERNAL = "internal"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"
    AUTONOMOUS = "autonomous"


class ApprovalStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ReminderType(str, PyEnum):
    TIME_BASED = "time_based"
    RELATIVE = "relative"
    SMART = "smart"
    RECURRING = "recurring"


class SessionState(str, PyEnum):
    ACTIVE = "active"
    IDLE = "idle"
    EXPIRED = "expired"


class EventType(str, PyEnum):
    SKILL_INVOKE = "skill_invoke"
    DECISION = "decision"
    USER_INPUT = "user_input"
    APPROVAL = "approval"
    ERROR = "error"
    TASK_UPDATE = "task_update"
    REMINDER = "reminder"
    SYSTEM = "system"


# Association table for task dependencies (many-to-many self-referential)
task_dependencies = Table(
    "task_dependencies",
    Base.metadata,
    Column("task_id", UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("depends_on_id", UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    """User model."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Authentication
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=True)  # Nullable for OAuth users
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Preferences (compact summary for hot memory)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    working_hours: Mapped[dict] = mapped_column(JSON, default=dict)  # {"start": "09:00", "end": "17:00"}
    communication_style: Mapped[str] = mapped_column(String(20), default="balanced")  # brief, balanced, detailed
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Onboarding
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    preferences_history = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")


class Task(Base):
    """Task model following spec.md Task Graph structure."""
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Core fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.PENDING, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1-5 (5 = highest)

    # Scheduling
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    actual_minutes: Mapped[int] = mapped_column(Integer, nullable=True)

    # Hierarchy
    parent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)

    # Organization
    tags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    task_metadata: Mapped[dict] = mapped_column(JSON, default=dict)  # Renamed from 'metadata' (reserved)

    # Results
    result: Mapped[str] = mapped_column(Text, nullable=True)
    blocked_reason: Mapped[str] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft delete
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="tasks")
    parent = relationship("Task", remote_side=[id], backref="subtasks")
    dependencies = relationship(
        "Task",
        secondary=task_dependencies,
        primaryjoin=id == task_dependencies.c.task_id,
        secondaryjoin=id == task_dependencies.c.depends_on_id,
        backref="dependents"
    )
    plan = relationship("Plan", back_populates="task", uselist=False)
    reminders = relationship("Reminder", back_populates="task", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="task")

    __table_args__ = (
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_user_priority", "user_id", "priority"),
        Index("ix_tasks_parent", "parent_id"),
    )


class Plan(Base):
    """Execution plan for a task."""
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True)

    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[list] = mapped_column(JSON, default=list)  # List of PlanStep dicts
    total_estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    task = relationship("Task", back_populates="plan")


class Session(Base):
    """Conversation session for context management."""
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    state: Mapped[SessionState] = mapped_column(Enum(SessionState), default=SessionState.ACTIVE)

    # Context (hot memory)
    current_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    conversation_history: Mapped[list] = mapped_column(JSON, default=list)  # Last N turns
    pending_questions: Mapped[list] = mapped_column(JSON, default=list)
    pending_approvals: Mapped[list] = mapped_column(JSON, default=list)
    context_summary: Mapped[str] = mapped_column(Text, nullable=True)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")
    current_task = relationship("Task", foreign_keys=[current_task_id])

    __table_args__ = (
        Index("ix_sessions_user_state", "user_id", "state"),
    )


class Skill(Base):
    """Registered skill with manifest."""
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # internal, external, autonomous

    # Manifest
    triggers: Mapped[list] = mapped_column(ARRAY(String), default=list)
    parameters_schema: Mapped[dict] = mapped_column(JSON, default=dict)

    # Permissions
    permission_level: Mapped[PermissionLevel] = mapped_column(Enum(PermissionLevel), default=PermissionLevel.INTERNAL)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    data_access: Mapped[list] = mapped_column(ARRAY(String), default=list)
    external_calls: Mapped[bool] = mapped_column(Boolean, default=False)

    # Execution
    timeout_ms: Mapped[int] = mapped_column(Integer, default=5000)
    module_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # State
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    load_strategy: Mapped[str] = mapped_column(String(20), default="lazy")  # eager, lazy, jit

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Approval(Base):
    """Approval queue for actions requiring confirmation."""
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)

    # Action
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    reasoning: Mapped[str] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    user_response: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="approvals")

    __table_args__ = (
        Index("ix_approvals_user_status", "user_id", "status"),
    )


class Reminder(Base):
    """Task reminder."""
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)

    reminder_type: Mapped[ReminderType] = mapped_column(Enum(ReminderType), default=ReminderType.TIME_BASED)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    recurrence_rule: Mapped[str] = mapped_column(String(100), nullable=True)  # cron expression
    channels: Mapped[list] = mapped_column(ARRAY(String), default=lambda: ["push"])

    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="reminders")
    task = relationship("Task", back_populates="reminders")

    __table_args__ = (
        Index("ix_reminders_pending", "scheduled_for", "sent"),
    )


class UserPreference(Base):
    """Learned user preferences."""
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    category: Mapped[str] = mapped_column(String(100), nullable=False)  # time_patterns, task_preferences, etc.
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source: Mapped[str] = mapped_column(String(50), default="inferred")  # explicit, inferred, feedback

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="preferences_history")

    __table_args__ = (
        Index("ix_prefs_user_category", "user_id", "category"),
    )


class Memory(Base):
    """Warm/Cold memory for semantic retrieval."""
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=True)

    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)  # conversation, task_context, pattern
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # session, task, learning
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Retrieval
    embedding: Mapped[list] = mapped_column(ARRAY(Float), nullable=True)
    keywords: Mapped[list] = mapped_column(ARRAY(String), default=list)

    # Lifecycle
    tier: Mapped[str] = mapped_column(String(10), default="warm")  # warm, cold
    relevance_score: Mapped[float] = mapped_column(Float, default=1.0)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="memories")

    __table_args__ = (
        Index("ix_memories_user_type", "user_id", "memory_type"),
        Index("ix_memories_tier", "tier"),
    )


class AuditLog(Base):
    """Audit log for all agent actions."""
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)

    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False, index=True)

    skill: Mapped[str] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=True)
    input_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict] = mapped_column(JSON, nullable=True)

    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    reasoning: Mapped[str] = mapped_column(Text, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")
    task = relationship("Task", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_user_time", "user_id", "timestamp"),
    )


class UndoAction(Base):
    """Undo history for reversible actions."""
    __tablename__ = "undo_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # create, update, delete, complete
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # task, reminder, etc.
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    previous_state: Mapped[dict] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict] = mapped_column(JSON, nullable=True)

    undone: Mapped[bool] = mapped_column(Boolean, default=False)
    undone_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_undo_session", "session_id", "created_at"),
    )


class APIKey(Base):
    """API keys for programmatic access."""
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)  # User-friendly name
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)  # Hashed key
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False)  # First 8 chars for identification

    # Permissions
    scopes: Mapped[list] = mapped_column(ARRAY(String), default=list)  # ["tasks:read", "tasks:write", etc.]

    # Rate limiting
    rate_limit: Mapped[int] = mapped_column(Integer, default=1000)  # Requests per hour
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_user", "user_id"),
        Index("ix_api_keys_prefix", "key_prefix"),
    )
