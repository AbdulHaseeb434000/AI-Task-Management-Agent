"""Email Skill - Send and manage emails.

Supports:
- SMTP sending
- Gmail API (placeholder)
- Outlook/Graph API (placeholder)
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from src.skills.base import (
    BaseSkill,
    SkillManifest,
    SkillCategory,
    SkillContext,
    SkillResult,
    LoadStrategy,
    PermissionLevel,
)


class EmailProvider(Enum):
    """Supported email providers."""
    SMTP = "smtp"
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SENDGRID = "sendgrid"


class EmailPriority(Enum):
    """Email priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass
class EmailMessage:
    """An email message."""
    id: str
    to: List[str]
    subject: str
    body: str
    from_address: Optional[str] = None
    cc: List[str] = None
    bcc: List[str] = None
    reply_to: Optional[str] = None
    priority: EmailPriority = EmailPriority.NORMAL
    html_body: Optional[str] = None
    attachments: List[Dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None

    def __post_init__(self):
        if self.cc is None:
            self.cc = []
        if self.bcc is None:
            self.bcc = []
        if self.attachments is None:
            self.attachments = []


class EmailSkill(BaseSkill):
    """Skill for email operations.

    Actions:
    - send: Send an email
    - draft: Create a draft email
    - schedule: Schedule an email for later
    - template: Use a template to send email
    - reply: Reply to an email
    """

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="email",
            description="Send and manage emails",
            version="1.0.0",
            category=SkillCategory.EXTERNAL,
            triggers=[
                "email", "send email", "mail", "message",
                "notify via email", "email reminder",
            ],
            permission_level=PermissionLevel.EXTERNAL,
            approval_required=True,  # Always require approval for sending
            load_strategy=LoadStrategy.LAZY,
            timeout_ms=30000,
            required_config=["email_provider"],
            parameters_schema={
                "action": {"type": "string", "required": True},
                "to": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "array", "items": {"type": "string"}},
                "priority": {"type": "string", "enum": ["low", "normal", "high"]},
            },
        )

    async def execute(self, context: SkillContext) -> SkillResult:
        """Execute an email action."""
        action = context.parameters.get("action", "send")

        actions = {
            "send": self._send_email,
            "draft": self._create_draft,
            "schedule": self._schedule_email,
            "template": self._send_from_template,
            "preview": self._preview_email,
        }

        handler = actions.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action: {action}. Valid actions: {list(actions.keys())}",
            )

        return await handler(context)

    async def _send_email(self, context: SkillContext) -> SkillResult:
        """Send an email."""
        params = context.parameters

        # Validate required fields
        to = params.get("to", [])
        if isinstance(to, str):
            to = [to]
        if not to:
            return SkillResult(success=False, error="Recipient (to) is required")

        subject = params.get("subject", "")
        if not subject:
            return SkillResult(success=False, error="Subject is required")

        body = params.get("body", "")
        if not body:
            return SkillResult(success=False, error="Body is required")

        # Build email message
        message = EmailMessage(
            id=str(uuid.uuid4()),
            to=to,
            subject=subject,
            body=body,
            cc=params.get("cc", []),
            bcc=params.get("bcc", []),
            priority=EmailPriority(params.get("priority", "normal")),
            html_body=params.get("html_body"),
        )

        # TODO: Integrate with actual email provider (SMTP, SendGrid, etc.)
        # For now, return success with placeholder
        return SkillResult(
            success=True,
            data={
                "message_id": message.id,
                "to": message.to,
                "subject": message.subject,
                "body_preview": message.body[:100] + "..." if len(message.body) > 100 else message.body,
                "status": "sent",
                "provider": "placeholder",
                "message": f"Email sent to {', '.join(message.to)} (placeholder - no actual email sent)",
            },
            metadata={"action": "send", "recipient_count": len(message.to)},
        )

    async def _create_draft(self, context: SkillContext) -> SkillResult:
        """Create an email draft."""
        params = context.parameters

        to = params.get("to", [])
        if isinstance(to, str):
            to = [to]

        subject = params.get("subject", "")
        body = params.get("body", "")

        message = EmailMessage(
            id=str(uuid.uuid4()),
            to=to,
            subject=subject,
            body=body,
        )

        # TODO: Save to drafts
        return SkillResult(
            success=True,
            data={
                "draft_id": message.id,
                "to": message.to,
                "subject": message.subject,
                "status": "draft",
                "message": "Draft created (placeholder)",
            },
            metadata={"action": "draft"},
        )

    async def _schedule_email(self, context: SkillContext) -> SkillResult:
        """Schedule an email for later sending."""
        params = context.parameters

        to = params.get("to", [])
        if isinstance(to, str):
            to = [to]
        if not to:
            return SkillResult(success=False, error="Recipient (to) is required")

        subject = params.get("subject", "")
        body = params.get("body", "")
        send_at = params.get("send_at")

        if not send_at:
            return SkillResult(success=False, error="send_at time is required for scheduling")

        try:
            scheduled_time = datetime.fromisoformat(send_at.replace("Z", "+00:00"))
        except ValueError:
            return SkillResult(success=False, error=f"Invalid send_at format: {send_at}")

        message = EmailMessage(
            id=str(uuid.uuid4()),
            to=to,
            subject=subject,
            body=body,
            scheduled_at=scheduled_time,
        )

        # TODO: Queue email for scheduled sending
        return SkillResult(
            success=True,
            data={
                "scheduled_id": message.id,
                "to": message.to,
                "subject": message.subject,
                "scheduled_at": scheduled_time.isoformat(),
                "status": "scheduled",
                "message": f"Email scheduled for {scheduled_time.isoformat()} (placeholder)",
            },
            metadata={"action": "schedule"},
        )

    async def _send_from_template(self, context: SkillContext) -> SkillResult:
        """Send email using a template."""
        params = context.parameters

        template_name = params.get("template")
        if not template_name:
            return SkillResult(success=False, error="Template name is required")

        to = params.get("to", [])
        if isinstance(to, str):
            to = [to]
        if not to:
            return SkillResult(success=False, error="Recipient (to) is required")

        # Template variables
        variables = params.get("variables", {})

        # TODO: Load template and substitute variables
        # Placeholder templates
        templates = {
            "task_reminder": {
                "subject": "Reminder: {task_title}",
                "body": "This is a reminder about your task: {task_title}\n\nDue: {due_date}",
            },
            "task_completed": {
                "subject": "Task Completed: {task_title}",
                "body": "The task '{task_title}' has been marked as completed.",
            },
            "daily_summary": {
                "subject": "Daily Task Summary",
                "body": "Here's your daily summary:\n\nCompleted: {completed_count}\nPending: {pending_count}",
            },
        }

        template = templates.get(template_name)
        if not template:
            return SkillResult(
                success=False,
                error=f"Template '{template_name}' not found. Available: {list(templates.keys())}",
            )

        # Substitute variables
        subject = template["subject"]
        body = template["body"]
        for key, value in variables.items():
            subject = subject.replace(f"{{{key}}}", str(value))
            body = body.replace(f"{{{key}}}", str(value))

        return SkillResult(
            success=True,
            data={
                "message_id": str(uuid.uuid4()),
                "to": to,
                "subject": subject,
                "body": body,
                "template": template_name,
                "status": "sent",
                "message": f"Template email sent to {', '.join(to)} (placeholder)",
            },
            metadata={"action": "template", "template_name": template_name},
        )

    async def _preview_email(self, context: SkillContext) -> SkillResult:
        """Preview an email without sending."""
        params = context.parameters

        to = params.get("to", [])
        if isinstance(to, str):
            to = [to]

        subject = params.get("subject", "(No subject)")
        body = params.get("body", "")

        # Check for template
        template_name = params.get("template")
        if template_name:
            variables = params.get("variables", {})
            # Would load and render template here
            body = f"[Template: {template_name}] " + body

        return SkillResult(
            success=True,
            data={
                "preview": True,
                "to": to,
                "subject": subject,
                "body": body,
                "estimated_recipients": len(to),
            },
            metadata={"action": "preview"},
        )

    async def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters."""
        action = parameters.get("action")
        if not action:
            return False, "Action is required"

        # Validate email addresses
        to = parameters.get("to", [])
        if isinstance(to, str):
            to = [to]
        for email in to:
            if "@" not in email:
                return False, f"Invalid email address: {email}"

        return True, None

    def requires_approval(self, context: SkillContext) -> bool:
        """All email sending requires approval (except preview)."""
        action = context.parameters.get("action", "")
        if action == "preview":
            return False
        return True
