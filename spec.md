# AI Task Management Agent - Specification

## Overview

The AI Task Management Agent is an intelligent assistant that manages user tasks autonomously. It analyzes tasks, prioritizes them, breaks down complex tasks, provides suggestions, asks clarifying questions, schedules when required, accomplishes tasks on its own when possible, and reminds users proactively.

### Core Philosophy

- **Skills-based architecture**: Capabilities are loaded on-demand, not all at once
- **Minimal context overhead**: Efficient memory management to avoid token overload
- **User-centric simplicity**: Hide complexity, surface only what's needed
- **Safe autonomous execution**: Act independently within boundaries, ask when uncertain

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                           │
│                  (API / CLI / Web / Chat - TBD)                 │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CORE AGENT LAYER                           │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │ Conversation│  │    Task      │  │    Decision Maker     │   │
│  │   Handler   │  │  Analyzer    │  │  (Skill Selection)    │   │
│  └─────────────┘  └──────────────┘  └───────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                       SKILL REGISTRY                            │
│         (Dynamic Loading / Manifest / Permissions)              │
└─────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ INTERNAL SKILLS │    │ EXTERNAL SKILLS │    │AUTONOMOUS SKILLS│
│   (CRUD, etc)   │    │ (Integrations)  │    │ (Self-execute)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXECUTION SANDBOX                            │
│              (Isolated, Secure, Audited)                        │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                 │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────────┐   │
│  │  Tasks   │  │  Memory   │  │  Audit   │  │   User Prefs  │   │
│  │   Store  │  │   Store   │  │   Log    │  │               │   │
│  └──────────┘  └───────────┘  └──────────┘  └───────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Core Agent Layer

### 1.1 Conversation Handler
- Interprets user intent from natural language
- Manages multi-turn conversation context
- Handles session persistence and handoff
- Routes requests to appropriate components

### 1.2 Task Analyzer
- Analyzes incoming tasks for complexity
- Identifies dependencies and relationships
- Estimates effort and suggests breakdowns
- Detects urgency and priority signals

### 1.3 Decision Maker
- Determines which skills to invoke
- Orchestrates multi-skill workflows
- Handles fallback logic when skills fail
- Respects approval boundaries

---

## 2. Skills System

Skills are modular, on-demand capabilities that the agent can invoke. They are not loaded into context until needed.

### 2.1 Directory Structure

```
skills/
├── internal/              # App operations (always available)
│   ├── task_crud.py       # Create, read, update, delete tasks
│   ├── prioritize.py      # Priority scoring algorithm
│   ├── breakdown.py       # Split complex tasks into subtasks
│   ├── schedule.py        # Time-based scheduling
│   └── search.py          # Search tasks, history
│
├── external/              # Third-party integrations (on-demand)
│   ├── calendar.py        # Google/Outlook calendar sync
│   ├── email.py           # Send emails, reminders
│   ├── github.py          # Create issues, PRs, track commits
│   ├── slack.py           # Send notifications
│   └── notion.py          # Sync with Notion databases
│
└── autonomous/            # Self-executing capabilities
    ├── research.py        # Web research for task context
    ├── draft.py           # Draft documents, emails
    ├── summarize.py       # Summarize content
    └── code.py            # Simple code generation tasks
```

### 2.2 Skill Manifest Format

Each skill includes a manifest describing its capabilities:

```json
{
  "name": "task_crud",
  "version": "1.0.0",
  "description": "Create, read, update, and delete tasks",
  "triggers": ["create task", "add task", "delete task", "update task", "show tasks"],
  "parameters": {
    "action": {"type": "string", "enum": ["create", "read", "update", "delete"]},
    "task_id": {"type": "string", "optional": true},
    "task_data": {"type": "object", "optional": true}
  },
  "permissions": {
    "approval_required": false,
    "data_access": ["tasks"],
    "external_calls": false
  },
  "timeout_ms": 5000
}
```

---

## 3. Skill Registry

### 3.1 Responsibilities
- Maintains catalog of all available skills
- Handles dynamic loading/unloading
- Validates skill permissions before execution
- Tracks skill versions and compatibility

### 3.2 Loading Strategy
- **Eager load**: Internal CRUD skills (always needed)
- **Lazy load**: External integrations (only when user requests)
- **JIT compile**: Autonomous skills (loaded for specific tasks)

### 3.3 Permission Levels

