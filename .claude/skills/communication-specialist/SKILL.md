---
name: communication-specialist
description: Handle notifications, alerts, and reminders. Use when the task involves sending updates to users, scheduling reminders, or creating progress reports. Actions are queued for approval.
---

# Communication Specialist

Execute communication operations using `src/scripts/comm_ops.py`.

## Commands

### Send Notification
```bash
uv run python src/scripts/comm_ops.py notify "<recipient>" "<message>" -p <priority> -c <channel>
```
Priorities: `low`, `normal`, `high`, `urgent`

### Send Alert
```bash
uv run python src/scripts/comm_ops.py alert "<title>" "<message>" -s <severity>
uv run python src/scripts/comm_ops.py alert "<title>" "<message>" -s error -a  # action required
```
Severities: `info`, `warning`, `error`, `critical`

### Schedule Reminder
```bash
uv run python src/scripts/comm_ops.py remind "<message>" "<scheduled_for>" -t <task_id>
uv run python src/scripts/comm_ops.py remind "Check status" "2024-01-15T10:00:00" -r daily
```

### View Pending Items
```bash
uv run python src/scripts/comm_ops.py pending -t all
uv run python src/scripts/comm_ops.py pending -t notifications
uv run python src/scripts/comm_ops.py pending -t reminders
```

### Format Progress Update
```bash
uv run python src/scripts/comm_ops.py progress "<task_id>" <percent> "<status_message>"
```

### Mark as Sent
```bash
uv run python src/scripts/comm_ops.py sent <notification_id>
```

## Notes

- Notifications are queued, not sent immediately
- Critical alerts should be used sparingly
- All actions are logged for audit trail
