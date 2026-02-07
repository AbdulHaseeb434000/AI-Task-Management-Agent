---
name: communication-specialist
description: Handle notifications, alerts, and reminders. Use when the task involves sending updates to users, scheduling reminders, or creating progress reports. Actions are queued for approval.
---

# Communication Specialist

Execute communication operations using `scripts/comm_ops.py`.

## Commands

### Send Notification
```bash
uv run python .claude/skills/communication-specialist/scripts/comm_ops.py notify "<recipient>" "<message>" -p <priority>
```
Priorities: `low`, `normal`, `high`, `urgent`

### Send Alert
```bash
uv run python .claude/skills/communication-specialist/scripts/comm_ops.py alert "<title>" "<message>" -s <severity>
```
Severities: `info`, `warning`, `error`, `critical` (add `-a` for action required)

### Schedule Reminder
```bash
uv run python .claude/skills/communication-specialist/scripts/comm_ops.py remind "<message>" "<scheduled_for>" -t <task_id>
```

### View Pending Items
```bash
uv run python .claude/skills/communication-specialist/scripts/comm_ops.py pending -t all
```

### Format Progress Update
```bash
uv run python .claude/skills/communication-specialist/scripts/comm_ops.py progress "<task_id>" <percent> "<message>"
```

### Mark as Sent
```bash
uv run python .claude/skills/communication-specialist/scripts/comm_ops.py sent <notification_id>
```

## Notes

- Notifications are queued, not sent immediately
- All actions logged for audit trail