| Level | Description | Examples |
|-------|-------------|----------|
| `internal` | No approval, no external effects | task_crud, prioritize |
| `external_read` | Reads from external services | calendar_read, github_issues |
| `external_write` | Writes to external services | email_send, slack_post |
| `autonomous` | Executes independently | research, code |

---

## 4. Memory Architecture

### 4.1 Tiered Memory System

```
┌─────────────────────────────────────────────────────────────────┐
│  HOT MEMORY (In-Context) - ~500-1000 tokens                     │
│  ─────────────────────────────────────────────────────────────  │
│  • Current conversation (last few turns)                        │
│  • Active task being discussed                                  │
│  • User's core preferences (compact summary)                    │
│  • Current session state                                        │
│                                                                 │
│  Loaded: Always                                                 │
│  Updated: Every turn                                            │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  WARM MEMORY (Retrieved on-demand via skills)                   │
│  ─────────────────────────────────────────────────────────────  │
│  • Recent tasks (last 7 days)                                   │
│  • Relevant task history (semantic search)                      │
│  • User patterns summary                                        │
│  • Related context for current task                             │
│                                                                 │
│  Loaded: When relevant to current query                         │
│  Updated: Periodically summarized                               │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  COLD MEMORY (Database/Vector Store)                            │
│  ─────────────────────────────────────────────────────────────  │
│  • All historical tasks                                         │
│  • Complete interaction logs                                    │
│  • Full preference history                                      │
│  • Archived data                                                │
│                                                                 │
│  Loaded: Never directly, queried via skills                     │
│  Updated: Append-only with periodic compaction                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Memory Techniques
- **Summarization**: Compress old conversations into summaries
- **Semantic retrieval**: Use embeddings to fetch relevant history
- **Forgetting**: Gracefully expire irrelevant data
- **Preference extraction**: Distill user patterns into compact rules

---

## 5. Task Graph

### 5.1 Internal Representation

Tasks are stored as a directed acyclic graph (DAG) internally:

```
Task {
  id: string
  title: string
  description: string
  status: pending | in_progress | completed | blocked
  priority: 1-5
  due_date: datetime | null
  parent_id: string | null        # For subtasks
  dependencies: string[]          # Task IDs that must complete first
  tags: string[]
  created_at: datetime
  updated_at: datetime
  metadata: object
}
```

### 5.2 User Experience - Hiding Complexity

The agent manages the graph internally but presents simply to users:

| Internal Complexity | User-Facing Presentation |
|---------------------|--------------------------|
| Complex DAG | Simple prioritized list |
| Dependency chains | "After X, you can do Y" |
| Subtask hierarchy | Expandable on demand |
| Blocked tasks | "Waiting on: [task]" |

### 5.3 Approaches

- **Progressive disclosure**: Show top-level tasks by default, expand on request
- **Smart flattening**: Present as list, manage graph internally
- **Natural language**: Describe relationships conversationally
- **Focus mode**: Show only "what's next"

---

## 6. Reminder Engine

### 6.1 Architecture

Server-side cron jobs with push notification delivery:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Scheduler      │────▶│  Reminder       │────▶│  Notification   │
│  (Cron/Queue)   │     │  Processor      │     │  Dispatcher     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                        ┌───────────────────────────────┼───────┐
                        ▼               ▼               ▼       ▼
                   ┌────────┐     ┌──────────┐    ┌──────┐  ┌───────┐
                   │  Push  │     │  Email   │    │ SMS  │  │ Slack │
                   └────────┘     └──────────┘    └──────┘  └───────┘
```

### 6.2 Reminder Types

| Type | Trigger | Example |
|------|---------|---------|
| **Time-based** | Specific datetime | "Remind at 9am tomorrow" |
| **Relative** | Before due date | "Remind 1 hour before deadline" |
| **Smart** | Based on patterns | "You usually do this at 9am" |
| **Recurring** | Periodic | "Every Monday at 10am" |
| **Location-based** | TBD | "Remind when I arrive at office" |

### 6.3 Delivery Channels
- Push notifications (mobile/desktop)
- Email
- SMS (optional)
- Slack/Discord/Teams
- In-app notifications

User configures preferred channels per reminder type.

---

## 7. Learning Module

### 7.1 What the Agent Learns

| Category | Examples |
|----------|----------|
| **Time patterns** | Productive hours, preferred meeting times |
| **Task preferences** | Max subtasks, default priority, naming conventions |
| **Priority signals** | What "urgent" means for this user |
| **Communication style** | Brief vs detailed, formal vs casual |
| **Domain knowledge** | Industry terms, common task types |
| **Completion patterns** | How long tasks actually take vs estimates |

