"""FastAPI routes for the AI Task Management Agent."""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_session
from src.database.orm import (
    User, Task, Session as DBSession, Approval, Reminder,
    TaskStatus, ApprovalStatus, SessionState
)
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
from src.skills.registry import get_registry
from src.skills.base import SkillContext
from src.agent.core import get_agent_handler

# Create routers
router = APIRouter()
users_router = APIRouter(prefix="/users", tags=["users"])
tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])
sessions_router = APIRouter(prefix="/sessions", tags=["sessions"])
chat_router = APIRouter(prefix="/chat", tags=["chat"])
skills_router = APIRouter(prefix="/skills", tags=["skills"])
approvals_router = APIRouter(prefix="/approvals", tags=["approvals"])
reminders_router = APIRouter(prefix="/reminders", tags=["reminders"])


# ============ Health ============

@router.get("/health", response_model=HealthResponse)
async def health_check(session: AsyncSession = Depends(get_session)):
    """Check API health status."""
    try:
        # Check database
        await session.execute(select(func.count()).select_from(User))
        db_status = "connected"
    except Exception:
        db_status = "error"

    # Check skills
    registry = await get_registry()
    skills_count = len(registry.list_skills())

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version="0.1.0",
        database=db_status,
        skills_loaded=skills_count,
    )


# ============ Users ============

@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new user."""
    # Check if email exists
    result = await session.execute(
        select(User).where(User.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    user = User(
        id=uuid.uuid4(),
        email=user_data.email,
        name=user_data.name,
        preferences=user_data.preferences,
    )
    session.add(user)
    await session.flush()
    return user


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get user by ID."""
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@users_router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update user details."""
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    return user


# ============ Tasks ============

@tasks_router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    user_id: uuid.UUID = Query(..., description="User ID"),
    session: AsyncSession = Depends(get_session),
):
    """Create a new task."""
    task = Task(
        id=uuid.uuid4(),
        user_id=user_id,
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        due_date=task_data.due_date,
        tags=task_data.tags,
        parent_id=task_data.parent_id,
        estimated_minutes=task_data.estimated_minutes,
        status=TaskStatus.PENDING,
    )
    session.add(task)
    await session.flush()
    return task


@tasks_router.get("", response_model=TaskListResponse)
async def list_tasks(
    user_id: uuid.UUID = Query(..., description="User ID"),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[int] = Query(None, ge=1, le=5),
    has_due_date: Optional[bool] = None,
    top_level_only: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List tasks with filters."""
    query = select(Task).where(
        Task.user_id == user_id,
        Task.deleted_at.is_(None),
    )

    if status_filter:
        query = query.where(Task.status == TaskStatus(status_filter))
    if priority:
        query = query.where(Task.priority == priority)
    if has_due_date is True:
        query = query.where(Task.due_date.isnot(None))
    elif has_due_date is False:
        query = query.where(Task.due_date.is_(None))
    if top_level_only:
        query = query.where(Task.parent_id.is_(None))

    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Apply pagination
    query = query.order_by(Task.priority.desc(), Task.due_date.asc().nullslast())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    tasks = result.scalars().all()

    return TaskListResponse(
        tasks=tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


@tasks_router.get("/stats", response_model=TaskStatsResponse)
async def get_task_stats(
    user_id: uuid.UUID = Query(..., description="User ID"),
    session: AsyncSession = Depends(get_session),
):
    """Get task statistics."""
    # Import and use the search skill
    registry = await get_registry()
    context = SkillContext(user_id=str(user_id), parameters={"action": "stats"})
    result = await registry.execute_skill("search", context)

    if result.success:
        return TaskStatsResponse(**result.data)
    else:
        raise HTTPException(status_code=500, detail=result.error)


@tasks_router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Query(..., description="User ID"),
    session: AsyncSession = Depends(get_session),
):
    """Get task by ID."""
    result = await session.execute(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@tasks_router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    task_data: TaskUpdate,
    user_id: uuid.UUID = Query(..., description="User ID"),
    session: AsyncSession = Depends(get_session),
):
    """Update a task."""
    result = await session.execute(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status" and value:
            value = TaskStatus(value)
        setattr(task, key, value)

    task.updated_at = datetime.utcnow()

    # Handle status transitions
    if task.status == TaskStatus.COMPLETED and not task.completed_at:
        task.completed_at = datetime.utcnow()
    if task.status == TaskStatus.IN_PROGRESS and not task.started_at:
        task.started_at = datetime.utcnow()

    return task


@tasks_router.delete("/{task_id}", response_model=SuccessResponse)
async def delete_task(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Query(..., description="User ID"),
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a task."""
    result = await session.execute(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.deleted_at = datetime.utcnow()
    return SuccessResponse(message=f"Task '{task.title}' deleted")


@tasks_router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: uuid.UUID,
    user_id: uuid.UUID = Query(..., description="User ID"),
    result_text: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Mark task as completed."""
    query_result = await session.execute(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id,
            Task.deleted_at.is_(None),
        )
    )
    task = query_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.utcnow()
    task.updated_at = datetime.utcnow()
    if result_text:
        task.result = result_text

    return task


# ============ Chat ============

@chat_router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: uuid.UUID = Query(..., description="User ID"),
):
    """Send a message to the AI agent."""
    # Get the agent handler
    handler = get_agent_handler()

    # Process the message through the Core Agent Layer
    result = await handler.process_message(
        user_id=user_id,
        message=request.message,
        session_id=request.session_id,
    )

    return ChatResponse(
        session_id=result.session_id,
        response=result.response,
        actions_taken=result.actions_taken,
        suggestions=result.suggestions,
        pending_approvals=result.pending_approvals,
    )


