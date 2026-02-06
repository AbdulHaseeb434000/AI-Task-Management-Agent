"""Database models for the multi-agent task management system."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class TaskStatus(str, Enum):
    """Status of a task in its lifecycle."""
    PENDING = "pending"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"  # Waiting for dependencies
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(str, Enum):
    """Types of specialist agents."""
    ORCHESTRATOR = "orchestrator"
    CODE = "code"
    RESEARCH = "research"
    WRITING = "writing"
    COMMUNICATION = "communication"
    FILE = "file"


class PlanStep(BaseModel):
    """A single step in an execution plan."""
    order: int = Field(description="Execution order (1-based)")
    description: str = Field(description="What this step accomplishes")
    agent_type: AgentType = Field(description="Which specialist handles this")
    dependencies: list[int] = Field(default_factory=list, description="Step orders that must complete first")
    subtask_id: Optional[str] = Field(default=None, description="Created subtask reference")
    estimated_minutes: int = Field(default=15, description="Estimated time to complete")


class Plan(BaseModel):
    """Execution plan for a task."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = Field(description="Parent task ID")
    strategy: str = Field(description="High-level approach description")
    steps: list[PlanStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    total_estimated_minutes: int = Field(default=0)

    def calculate_duration(self) -> int:
        """Calculate total estimated duration."""
        self.total_estimated_minutes = sum(step.estimated_minutes for step in self.steps)
        return self.total_estimated_minutes


class Task(BaseModel):
    """A task or subtask in the system."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(description="Short task title")
    description: str = Field(description="Full task description")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: int = Field(default=3, ge=1, le=5, description="Priority 1-5 (5 highest)")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Relationships
    plan_id: Optional[str] = Field(default=None, description="Associated plan")
    parent_id: Optional[str] = Field(default=None, description="Parent task (for subtasks)")
    subtask_ids: list[str] = Field(default_factory=list, description="Child subtasks")
    dependencies: list[str] = Field(default_factory=list, description="Task IDs that must complete first")

    # Assignment
    assigned_agent: Optional[AgentType] = None

    # Results
    result: Optional[str] = Field(default=None, description="Outcome when completed")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    # Context
    metadata: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    def mark_started(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_completed(self, result: str) -> None:
        """Mark task as completed with result."""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_failed(self, error: str) -> None:
        """Mark task as failed with error."""
        self.status = TaskStatus.FAILED
        self.error = error
        self.updated_at = datetime.utcnow()

    def is_blocked(self) -> bool:
        """Check if task is blocked by dependencies."""
        return self.status == TaskStatus.WAITING and len(self.dependencies) > 0


class ExecutionLog(BaseModel):
    """Log entry for task execution."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    agent_type: AgentType
    action: str = Field(description="What action was taken")
    input_data: Optional[str] = None
    output_data: Optional[str] = None
    status: str = Field(default="success")  # success, error, pending
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TaskBreakdown(BaseModel):
    """Output from the planner for task breakdown."""
    original_task: str
    plan: Plan
    subtasks: list[Task]
    recommended_order: list[str] = Field(description="Task IDs in recommended execution order")