### 7.2 Implementation Approaches

1. **Rule extraction**: Analyze history, extract explicit rules
   - "User schedules gym on Mon/Wed/Fri"
   - "User prefers tasks broken into 3 subtasks max"

2. **Preference embeddings**: Vector representation of behavior
   - Similarity matching for recommendations

3. **Feedback loops**: Learn from corrections
   - Agent sets priority high → user changes to low → adjust

4. **Explicit teaching**: User tells agent preferences
   - "I prefer morning meetings"

### 7.3 Transparency (TBD)

**Option A**: Transparent learning
- "I noticed you prefer morning tasks. Want me to schedule accordingly?"

**Option B**: Silent learning
- Agent adapts without announcing

**Option C**: Hybrid
- Ask for significant changes, silently apply minor ones

---

## 8. Approval Queue

### 8.1 Approval Tiers

```
┌─────────────────────────────────────────────────────────────────┐
│  AUTO-EXECUTE (No approval needed)                              │
│  ─────────────────────────────────────────────────────────────  │
│  • Create / update / complete tasks                             │
│  • Break down tasks into subtasks                               │
│  • Set reminders                                                │
│  • Prioritize and schedule internally                           │
│  • Search and analyze                                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  APPROVAL REQUIRED                                              │
│  ─────────────────────────────────────────────────────────────  │
│  • Send emails / messages                                       │
│  • Place orders / payments                                      │
│  • Modify external systems (calendar, GitHub, etc.)             │
│  • Delete data permanently                                      │
│  • Any action with external side effects                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  USER-CONFIGURABLE                                              │
│  ─────────────────────────────────────────────────────────────  │
│  • User can promote/demote actions between tiers                │
│  • "Always allow calendar edits without asking"                 │
│  • "Always ask before creating subtasks"                        │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Approval Flow

```
Agent wants to execute action
        │
        ▼
┌──────────────────┐
│ Check permission │
│     tier         │
└──────────────────┘
        │
   ┌────┴────┐
   ▼         ▼
Auto      Needs
Execute   Approval
   │         │
   ▼         ▼
Execute   Queue action
   │      & notify user
   │         │
   │         ▼
   │      User decides
   │         │
   │    ┌────┴────┐
   │    ▼         ▼
   │  Approve   Reject
   │    │         │
   │    ▼         ▼
   │  Execute   Cancel
   │    │         │
   └────┴────┬────┘
             ▼
        Log result
```

---

## 9. Execution Sandbox

### 9.1 Requirements

- **Isolation**: Each execution runs in isolated environment
- **Resource limits**: CPU, memory, time constraints
- **Network control**: Whitelist only necessary APIs
- **No persistence**: Stateless execution (state in database, not sandbox)
- **Audit logging**: Complete record of what ran

### 9.2 Cloud Options

| Option | Description | Use Case |
|--------|-------------|----------|
| **Docker** | Container-based isolation | Development, self-hosted |
| **AWS Lambda** | Serverless functions | Production, auto-scaling |
| **GCP Cloud Functions** | Google's serverless | GCP-based deployments |
| **Modal.com** | Python-native serverless | Fast iteration, GPU tasks |
| **E2B.dev** | AI-focused sandboxes | Agent code execution |
| **Firecracker** | Lightweight microVMs | High isolation needs |

### 9.3 Recommended Approach

| Environment | Solution |
|-------------|----------|
| **Development** | Docker containers locally |
| **Production** | E2B or Modal (AI-optimized) |
| **High security** | Firecracker microVMs |

### 9.4 Sandbox Configuration

```yaml
sandbox:
  timeout_ms: 30000
  memory_mb: 512
  cpu_limit: 1.0
  network:
    allowed_hosts:
      - api.openai.com
      - api.github.com
    blocked_hosts:
      - "*"  # Block all by default
  filesystem:
    read_only: true
    temp_dir: /tmp
  audit:
    log_all_calls: true
    log_network: true
