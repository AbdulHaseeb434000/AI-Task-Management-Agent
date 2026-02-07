"""API module - FastAPI routes and schemas."""

from src.api.routes import router
from src.api.schemas import (
    # User
    UserCreate, UserUpdate, UserResponse,
    # Task
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, TaskFilters, TaskStatsResponse,
    # Session
    SessionResponse,
    # Chat
    ChatRequest, ChatResponse,
    # Skill
    SkillManifestResponse, SkillExecuteRequest, SkillExecuteResponse,
    # Approval
    ApprovalResponse, ApprovalDecision,
    # Reminder
    ReminderCreate, ReminderResponse,
    # Generic
    SuccessResponse, ErrorResponse, HealthResponse,
)

__all__ = [
    "router",
    # User
    "UserCreate", "UserUpdate", "UserResponse",
    # Task
    "TaskCreate", "TaskUpdate", "TaskResponse", "TaskListResponse", "TaskFilters", "TaskStatsResponse",
    # Session
    "SessionResponse",
    # Chat
    "ChatRequest", "ChatResponse",
    # Skill
    "SkillManifestResponse", "SkillExecuteRequest", "SkillExecuteResponse",
    # Approval
    "ApprovalResponse", "ApprovalDecision",
    # Reminder
    "ReminderCreate", "ReminderResponse",
    # Generic
    "SuccessResponse", "ErrorResponse", "HealthResponse",
]
