#!/usr/bin/env python3
"""Communication operations script - notifications, alerts, reminders."""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path


def get_db_path() -> Path:
    """Get the database path."""
    return Path(__file__).parent.parent / "data" / "notifications.db"


def init_notification_db():
    """Initialize the notifications database."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            recipient TEXT NOT NULL,
            message TEXT NOT NULL,
            priority TEXT DEFAULT 'normal',
            channel TEXT DEFAULT 'default',
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            sent_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            message TEXT NOT NULL,
            scheduled_for TEXT NOT NULL,
            repeat TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def send_notification(
    recipient: str,
    message: str,
    priority: str = "normal",
    channel: str = "default",
) -> dict:
    """Queue a notification for sending."""
    init_notification_db()

    conn = sqlite3.connect(get_db_path())
    cursor = conn.execute(
        """
        INSERT INTO notifications (type, recipient, message, priority, channel, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("notification", recipient, message, priority, channel, "queued", datetime.now().isoformat())
    )
    notification_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "queued",
        "notification_id": notification_id,
        "recipient": recipient,
        "priority": priority,
        "channel": channel,
    }


def send_alert(
    title: str,
    message: str,
    severity: str = "info",
    action_required: bool = False,
) -> dict:
    """Queue an alert."""
    init_notification_db()

    full_message = f"[{severity.upper()}] {title}: {message}"
    if action_required:
        full_message += " [ACTION REQUIRED]"

    conn = sqlite3.connect(get_db_path())
    cursor = conn.execute(
        """
        INSERT INTO notifications (type, recipient, message, priority, channel, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("alert", "all", full_message, severity, "default", "queued", datetime.now().isoformat())
    )
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "queued",
        "alert_id": alert_id,
        "severity": severity,
        "action_required": action_required,
    }


def schedule_reminder(
    message: str,
    scheduled_for: str,
    task_id: str = None,
    repeat: str = None,
) -> dict:
    """Schedule a reminder."""
    init_notification_db()

    conn = sqlite3.connect(get_db_path())
    cursor = conn.execute(
        """
        INSERT INTO reminders (task_id, message, scheduled_for, repeat, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (task_id, message, scheduled_for, repeat, "pending", datetime.now().isoformat())
    )
    reminder_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "scheduled",
        "reminder_id": reminder_id,
        "scheduled_for": scheduled_for,
        "repeat": repeat,
    }


def get_pending_notifications() -> dict:
    """Get all pending notifications."""
    init_notification_db()

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM notifications WHERE status = 'queued' ORDER BY created_at"
    )
    notifications = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "status": "success",
        "count": len(notifications),
        "notifications": notifications,
    }


def get_pending_reminders() -> dict:
    """Get all pending reminders."""
    init_notification_db()

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM reminders WHERE status = 'pending' ORDER BY scheduled_for"
    )
    reminders = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "status": "success",
        "count": len(reminders),
        "reminders": reminders,
    }


def mark_sent(notification_id: int) -> dict:
    """Mark a notification as sent."""
    init_notification_db()

    conn = sqlite3.connect(get_db_path())
    conn.execute(
        "UPDATE notifications SET status = 'sent', sent_at = ? WHERE id = ?",
        (datetime.now().isoformat(), notification_id)
    )
    conn.commit()
    conn.close()

    return {"status": "success", "notification_id": notification_id, "marked": "sent"}


def format_progress_update(
    task_id: str,
    progress: int,
    status_message: str,
) -> dict:
    """Format a progress update message."""
    bar_length = 20
    filled = int(bar_length * progress / 100)
    bar = "█" * filled + "░" * (bar_length - filled)

    message = f"Task {task_id}: [{bar}] {progress}%\n{status_message}"

    return {
        "status": "success",
        "formatted_message": message,
        "task_id": task_id,
        "progress": progress,
    }


def main():
    parser = argparse.ArgumentParser(description="Communication operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # notify command
    notify_parser = subparsers.add_parser("notify", help="Send notification")
    notify_parser.add_argument("recipient", help="Recipient identifier")
    notify_parser.add_argument("message", help="Notification message")
    notify_parser.add_argument("--priority", "-p", default="normal",
                                choices=["low", "normal", "high", "urgent"])
    notify_parser.add_argument("--channel", "-c", default="default")

    # alert command
    alert_parser = subparsers.add_parser("alert", help="Send alert")
    alert_parser.add_argument("title", help="Alert title")
    alert_parser.add_argument("message", help="Alert message")
    alert_parser.add_argument("--severity", "-s", default="info",
                               choices=["info", "warning", "error", "critical"])
    alert_parser.add_argument("--action", "-a", action="store_true",
                               help="Action required")

    # remind command
    remind_parser = subparsers.add_parser("remind", help="Schedule reminder")
    remind_parser.add_argument("message", help="Reminder message")
    remind_parser.add_argument("scheduled_for", help="When to remind (ISO format)")
    remind_parser.add_argument("--task", "-t", help="Related task ID")
    remind_parser.add_argument("--repeat", "-r", choices=["daily", "weekly"])

    # pending command
    pending_parser = subparsers.add_parser("pending", help="Get pending items")
    pending_parser.add_argument("--type", "-t", default="all",
                                 choices=["all", "notifications", "reminders"])

    # progress command
    progress_parser = subparsers.add_parser("progress", help="Format progress update")
    progress_parser.add_argument("task_id", help="Task ID")
    progress_parser.add_argument("progress", type=int, help="Progress percentage")
    progress_parser.add_argument("message", help="Status message")

    # sent command
    sent_parser = subparsers.add_parser("sent", help="Mark notification as sent")
    sent_parser.add_argument("notification_id", type=int, help="Notification ID")

    args = parser.parse_args()

    if args.command == "notify":
        result = send_notification(args.recipient, args.message, args.priority, args.channel)
    elif args.command == "alert":
        result = send_alert(args.title, args.message, args.severity, args.action)
    elif args.command == "remind":
        result = schedule_reminder(args.message, args.scheduled_for, args.task, args.repeat)
    elif args.command == "pending":
        if args.type == "notifications":
            result = get_pending_notifications()
        elif args.type == "reminders":
            result = get_pending_reminders()
        else:
            notifs = get_pending_notifications()
            reminders = get_pending_reminders()
            result = {
                "notifications": notifs["notifications"],
                "reminders": reminders["reminders"],
            }
    elif args.command == "progress":
        result = format_progress_update(args.task_id, args.progress, args.message)
    elif args.command == "sent":
        result = mark_sent(args.notification_id)
    else:
        result = {"error": "Unknown command"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
