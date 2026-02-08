"""Tests for Approval and Audit functionality."""

import uuid
from datetime import datetime
import pytest

from src.approvals.queue import (
    PendingAction,
    ApprovalResult,
    ApprovalQueue,
)
from src.audit.logger import (
    AuditEntry,
    AuditLogger,
)
from src.database.orm import ApprovalStatus, EventType


class TestApprovalStatus:
    """Tests for ApprovalStatus enum."""

    def test_status_values(self):
        """Test approval status values."""
        assert ApprovalStatus.PENDING.value == "pending"
        assert ApprovalStatus.APPROVED.value == "approved"
        assert ApprovalStatus.REJECTED.value == "rejected"
        assert ApprovalStatus.EXPIRED.value == "expired"


class TestPendingAction:
    """Tests for PendingAction dataclass."""

    def test_create_pending_action(self):
        """Test creating a pending action."""
        approval_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.utcnow()

        action = PendingAction(
            approval_id=approval_id,
            user_id=user_id,
            action_name="email.send",
            action_data={"to": "user@example.com", "subject": "Test"},
            description="Send email to user",
            created_at=now,
            expires_at=None,
            status=ApprovalStatus.PENDING,
        )

        assert action.approval_id == approval_id
        assert action.user_id == user_id
        assert action.action_name == "email.send"
        assert action.action_data["to"] == "user@example.com"
        assert action.status == ApprovalStatus.PENDING


class TestApprovalResult:
    """Tests for ApprovalResult dataclass."""

    def test_success_result(self):
        """Test successful approval result."""
        result = ApprovalResult(
            success=True,
            action_executed=True,
            result_data={"message": "Email sent"},
        )

        assert result.success is True
        assert result.action_executed is True
        assert result.error is None

    def test_failure_result(self):
        """Test failed approval result."""
        result = ApprovalResult(
            success=False,
            error="Approval not found",
        )

        assert result.success is False
        assert result.action_executed is False
        assert result.error == "Approval not found"


class TestApprovalQueueHelpers:
    """Tests for ApprovalQueue helper methods."""

    def test_summarize_email_action(self):
        """Test summarizing email action."""
        queue = ApprovalQueue()

        summary = queue._summarize_action(
            "email.send",
            {"to": "user@example.com", "subject": "Important Update"},
        )

        assert "user@example.com" in summary
        assert "Important Update" in summary

    def test_summarize_task_delete(self):
        """Test summarizing task delete action."""
        queue = ApprovalQueue()

        summary = queue._summarize_action(
            "task.delete",
            {"title": "My Task"},
        )

        assert "Delete task" in summary
        assert "My Task" in summary

    def test_summarize_calendar_action(self):
        """Test summarizing calendar action."""
        queue = ApprovalQueue()

        summary = queue._summarize_action(
            "calendar.create",
            {"title": "Team Meeting"},
        )

        assert "Calendar" in summary
        assert "Team Meeting" in summary

    def test_summarize_github_action(self):
        """Test summarizing GitHub action."""
        queue = ApprovalQueue()

        summary = queue._summarize_action(
            "github.create_issue",
            {"title": "Bug Report"},
        )

        assert "GitHub" in summary
        assert "Bug Report" in summary

    def test_summarize_unknown_action(self):
        """Test summarizing unknown action type."""
        queue = ApprovalQueue()

        summary = queue._summarize_action(
            "custom.action",
            {"data": "value"},
        )

        assert summary == "custom.action"

    def test_queue_initialization(self):
        """Test queue initialization with defaults."""
        queue = ApprovalQueue()

        assert queue.default_expiry_hours == 24

    def test_queue_custom_expiry(self):
        """Test queue initialization with custom expiry."""
        queue = ApprovalQueue(default_expiry_hours=48)

        assert queue.default_expiry_hours == 48

    def test_register_executor(self):
        """Test registering an action executor."""
        queue = ApprovalQueue()

        async def my_executor(data):
            return {"status": "done"}

        queue.register_executor("my_action", my_executor)

        assert "my_action" in queue._executors


class TestEventType:
    """Tests for EventType enum."""

    def test_event_type_values(self):
        """Test event type values (actual ORM values)."""
        # These are the actual EventType values defined in ORM
        assert EventType.SKILL_INVOKE.value == "skill_invoke"
        assert EventType.DECISION.value == "decision"
        assert EventType.USER_INPUT.value == "user_input"
        assert EventType.APPROVAL.value == "approval"
        assert EventType.ERROR.value == "error"
        assert EventType.TASK_UPDATE.value == "task_update"
        assert EventType.REMINDER.value == "reminder"
        assert EventType.SYSTEM.value == "system"


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""

    def test_create_entry(self):
        """Test creating an audit entry."""
        entry_id = uuid.uuid4()
        user_id = uuid.uuid4()
        entity_id = uuid.uuid4()
        now = datetime.utcnow()

        entry = AuditEntry(
            id=entry_id,
            user_id=user_id,
            event_type=EventType.TASK_UPDATE,  # Using actual ORM value
            entity_type="task",
            entity_id=entity_id,
            details={"title": "New Task"},
            session_id=None,
            created_at=now,
            can_undo=True,
        )

        assert entry.id == entry_id
        assert entry.user_id == user_id
        assert entry.event_type == EventType.TASK_UPDATE
        assert entry.entity_type == "task"
        assert entry.can_undo is True


class TestAuditLoggerHelpers:
    """Tests for AuditLogger helper methods."""

    def test_summarize_success_result(self):
        """Test summarizing successful result."""
        logger = AuditLogger()

        summary = logger._summarize_result({
            "success": True,
            "data": {"id": "123", "title": "Task"},
        })

        assert summary["success"] is True
        assert "data_keys" in summary

    def test_summarize_error_result(self):
        """Test summarizing error result."""
        logger = AuditLogger()

        summary = logger._summarize_result({
            "success": False,
            "error": "Something went wrong",
        })

        assert summary["success"] is False
        assert summary["error"] == "Something went wrong"

    def test_summarize_list_result(self):
        """Test summarizing result with list data."""
        logger = AuditLogger()

        summary = logger._summarize_result({
            "success": True,
            "data": [1, 2, 3, 4, 5],
        })

        assert summary["success"] is True
        assert summary["data_count"] == 5

    def test_summarize_empty_result(self):
        """Test summarizing empty result."""
        logger = AuditLogger()

        summary = logger._summarize_result({})

        assert summary == {}
