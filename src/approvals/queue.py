"""Approval Queue - Manages pending action approvals.

Handles:
- Queueing actions for approval
- User approval/rejection
- Execution on approval
- Expiration handling
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.orm import Approval, ApprovalStatus
from src.database.connection import get_async_session
from src.approvals.policy import ApprovalPolicy, get_policy_manager


@dataclass
class PendingAction:
    """An action pending approval."""
    approval_id: uuid.UUID
    user_id: uuid.UUID
    action_name: str
    action_data: Dict[str, Any]
    description: str
    created_at: datetime
    expires_at: Optional[datetime]
    status: ApprovalStatus


@dataclass
class ApprovalResult:
    """Result of processing an approval."""
    success: bool
    action_executed: bool = False
    error: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None


# Type for action executors
ActionExecutor = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class ApprovalQueue:
    """Manages the approval queue for actions.

    Provides:
    - Queueing actions needing approval
    - Approval/rejection handling
    - Action execution on approval
    - Notification to users
    """

    def __init__(
        self,
        default_expiry_hours: int = 24,
    ):
        """Initialize the approval queue.

        Args:
            default_expiry_hours: How long approvals are valid.
        """
        self.default_expiry_hours = default_expiry_hours
        self._executors: Dict[str, ActionExecutor] = {}
        self._policy = get_policy_manager()

    def register_executor(
        self,
        action_name: str,
        executor: ActionExecutor,
    ) -> None:
        """Register an executor for an action type.

        Args:
            action_name: The action name.
            executor: Async function to execute the action.
        """
        self._executors[action_name] = executor

    async def queue_action(
        self,
        user_id: uuid.UUID,
        action_name: str,
        action_data: Dict[str, Any],
        description: Optional[str] = None,
        session_id: Optional[uuid.UUID] = None,
        skill_name: Optional[str] = None,
        expiry_hours: Optional[int] = None,
    ) -> PendingAction:
        """Queue an action for approval.

        Args:
            user_id: The user's ID.
            action_name: The action name.
            action_data: Data needed to execute the action.
            description: Human-readable description.
            session_id: Optional session ID.
            skill_name: Optional skill that triggered this.
            expiry_hours: Optional custom expiry.

        Returns:
            PendingAction object.
        """
        expires_at = datetime.utcnow() + timedelta(
            hours=expiry_hours or self.default_expiry_hours
        )

        # Get action info for description
        action_info = self._policy.get_action_info(action_name)
        if not description and action_info:
            description = action_info.description

        async with get_async_session() as session:
            approval = Approval(
                user_id=user_id,
                skill_name=skill_name or action_name,
                action_type=action_name,
                action_data=action_data,
                status=ApprovalStatus.PENDING,
                expires_at=expires_at,
            )
            session.add(approval)
            await session.commit()
            await session.refresh(approval)

        return PendingAction(
            approval_id=approval.id,
            user_id=user_id,
            action_name=action_name,
            action_data=action_data,
            description=description or action_name,
            created_at=approval.created_at,
            expires_at=expires_at,
            status=ApprovalStatus.PENDING,
        )

    async def check_and_queue(
        self,
        user_id: uuid.UUID,
        action_name: str,
        action_data: Dict[str, Any],
        description: Optional[str] = None,
    ) -> tuple[bool, Optional[PendingAction]]:
        """Check if action needs approval and queue if so.

        Args:
            user_id: The user's ID.
            action_name: The action name.
            action_data: Action data.
            description: Human-readable description.

        Returns:
            Tuple of (needs_approval, pending_action or None).
        """
        # Load user overrides if not cached
        await self._policy.load_user_overrides(user_id)

        if self._policy.requires_approval(user_id, action_name):
            pending = await self.queue_action(
                user_id=user_id,
                action_name=action_name,
                action_data=action_data,
                description=description,
            )
            return True, pending

        return False, None

    async def approve(
        self,
        approval_id: uuid.UUID,
        user_id: uuid.UUID,
        execute: bool = True,
    ) -> ApprovalResult:
        """Approve a pending action.

        Args:
            approval_id: The approval ID.
            user_id: The user approving (must match).
            execute: Whether to execute immediately.

        Returns:
            ApprovalResult.
        """
        async with get_async_session() as session:
            approval = await session.get(Approval, approval_id)

            if not approval:
                return ApprovalResult(
                    success=False,
                    error="Approval not found",
                )

            if approval.user_id != user_id:
                return ApprovalResult(
                    success=False,
                    error="Not authorized to approve this action",
                )

            if approval.status != ApprovalStatus.PENDING:
                return ApprovalResult(
                    success=False,
                    error=f"Approval already {approval.status.value}",
                )

            if approval.expires_at and approval.expires_at < datetime.utcnow():
                approval.status = ApprovalStatus.EXPIRED
                await session.commit()
                return ApprovalResult(
                    success=False,
                    error="Approval has expired",
                )

            approval.status = ApprovalStatus.APPROVED
            approval.responded_at = datetime.utcnow()
            await session.commit()

        # Execute if requested
        if execute:
            return await self._execute_action(approval)

        return ApprovalResult(success=True, action_executed=False)

    async def reject(
        self,
        approval_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> ApprovalResult:
        """Reject a pending action.

        Args:
            approval_id: The approval ID.
            user_id: The user rejecting.
            reason: Optional rejection reason.

        Returns:
            ApprovalResult.
        """
        async with get_async_session() as session:
            approval = await session.get(Approval, approval_id)

            if not approval:
                return ApprovalResult(
                    success=False,
                    error="Approval not found",
                )

            if approval.user_id != user_id:
                return ApprovalResult(
                    success=False,
                    error="Not authorized to reject this action",
                )

            if approval.status != ApprovalStatus.PENDING:
                return ApprovalResult(
                    success=False,
                    error=f"Approval already {approval.status.value}",
                )

            approval.status = ApprovalStatus.REJECTED
            approval.responded_at = datetime.utcnow()
            if reason:
                approval.action_data = {
                    **approval.action_data,
                    "_rejection_reason": reason,
                }
            await session.commit()

        return ApprovalResult(success=True, action_executed=False)

    async def _execute_action(
        self,
        approval: Approval,
    ) -> ApprovalResult:
        """Execute an approved action.

        Args:
            approval: The approved Approval object.

        Returns:
            ApprovalResult.
        """
        executor = self._executors.get(approval.action_type)
        if not executor:
            return ApprovalResult(
                success=True,
                action_executed=False,
                error=f"No executor registered for {approval.action_type}",
            )

        try:
            result_data = await executor(approval.action_data)
            return ApprovalResult(
                success=True,
                action_executed=True,
                result_data=result_data,
            )
        except Exception as e:
            return ApprovalResult(
                success=True,
                action_executed=False,
                error=str(e),
            )

    async def get_pending(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
    ) -> List[PendingAction]:
        """Get pending approvals for a user.

        Args:
            user_id: The user's ID.
            limit: Maximum to return.

        Returns:
            List of PendingAction.
        """
        async with get_async_session() as session:
            result = await session.execute(
                select(Approval)
                .where(
                    Approval.user_id == user_id,
                    Approval.status == ApprovalStatus.PENDING,
                )
                .order_by(Approval.created_at.desc())
                .limit(limit)
            )
            approvals = result.scalars().all()

        # Check for expired
        pending = []
        for approval in approvals:
            if approval.expires_at and approval.expires_at < datetime.utcnow():
                # Mark as expired (async update)
                await self._mark_expired(approval.id)
                continue

            action_info = self._policy.get_action_info(approval.action_type)
            description = (
                action_info.description if action_info
                else approval.action_type
            )

            pending.append(PendingAction(
                approval_id=approval.id,
                user_id=approval.user_id,
                action_name=approval.action_type,
                action_data=approval.action_data,
                description=description,
                created_at=approval.created_at,
                expires_at=approval.expires_at,
                status=approval.status,
            ))

        return pending

    async def _mark_expired(self, approval_id: uuid.UUID) -> None:
        """Mark an approval as expired.

        Args:
            approval_id: The approval ID.
        """
        async with get_async_session() as session:
            await session.execute(
                update(Approval)
                .where(Approval.id == approval_id)
                .values(status=ApprovalStatus.EXPIRED)
            )
            await session.commit()

    async def get_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        include_pending: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get approval history for a user.

        Args:
            user_id: The user's ID.
            limit: Maximum to return.
            include_pending: Include pending approvals.

        Returns:
            List of approval dicts.
        """
        async with get_async_session() as session:
            conditions = [Approval.user_id == user_id]
            if not include_pending:
                conditions.append(Approval.status != ApprovalStatus.PENDING)

            result = await session.execute(
                select(Approval)
                .where(and_(*conditions))
                .order_by(Approval.created_at.desc())
                .limit(limit)
            )
            approvals = result.scalars().all()

        return [
            {
                "id": str(a.id),
                "action_type": a.action_type,
                "status": a.status.value,
                "created_at": a.created_at.isoformat(),
                "responded_at": a.responded_at.isoformat() if a.responded_at else None,
                "action_summary": self._summarize_action(a.action_type, a.action_data),
            }
            for a in approvals
        ]

    def _summarize_action(
        self,
        action_type: str,
        action_data: Dict[str, Any],
    ) -> str:
        """Create a human-readable summary of an action.

        Args:
            action_type: The action type.
            action_data: The action data.

        Returns:
            Summary string.
        """
        if action_type == "email.send":
            to = action_data.get("to", "unknown")
            subject = action_data.get("subject", "no subject")
            return f"Send email to {to}: {subject}"

        if action_type == "task.delete":
            title = action_data.get("title", "unknown")
            return f"Delete task: {title}"

        if action_type.startswith("calendar."):
            title = action_data.get("title", "event")
            return f"Calendar: {title}"

        if action_type.startswith("github."):
            title = action_data.get("title", "")
            return f"GitHub: {title}"

        return action_type

    async def cancel(
        self,
        approval_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Cancel a pending approval.

        Args:
            approval_id: The approval ID.
            user_id: The user cancelling.

        Returns:
            True if cancelled.
        """
        async with get_async_session() as session:
            approval = await session.get(Approval, approval_id)

            if not approval or approval.user_id != user_id:
                return False

            if approval.status != ApprovalStatus.PENDING:
                return False

            approval.status = ApprovalStatus.EXPIRED  # Using expired as cancelled
            approval.responded_at = datetime.utcnow()
            await session.commit()

        return True

    async def cleanup_expired(self) -> int:
        """Clean up expired approvals.

        Returns:
            Number of approvals marked as expired.
        """
        async with get_async_session() as session:
            result = await session.execute(
                update(Approval)
                .where(
                    Approval.status == ApprovalStatus.PENDING,
                    Approval.expires_at < datetime.utcnow(),
                )
                .values(status=ApprovalStatus.EXPIRED)
            )
            await session.commit()
            return result.rowcount


# Global queue
_queue: Optional[ApprovalQueue] = None


def get_approval_queue() -> ApprovalQueue:
    """Get the global approval queue."""
    global _queue
    if _queue is None:
        _queue = ApprovalQueue()
    return _queue
