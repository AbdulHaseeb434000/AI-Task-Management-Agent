# Multi-Agent System Blueprint

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INPUT                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR AGENT                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    PLANNER MODULE                                │    │
│  │  • Analyze user request                                          │    │
│  │  • Create execution plan                                         │    │
│  │  • Break down into subtasks                                      │    │
│  │  • Determine specialist assignments                              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  Tools: plan_task, create_subtasks, save_to_db, assign_specialist       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
        ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
        │   CODE        │ │   RESEARCH    │ │   WRITING     │
        │   AGENT       │ │   AGENT       │ │   AGENT       │
        ├───────────────┤ ├───────────────┤ ├───────────────┤
        │ Uses skill:   │ │ Uses skill:   │ │ Uses skill:   │
        │ code-         │ │ research-     │ │ writing-      │
        │ specialist    │ │ specialist    │ │ specialist    │
        │               │ │               │ │               │
        │ Script:       │ │ Script:       │ │ Script:       │
        │ code_ops.py   │ │ research_     │ │ writing_      │
        │               │ │ ops.py        │ │ ops.py        │
        └───────────────┘ └───────────────┘ └───────────────┘
                │               │               │
                └───────────────┼───────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATABASE (SQLite)                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Tasks     │  │  Subtasks   │  │   Plans     │  │  Execution  │     │
│  │             │  │             │  │             │  │    Logs     │     │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Models

### Task
```python
class Task:
    id: str                    # UUID
    title: str                 # Short title
    description: str           # Full description
    status: TaskStatus         # pending | planning | in_progress | completed | failed
    priority: int              # 1-5 (5 = highest)
    created_at: datetime
    updated_at: datetime
    plan_id: str | None        # Reference to plan
    parent_id: str | None      # For subtasks
    assigned_agent: str | None # Which specialist handles this
    result: str | None         # Outcome when completed
    metadata: dict             # Additional context
```

### Plan
```python
class Plan:
    id: str                    # UUID
    task_id: str               # Parent task
    strategy: str              # High-level approach
    steps: list[PlanStep]      # Ordered steps
    created_at: datetime
    estimated_duration: int    # Minutes
```

### PlanStep
```python
class PlanStep:
    order: int                 # Execution order
    description: str           # What to do
    agent_type: str            # Which specialist
    dependencies: list[int]    # Steps that must complete first
    subtask_id: str | None     # Created subtask reference
```

## Agent Definitions

### 1. Orchestrator Agent (Main)

**Role**: Central coordinator that plans and delegates

**Instructions**:
```
You are the Orchestrator Agent for a task management system.

When a user gives you a task:
1. Analyze the request to understand the full scope
2. Create a strategic plan with clear steps
3. Break down into subtasks with appropriate assignments
4. Save everything to the database
5. Hand off subtasks to specialist agents
6. Monitor progress and report back

Always think step-by-step and be thorough in planning.
```

**Tools**:
- `analyze_request`: Parse and understand user intent
- `create_plan`: Generate execution strategy
- `create_subtasks`: Break plan into actionable items
- `save_task`: Persist to database
- `get_task_status`: Check progress
- `update_task`: Modify task details

**Handoffs**:
- → Code Agent (for programming tasks)
- → Research Agent (for information gathering)
- → Writing Agent (for documentation/content)
- → Communication Agent (for emails/messages)
- → File Agent (for file operations)

### 2. Code Agent (Specialist)

**Role**: Handle all programming-related tasks

**Instructions**:
```
You are a Code Agent specialized in software development.

Your capabilities:
- Write clean, tested code
- Debug and fix issues
- Refactor for better quality
- Explain code and architecture

Always follow best practices and include error handling.
When done, update the task status and provide results.
```

**Tools**:
- `write_code`: Generate code files
- `run_code`: Execute and test
- `analyze_code`: Review for issues
- `update_task_result`: Save outcome

### 3. Research Agent (Specialist)

**Role**: Gather and synthesize information

**Instructions**:
```
You are a Research Agent specialized in information gathering.

Your capabilities:
- Search the web for current information
- Fetch and analyze documentation
- Summarize findings concisely
- Provide cited sources

Always verify information and provide balanced perspectives.
When done, update the task status and provide results.
```

**Tools**:
- `web_search`: Search the internet
- `fetch_url`: Get page content
- `fetch_docs`: Get library documentation (Context7)
- `summarize`: Condense information
- `update_task_result`: Save outcome

### 4. Writing Agent (Specialist)

**Role**: Create and edit written content

**Instructions**:
```
You are a Writing Agent specialized in content creation.

Your capabilities:
- Draft documents, emails, reports
- Edit and improve existing text
- Format content appropriately
- Proofread for errors

Match tone and style to the context.
When done, update the task status and provide results.
```

**Tools**:
- `draft_content`: Create new text
- `edit_content`: Improve existing text
- `format_document`: Apply formatting
- `update_task_result`: Save outcome