```

---

## 10. Error Handling & Recovery

### 10.1 Error Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│  SKILL EXECUTION                                                │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │   Execute    │                                               │
│  └──────────────┘                                               │
│         │                                                       │
│    ┌────┴────┐                                                  │
│    ▼         ▼                                                  │
│ Success   Failure                                               │
│    │         │                                                  │
│    ▼         ▼                                                  │
│ Continue  Retry (3x with exponential backoff)                   │
│              │                                                  │
│         ┌────┴────┐                                             │
│         ▼         ▼                                             │
│      Success   Still failing                                    │
│         │         │                                             │
│         ▼         ▼                                             │
│      Continue  Try fallback skill (if available)                │
│                   │                                             │
│              ┌────┴────┐                                        │
│              ▼         ▼                                        │
│           Success   No fallback                                 │
│              │         │                                        │
│              ▼         ▼                                        │
│           Continue  Graceful degradation                        │
│                        │                                        │
│                        ▼                                        │
│                   Notify user if critical                       │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 Error Types

| Error Type | Response |
|------------|----------|
| **Transient** (network, timeout) | Retry with backoff |
| **Skill failure** | Try fallback, degrade gracefully |
| **Invalid input** | Ask user for clarification |
| **Permission denied** | Request approval or inform user |
| **Critical failure** | Halt, notify user, log for debugging |

---

## 11. Conversation Manager

### 11.1 Responsibilities
- Session persistence across interactions
- Context windowing (keep last N turns)
- Intent tracking across multi-turn conversations
- Graceful handoff (user leaves, comes back later)

### 11.2 Session State

```json
{
  "session_id": "uuid",
  "user_id": "uuid",
  "started_at": "datetime",
  "last_activity": "datetime",
  "context": {
    "current_task": "task_id or null",
    "conversation_history": ["last N turns"],
    "pending_questions": [],
    "pending_approvals": []
  },
  "state": "active | idle | expired"
}
```

### 11.3 Context Windowing
- Keep last 5-10 turns in hot memory
- Summarize older turns
- Retrieve relevant history on demand

---

## 12. Conflict Resolution

### 12.1 Conflict Types

| Conflict | Resolution Strategy |
|----------|---------------------|
| **Schedule overlap** | Notify user, suggest alternatives |
| **Priority contradiction** | Use latest input, ask if ambiguous |
| **Dependency cycle** | Detect and report to user |
| **Resource conflict** | Queue or ask user to prioritize |

### 12.2 Resolution Flow

```
Detect conflict
      │
      ▼
Is it resolvable automatically?
      │
  ┌───┴───┐
  ▼       ▼
 Yes      No
  │       │
  ▼       ▼
Resolve  Present options to user
  │       │
  ▼       ▼
Log     User decides
```

---

## 13. Audit Log

### 13.1 What's Logged

- Every agent decision with reasoning
- All skill invocations (input, output, duration)
- User interactions
- Approvals granted/denied
- Errors and recoveries
- State changes

### 13.2 Log Format

```json
{
  "timestamp": "datetime",
  "event_type": "skill_invoke | decision | user_input | approval | error",
  "user_id": "uuid",
  "session_id": "uuid",
  "details": {
    "skill": "task_crud",
    "action": "create",
    "input": {},
    "output": {},
    "duration_ms": 150,
    "reasoning": "User asked to add a task"
  }
}
```

### 13.3 Use Cases
- Debugging: "Why did the agent do X?"
- Learning: Analyze patterns for improvement
- Compliance: Audit trail for sensitive actions
- User insight: "Show me what you did today"

---

## 14. Security & Authentication

### 14.1 Authentication (TBD)
- User authentication method
- Session management
- API key handling for external services

### 14.2 Data Security
- Encryption at rest
- Encryption in transit
- Credential storage (vault/secrets manager)

### 14.3 Skill Security
- Permission scoping per skill
- API key isolation
- Rate limiting per skill

---

## 15. Undo & Rollback

### 15.1 Undoable Actions

| Action | Undo Strategy |
|--------|---------------|
| Create task | Delete task |
| Update task | Restore previous state |
| Delete task | Soft delete, restore from archive |
| Complete task | Reopen task |
| Send email | Cannot undo (warn before) |

### 15.2 Implementation
- Maintain action history per session
- Store previous state before mutations
- "Undo" command reverses last undoable action

---

## 16. Onboarding Flow

### 16.1 New User Flow

```
1. Welcome & Introduction
   "Hi! I'm your AI task management assistant."

2. Core Preferences
   - Preferred working hours
   - Communication style (brief/detailed)
   - Default reminder timing

3. Integration Setup (Optional)
   - Connect calendar
   - Connect email
   - Connect other services

4. First Task
   - Guide user through creating first task
   - Demonstrate breakdown and prioritization

