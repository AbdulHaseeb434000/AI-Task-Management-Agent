"""API request/response schemas using Pydantic."""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Any, Dict
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


# Enums for API
class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PriorityEnum(int, Enum):
    LOWEST = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    HIGHEST = 5


# User schemas
class UserCreate(BaseModel):
    email: EmailStr
    name: str
    preferences: Dict[str, Any] = Field(default_factory=dict)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    working_hours: Optional[Dict[str, str]] = None
    communication_style: Optional[str] = None
    timezone: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    preferences: Dict[str, Any]
    working_hours: Dict[str, Any]
    communication_style: str
    timezone: str
    onboarding_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Task schemas
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: int = Field(default=3, ge=1, le=5)
    due_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    parent_id: Optional[UUID] = None
    estimated_minutes: Optional[int] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[TaskStatusEnum] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    result: Optional[str] = None


class TaskResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    status: TaskStatusEnum
    priority: int
    due_date: Optional[datetime]
    scheduled_start: Optional[datetime]
    estimated_minutes: Optional[int]
    actual_minutes: Optional[int]
    parent_id: Optional[UUID]
    tags: List[str]
    result: Optional[str]
    blocked_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int


class TaskFilters(BaseModel):
    status: Optional[TaskStatusEnum] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    priority_min: Optional[int] = Field(None, ge=1, le=5)
    priority_max: Optional[int] = Field(None, ge=1, le=5)
    has_due_date: Optional[bool] = None
    is_overdue: Optional[bool] = None
    tags: Optional[List[str]] = None
    parent_id: Optional[UUID] = None
    top_level_only: Optional[bool] = None


# Session schemas
class SessionCreate(BaseModel):
    pass  # No input needed, created from auth


class SessionResponse(BaseModel):
    id: UUID
    state: str
    current_task_id: Optional[UUID]
    started_at: datetime
    last_activity: datetime

    class Config:
        from_attributes = True


# Conversation schemas
class MessageInput(BaseModel):
    content: str = Field(..., min_length=1)
    session_id: Optional[UUID] = None


class MessageResponse(BaseModel):
    role: str  # user, assistant
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationResponse(BaseModel):
    session_id: UUID
    messages: List[MessageResponse]
    current_task: Optional[TaskResponse] = None
    pending_approvals: List[Dict[str, Any]] = Field(default_factory=list)


# Chat/Agent interaction
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: Optional[UUID] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: UUID
    response: str
    actions_taken: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    pending_approvals: List[str] = Field(default_factory=list)
    blocked: bool = False
    violations: Optional[List[str]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Skill schemas
class SkillManifestResponse(BaseModel):
    name: str
    version: str
    description: str
    category: str
    triggers: List[str]
    permission_level: str
    approval_required: bool

    class Config:
        from_attributes = True


class SkillExecuteRequest(BaseModel):
    skill_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SkillExecuteResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    requires_approval: bool = False
    approval_id: Optional[UUID] = None


# Approval schemas
class ApprovalCreate(BaseModel):
    skill_name: str
    action: str
    parameters: Dict[str, Any]
    reasoning: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: UUID
    skill_name: str
    action: str
    parameters: Dict[str, Any]
    reasoning: Optional[str]
    status: str
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class ApprovalDecision(BaseModel):
    approved: bool
    response: Optional[str] = None


# Reminder schemas
class ReminderCreate(BaseModel):
    task_id: Optional[UUID] = None
    message: str
    scheduled_for: datetime
    recurrence_rule: Optional[str] = None
    channels: List[str] = Field(default_factory=lambda: ["push"])


class ReminderResponse(BaseModel):
    id: UUID
    task_id: Optional[UUID]
    message: str
    scheduled_for: datetime
    recurrence_rule: Optional[str]
    channels: List[str]
    sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Stats and analytics
class TaskStatsResponse(BaseModel):
    total_tasks: int
    by_status: Dict[str, int]
    overdue: int
    due_today: int
    completed_last_30_days: int


# Health check
class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    skills_loaded: int


# Generic responses
class SuccessResponse(BaseModel):
    success: bool = True
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
