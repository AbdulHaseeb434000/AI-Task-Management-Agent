"""Communication Agent - Specialist for notifications and user communication."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents import Agent, function_tool


@function_tool
def send_notification(
    recipient: str,
    message: str,
    channel: str = "default",
    priority: str = "normal",
) -> dict:
    """Send a notification to a user.

    Args:
        recipient: User identifier or "all" for broadcast
        message: Notification content
        channel: Delivery channel (default, email, slack, sms)
        priority: Notification priority (low, normal, high, urgent)

    Returns:
        Notification delivery status
    """
    return {
        "status": "sent",
        "recipient": recipient,
        "channel": channel,
        "priority": priority,
        "message_preview": message[:100] if len(message) > 100 else message,
    }


@function_tool
def send_progress_update(
    task_id: str,
    progress_percent: int,
    status_message: str,
    details: dict = None,
) -> dict:
    """Send a progress update for a task.

    Args:
        task_id: The task being updated
        progress_percent: Completion percentage (0-100)
        status_message: Brief status description
        details: Optional additional details

    Returns:
        Update delivery status
    """
    return {
        "status": "sent",
        "task_id": task_id,
        "progress": progress_percent,
        "message": status_message,
        "details": details or {},
    }


@function_tool
def request_user_input(
    prompt: str,
    input_type: str = "text",
    options: list[str] = None,
    required: bool = True,
) -> dict:
    """Request input from the user.

    Args:
        prompt: The question or prompt for the user
        input_type: Expected input type (text, choice, confirmation, file)
        options: Available options for choice type
        required: Whether input is required

    Returns:
        Request status (actual input handled asynchronously)
    """
    return {
        "status": "pending",
        "prompt": prompt,
        "input_type": input_type,
        "options": options,
        "required": required,
    }


@function_tool
def send_alert(
    alert_type: str,
    title: str,
    message: str,
    severity: str = "info",
    action_required: bool = False,
) -> dict:
    """Send an alert to the user.

    Args:
        alert_type: Type of alert (task_complete, error, warning, reminder)
        title: Alert title
        message: Alert message content
        severity: Alert severity (info, warning, error, critical)
        action_required: Whether user action is needed

    Returns:
        Alert delivery status
    """
    return {
        "status": "sent",
        "alert_type": alert_type,
        "title": title,
        "severity": severity,
        "action_required": action_required,
    }


@function_tool
def schedule_reminder(
    task_id: str,
    reminder_time: str,
    message: str,
    repeat: str = None,
) -> dict:
    """Schedule a reminder for a task.

    Args:
        task_id: The related task ID
        reminder_time: ISO timestamp or relative time ("1h", "1d")
        message: Reminder message
        repeat: Repeat interval (daily, weekly, or None)

    Returns:
        Scheduled reminder details
    """
    return {
        "status": "scheduled",
        "task_id": task_id,
        "scheduled_for": reminder_time,
        "message": message,
        "repeat": repeat,
    }


@function_tool
def format_summary_report(
    title: str,
    sections: list[dict],
    include_metrics: bool = True,
) -> dict:
    """Format a summary report for user communication.

    Args:
        title: Report title
        sections: List of sections with 'heading' and 'content'
        include_metrics: Whether to include task metrics

    Returns:
        Formatted report
    """
    formatted_sections = []
    for section in sections:
        formatted_sections.append({
            "heading": section.get("heading", "Section"),
            "content": section.get("content", ""),
        })

    return {
        "status": "success",
        "title": title,
        "sections": formatted_sections,
        "include_metrics": include_metrics,
    }


COMMUNICATION_AGENT_INSTRUCTIONS = """You are a Communication Agent specialized in user notifications and coordination.

## Capabilities

- **Notifications**: Send updates via various channels
- **Progress Updates**: Keep users informed of task progress
- **Alerts**: Send important alerts with appropriate severity
- **Reminders**: Schedule task reminders
- **Input Requests**: Request user input when needed
- **Reports**: Format summary reports

## Communication Channels

- Default (in-app notifications)
- Email
- Slack
- SMS (high priority only)

## Alert Severities

- **info**: Routine updates
- **warning**: Potential issues
- **error**: Action needed
- **critical**: Immediate attention required

## Guidelines

1. Be concise and clear
2. Use appropriate priority levels
3. Don't over-notify (batch when possible)
4. Include actionable information
5. Respect user preferences

## When to Alert

- Task completion
- Errors requiring attention
- Approval requests
- Scheduled reminders
- Progress milestones

## Message Format

- Keep subject lines under 60 characters
- Lead with the most important info
- Include relevant task IDs
- Provide clear next steps

Clear communication drives action. Be brief, be clear, be helpful.
"""


def create_communication_agent() -> Agent:
    """Create the communication specialist agent."""
    return Agent(
        name="Communication Agent",
        instructions=COMMUNICATION_AGENT_INSTRUCTIONS,
        model="gpt-4o",
        tools=[
            send_notification,
            send_progress_update,
            request_user_input,
            send_alert,
            schedule_reminder,
            format_summary_report,
        ],
    )


# Alias for consistency
CommunicationAgent = create_communication_agent