5. Learning Mode
   - Agent observes and adapts
   - Asks clarifying questions initially
```

### 16.2 Cold Start Problem
- Use sensible defaults
- Ask questions progressively (not all at once)
- Learn from early interactions rapidly

---

## 17. Observability

### 17.1 Metrics to Track
- Response latency
- Skill execution time
- Error rates by skill
- Token usage per request
- User satisfaction signals

### 17.2 Tracing
- Trace ID per request
- Span for each skill invocation
- Distributed tracing for external calls

### 17.3 Dashboards
- System health
- Usage patterns
- Error trends
- Cost tracking

---

## Decisions To Be Made (TBD)

### User Interface
- [ ] API only?
- [ ] CLI interface?
- [ ] Web UI?
- [ ] Mobile app?
- [ ] Chat platform integrations (Slack, Discord, Telegram)?

### Multi-User Support
- [ ] Single user only?
- [ ] Multi-user with isolation?
- [ ] Team/workspace support?
- [ ] Shared tasks and collaboration?

### Database Choice
- [ ] SQLite (simplicity, single-user)
- [ ] PostgreSQL (scale, multi-user)
- [ ] MongoDB (flexibility)
- [ ] Hybrid (SQL + Vector store for embeddings)

### Autonomous Execution Limits
- [ ] What can execute without asking?
- [ ] Token/cost limits per action?
- [ ] Time limits per autonomous task?

### Skill Extensibility
- [ ] Can users add custom skills?
- [ ] Skill marketplace?
- [ ] Skill API for third-party developers?

### Learning Module Transparency
- [ ] Transparent (announce learning)?
- [ ] Silent (adapt quietly)?
- [ ] Hybrid (ask for major changes)?

### Offline/Degraded Mode
- [ ] What works without internet?
- [ ] Fallback behavior when LLM unavailable?
- [ ] Local model option?

### Pricing/Cost Model (if applicable)
- [ ] Free tier limits?
- [ ] Usage-based pricing?
- [ ] Feature-based tiers?

---

## Project Structure (Proposed)

```
ai-task-management-agent/
├── main.py                    # FastAPI entry point
├── pyproject.toml             # Project config
├── uv.lock                    # Dependency lock
├── spec.md                    # This document
│
├── src/
│   ├── agent/                 # Core agent layer
│   │   ├── __init__.py
│   │   ├── core.py            # Main agent orchestrator
│   │   ├── conversation.py    # Conversation handler
│   │   ├── analyzer.py        # Task analyzer
│   │   └── decision.py        # Decision maker
│   │
│   ├── skills/                # Skills system
│   │   ├── __init__.py
│   │   ├── registry.py        # Skill registry
│   │   ├── base.py            # Base skill class
│   │   ├── internal/          # Internal skills
│   │   ├── external/          # External integrations
│   │   └── autonomous/        # Self-executing skills
│   │
│   ├── memory/                # Memory management
│   │   ├── __init__.py
│   │   ├── hot.py             # In-context memory
│   │   ├── warm.py            # Retrieved memory
│   │   └── cold.py            # Database memory
│   │
│   ├── tasks/                 # Task management
│   │   ├── __init__.py
│   │   ├── models.py          # Task models
│   │   ├── graph.py           # Task graph
│   │   └── scheduler.py       # Scheduling logic
│   │
│   ├── reminders/             # Reminder engine
│   │   ├── __init__.py
│   │   ├── scheduler.py       # Cron/queue
│   │   └── dispatcher.py      # Notification dispatch
│   │
│   ├── learning/              # Learning module
│   │   ├── __init__.py
│   │   ├── patterns.py        # Pattern detection
│   │   └── preferences.py     # Preference management
│   │
│   ├── approval/              # Approval queue
│   │   ├── __init__.py
│   │   └── queue.py           # Approval logic
│   │
│   ├── sandbox/               # Execution sandbox
│   │   ├── __init__.py
│   │   └── executor.py        # Sandboxed execution
│   │
│   └── api/                   # API layer
│       ├── __init__.py
│       ├── routes.py          # API routes
│       └── schemas.py         # Request/response schemas
│
├── tests/                     # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── config/                    # Configuration
    ├── default.yaml
    └── production.yaml
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | TBD | Initial specification |

---

## References

- OpenAI Agents SDK: https://github.com/openai/openai-agents-python
- FastAPI: https://fastapi.tiangolo.com/
- E2B Sandboxes: https://e2b.dev/
- Modal: https://modal.com/