# ============ Skills ============

@skills_router.get("", response_model=List[SkillManifestResponse])
async def list_skills():
    """List all available skills."""
    registry = await get_registry()
    manifests = registry.list_skills()

    return [
        SkillManifestResponse(
            name=m.name,
            version=m.version,
            description=m.description,
            category=m.category.value,
            triggers=m.triggers,
            permission_level=m.permission_level.value,
            approval_required=m.approval_required,
        )
        for m in manifests
    ]


@skills_router.post("/execute", response_model=SkillExecuteResponse)
async def execute_skill(
    request: SkillExecuteRequest,
    user_id: uuid.UUID = Query(..., description="User ID"),
    session_id: Optional[uuid.UUID] = None,
):
    """Execute a skill directly."""
    registry = await get_registry()

    context = SkillContext(
        user_id=str(user_id),
        session_id=str(session_id) if session_id else None,
        parameters=request.parameters,
    )

    result = await registry.execute_skill(request.skill_name, context)

    return SkillExecuteResponse(
        success=result.success,
        data=result.data,
        error=result.error,
        duration_ms=result.duration_ms,
        requires_approval=result.requires_approval,
        approval_id=uuid.UUID(result.approval_id) if result.approval_id else None,
    )


# ============ Approvals ============

@approvals_router.get("", response_model=List[ApprovalResponse])
async def list_approvals(
    user_id: uuid.UUID = Query(..., description="User ID"),
    status_filter: Optional[str] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_session),
):
    """List pending approvals."""
    query = select(Approval).where(Approval.user_id == user_id)

    if status_filter:
        query = query.where(Approval.status == ApprovalStatus(status_filter))
    else:
        query = query.where(Approval.status == ApprovalStatus.PENDING)

    query = query.order_by(Approval.created_at.desc())

    result = await session.execute(query)
    approvals = result.scalars().all()
    return approvals


@approvals_router.post("/{approval_id}/respond", response_model=ApprovalResponse)
async def respond_to_approval(
    approval_id: uuid.UUID,
    decision: ApprovalDecision,
    user_id: uuid.UUID = Query(..., description="User ID"),
    session: AsyncSession = Depends(get_session),
):
    """Approve or reject a pending action."""
    result = await session.execute(
        select(Approval).where(
            Approval.id == approval_id,
            Approval.user_id == user_id,
            Approval.status == ApprovalStatus.PENDING,
        )
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found or already processed")

    if datetime.utcnow() > approval.expires_at:
        approval.status = ApprovalStatus.EXPIRED
        raise HTTPException(status_code=400, detail="Approval has expired")

    approval.status = ApprovalStatus.APPROVED if decision.approved else ApprovalStatus.REJECTED
    approval.user_response = decision.response
    approval.responded_at = datetime.utcnow()

    # TODO: If approved, execute the action

    return approval


# ============ Reminders ============

@reminders_router.post("", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    reminder_data: ReminderCreate,
    user_id: uuid.UUID = Query(..., description="User ID"),
    session: AsyncSession = Depends(get_session),
):
    """Create a new reminder."""
    reminder = Reminder(
        id=uuid.uuid4(),
        user_id=user_id,
        task_id=reminder_data.task_id,
        message=reminder_data.message,
        scheduled_for=reminder_data.scheduled_for,
        recurrence_rule=reminder_data.recurrence_rule,
        channels=reminder_data.channels,
    )
    session.add(reminder)
    await session.flush()
    return reminder


@reminders_router.get("", response_model=List[ReminderResponse])
async def list_reminders(
    user_id: uuid.UUID = Query(..., description="User ID"),
    pending_only: bool = True,
    session: AsyncSession = Depends(get_session),
):
    """List reminders."""
    query = select(Reminder).where(Reminder.user_id == user_id)

    if pending_only:
        query = query.where(Reminder.sent == False)

    query = query.order_by(Reminder.scheduled_for.asc())

    result = await session.execute(query)
    reminders = result.scalars().all()
    return reminders


@reminders_router.delete("/{reminder_id}", response_model=SuccessResponse)
async def delete_reminder(
    reminder_id: uuid.UUID,
    user_id: uuid.UUID = Query(..., description="User ID"),
    session: AsyncSession = Depends(get_session),
):
    """Delete a reminder."""
    result = await session.execute(
        select(Reminder).where(
            Reminder.id == reminder_id,
            Reminder.user_id == user_id,
        )
    )
    reminder = result.scalar_one_or_none()

    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    await session.delete(reminder)
    return SuccessResponse(message="Reminder deleted")


# Include all routers
router.include_router(users_router)
router.include_router(tasks_router)
router.include_router(sessions_router)
router.include_router(chat_router)
router.include_router(skills_router)
router.include_router(approvals_router)
router.include_router(reminders_router)