### 5. Communication Agent (Specialist)

**Role**: Handle external communications

**Instructions**:
```
You are a Communication Agent for external interactions.

Your capabilities:
- Draft emails and messages
- Schedule communications
- Manage follow-ups

IMPORTANT: Always require approval before sending.
When done, update the task status and provide results.
```

**Tools**:
- `draft_email`: Compose email (approval required)
- `draft_message`: Compose message (approval required)
- `schedule_reminder`: Set follow-up
- `update_task_result`: Save outcome

## Workflow Example

**User Input**: "Build a REST API for user authentication with JWT"

### Step 1: Orchestrator Plans
```
Plan:
1. Research JWT best practices (Research Agent)
2. Design API endpoints (Code Agent)
3. Implement authentication logic (Code Agent)
4. Write tests (Code Agent)
5. Create API documentation (Writing Agent)
```

### Step 2: Subtasks Created
```
Subtask 1: Research JWT authentication patterns
  - Agent: Research
  - Priority: 5
  - Dependencies: None

Subtask 2: Design /auth endpoints schema
  - Agent: Code
  - Priority: 4
  - Dependencies: [1]

Subtask 3: Implement login/register/refresh
  - Agent: Code
  - Priority: 4
  - Dependencies: [2]

Subtask 4: Write unit and integration tests
  - Agent: Code
  - Priority: 3
  - Dependencies: [3]

Subtask 5: Document API with OpenAPI spec
  - Agent: Writing
  - Priority: 2
  - Dependencies: [3]
```

### Step 3: Execution
- Research Agent completes research → saves findings
- Code Agent designs endpoints → saves schema
- Code Agent implements auth → saves code
- Code Agent writes tests → saves test results
- Writing Agent creates docs → saves documentation

### Step 4: Completion
- Orchestrator aggregates results
- Reports to user with summary

## File Structure

```
src/
├── agent/
│   ├── __init__.py
│   ├── orchestrator.py       # Main orchestrator agent (has planning tools)
│   ├── specialists/          # Lightweight agents (no tools, use skills)
│   │   ├── __init__.py
│   │   ├── code_agent.py
│   │   ├── research_agent.py
│   │   ├── writing_agent.py
│   │   └── communication_agent.py
│   └── tools/
│       ├── __init__.py
│       ├── planning.py       # Orchestrator planning tools
│       └── database.py       # Orchestrator DB tools
│
├── scripts/                  # Executable skill scripts
│   ├── code_ops.py           # Code operations
│   ├── research_ops.py       # Research operations
│   ├── writing_ops.py        # Writing operations
│   └── comm_ops.py           # Communication operations
│
├── database/
│   ├── __init__.py
│   ├── models.py             # Pydantic models
│   ├── connection.py         # SQLite connection
│   └── operations.py         # CRUD operations
│
└── data/                     # Runtime data (gitignored)
    ├── tasks.db              # Task database
    └── notifications.db      # Notification queue

.claude/skills/               # Skill definitions
├── code-specialist/SKILL.md
├── research-specialist/SKILL.md
├── writing-specialist/SKILL.md
└── communication-specialist/SKILL.md
```

## Key Design Decisions

### 1. Skills-Based Architecture (Not Tools)

Specialist agents use **skills and scripts** instead of `@function_tool`:

**Why skills over tools:**
- Tools load everything into context upfront (wasteful)
- Skills load on-demand only when needed (efficient)
- Scripts are standalone executables (testable, debuggable)
- Progressive disclosure: instructions first, capability when used

**Structure:**
```
.claude/skills/
├── code-specialist/SKILL.md      → src/scripts/code_ops.py
├── research-specialist/SKILL.md  → src/scripts/research_ops.py
├── writing-specialist/SKILL.md   → src/scripts/writing_ops.py
└── communication-specialist/SKILL.md → src/scripts/comm_ops.py
```

**Execution:**
```bash
uv run python src/scripts/code_ops.py analyze <file>
uv run python src/scripts/writing_ops.py draft <file> -t "Title"
```

### 2. Handoffs vs Agents-as-Tools

Using **handoffs** for specialist agents because:
- Specialists need full autonomy to complete subtasks
- Each specialist has its own tools and context
- Clear separation of responsibilities

### 2. Database Persistence

SQLite for simplicity, with option to upgrade:
- Tasks and subtasks persisted immediately
- Execution logs for debugging
- Session memory for conversation context

### 3. Approval Queue

Communications Agent requires approval:
- Emails/messages queued, not sent directly
- User confirms before external actions
- Audit trail maintained

### 4. Error Handling

Each agent handles its own errors:
- Retry logic for transient failures
- Escalate to orchestrator for critical failures
- Task marked as failed with reason

## Next Steps

1. Implement database models
2. Create orchestrator agent with planning tools
3. Implement specialist agents
4. Add task management tools
5. Create API endpoints
6. Add tests
